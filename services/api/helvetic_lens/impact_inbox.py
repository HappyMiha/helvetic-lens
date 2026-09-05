"""Organization impact inbox assembled from saved events, candidates and analyses."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from . import relation_analysis as relation_ai
from .config import DomainError
from .models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def principal_key(user_id: str | None) -> str:
    return f"user:{user_id}" if user_id else "anonymous-development"


@dataclass(frozen=True)
class ImpactInboxFilters:
    source: str = ""
    severity: str = ""
    item_type: str = ""
    watched_law: str = ""
    state: str = ""
    candidate: str = ""
    detected_from: datetime | None = None
    detected_before: datetime | None = None
    sources: tuple[str, ...] = ()
    excluded_states: tuple[str, ...] = ()
    event_ids: tuple[str, ...] | None = None
    admitted_before: datetime | None = None


class ImpactInboxReader:
    def __init__(self, organization_id: str, user_id: str | None):
        self.organization_id = organization_id
        self.user_id = user_id
        self.principal = principal_key(user_id)

    @staticmethod
    def _latest_analyses(
        session: Session, organization_candidate_id: str
    ) -> tuple[RelationImpactAnalysis | None, RelationImpactAnalysis | None, int]:
        history = select(RelationImpactAnalysis).where(
            RelationImpactAnalysis.organization_candidate_id == organization_candidate_id
        ).order_by(RelationImpactAnalysis.created_at.desc(), RelationImpactAnalysis.id.desc())
        latest = session.scalar(history.limit(1))
        if latest is None:
            return None, None, 0
        # A newly completed attempt after the first query belongs to the next
        # read, not to a current/failed-latest combination from different tops.
        through_latest = or_(
            RelationImpactAnalysis.created_at < latest.created_at,
            (RelationImpactAnalysis.created_at == latest.created_at)
            & (RelationImpactAnalysis.id <= latest.id),
        )
        history = history.where(through_latest)
        current = latest if latest.status == "succeeded" and relation_ai.result_uses_current_rules(latest.result) else session.scalar(
            history.where(
                RelationImpactAnalysis.status == "succeeded",
                RelationImpactAnalysis.result["schema_version"].as_string() == relation_ai.SCHEMA_VERSION,
            ).limit(1)
        )
        # Count in SQL; never transfer/materialize the historical JSON/evidence
        # payloads just to find two records or display the history count.
        count = session.scalar(select(func.count()).select_from(RelationImpactAnalysis).where(
            RelationImpactAnalysis.organization_candidate_id == organization_candidate_id,
            through_latest,
        )) or 0
        return current, latest, count

    def _history_selection(self, session: Session, model, candidate_ids: list[str], relevant) -> dict[str, tuple]:
        """Select latest/relevant IDs and counts together, then hydrate only those.

        The scalar window query sees one database statement snapshot. New history
        appended before hydration cannot alter its chosen IDs/count. Existing rows
        remain live records; this is not a frozen transaction-wide evidence view.
        """
        if len(candidate_ids) > 100:
            raise ValueError("History selection requires batches of at most 100 candidates.")
        if not candidate_ids:
            return {}
        ordering = (model.created_at.desc(), model.id.desc())
        ranked = select(
            model.id.label("latest_id"), model.organization_candidate_id.label("candidate_id"),
            func.row_number().over(partition_by=model.organization_candidate_id, order_by=ordering).label("position"),
            func.count().over(partition_by=model.organization_candidate_id).label("total"),
            func.first_value(case((relevant, model.id), else_=None)).over(
                partition_by=model.organization_candidate_id,
                order_by=(case((relevant, 0), else_=1), *ordering),
            ).label("relevant_id"),
        ).where(model.organization_id == self.organization_id,
                model.organization_candidate_id.in_(candidate_ids)).subquery()
        metadata = session.execute(select(ranked.c.candidate_id, ranked.c.latest_id, ranked.c.relevant_id, ranked.c.total)
                                   .where(ranked.c.position == 1)).all()
        chosen_ids = {id_ for row in metadata for id_ in (row.latest_id, row.relevant_id) if id_}
        records = {row.id: row for row in session.scalars(select(model).where(
            model.organization_id == self.organization_id, model.id.in_(chosen_ids),
        ))} if chosen_ids else {}
        return {row.candidate_id: (records.get(row.relevant_id), records.get(row.latest_id), row.total) for row in metadata}

    def _page_histories(self, session: Session, candidate_ids: list[str]) -> tuple[dict, dict]:
        analyses = self._history_selection(session, RelationImpactAnalysis, candidate_ids,
                                          (RelationImpactAnalysis.status == "succeeded")
                                          & (RelationImpactAnalysis.result["schema_version"].as_string() == relation_ai.SCHEMA_VERSION))
        reviews = self._history_selection(session, OrganizationRelationReview, candidate_ids,
                                         OrganizationRelationReview.decision.in_(("confirmed", "rejected")))
        return analyses, reviews

    @staticmethod
    def _watch_context(
        session: Session, delivery: OrganizationRelationCandidate
    ) -> tuple[DocumentWatch, Law, RegulatoryWork]:
        watch = session.get(DocumentWatch, delivery.watch_id)
        if not watch:
            raise DomainError("The monitored document is no longer available.", 404, "not_found")
        law = session.get(Law, watch.law_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        target = session.get(RegulatoryWork, candidate.target_work_id) if candidate else None
        if not law or not candidate or not target:
            raise DomainError("The saved impact candidate is incomplete.", 409, "candidate_incomplete")
        return watch, law, target

    @staticmethod
    def _comparison_url(session: Session, law_id: str) -> str | None:
        comparison = session.scalar(
            select(Comparison)
            .where(Comparison.law_id == law_id)
            .order_by(Comparison.created_at.desc(), Comparison.id.desc())
            .limit(1)
        )
        return f"/compare/{comparison.id}" if comparison else None

    @staticmethod
    def _mapped_law(session: Session, work_id: str) -> tuple[Law | None, DocumentWatch | None]:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.work_id == work_id)
        )
        law = session.get(Law, mapping.law_id) if mapping else None
        watch = (
            session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law.id))
            if law
            else None
        )
        return law, watch

    @staticmethod
    def _status(
        relation: RegulatoryRelation | None,
        review: OrganizationRelationReview | None,
        current: RelationImpactAnalysis | None,
        latest: RelationImpactAnalysis | None,
    ) -> str:
        if relation and relation.state == "confirmed":
            return "confirmed_relation"
        if review and review.decision == "confirmed":
            return "confirmed_relation"
        if review and review.decision == "rejected":
            return "no_supported_impact"
        if current and (current.result or {}).get("assessment_status") == "needs_review":
            return "stale"
        if not current and latest and latest.status == "succeeded":
            return "stale"
        if current and (current.result or {}).get("supported"):
            return "possible_impact"
        if current:
            return "no_supported_impact"
        if latest and latest.status == "failed":
            return "analysis_failed"
        return "awaiting_analysis"

    @staticmethod
    def _severity(
        status: str, event: RegulatoryEvent, current: RelationImpactAnalysis | None
    ) -> str:
        # Preserve independent official/deterministic urgency even when AI is
        # unavailable or its unsupported draft has been downgraded.
        if event.impact in {"high", "medium", "low"}:
            return event.impact
        if status == "confirmed_relation" and event.event_type in {"repealed", "replaced"}:
            return "high"
        result = current.result if current else None
        if result and result.get("assessment_status") != "needs_review":
            if result.get("potential_severity") in {"high", "medium", "low", "none"}:
                return result["potential_severity"]
        return "unknown"

    def _law_item(
        self,
        session: Session,
        delivery: OrganizationRelationCandidate,
        candidate: RelationCandidate,
        event: RegulatoryEvent,
        analysis_history: tuple,
        review_history: tuple,
    ) -> dict:
        watch, law, target = self._watch_context(session, delivery)
        relation = session.get(RegulatoryRelation, candidate.relation_id) if candidate.relation_id else None
        review, latest_review, review_history_count = review_history
        current, latest, history_count = analysis_history
        status = self._status(relation, review, current, latest)
        result = (current.result or {}) if current else {}
        citations = result.get("citations") or []
        actions = result.get("actions") or []
        why = candidate.why_json or []
        if isinstance(why, dict):
            why = [why]
        official = relation if relation and relation.state == "confirmed" else None
        if official:
            effect = (
                f"The official source records a {official.relation_type.replace('_', ' ')} "
                "relation to this monitored document."
            )
        elif review and review.decision == "confirmed":
            effect = result.get("explanation") or "An organization administrator confirmed this review lead."
        elif review and review.decision == "rejected":
            effect = review.note or "An organization administrator rejected this proposed impact."
        else:
            effect = result.get("explanation") or (
                "Saved metadata produced a bounded candidate. Local analysis has not yet supplied a valid conclusion."
            )
        next_step = (
            actions[0].get("title")
            if actions
            else "Inspect the saved relation evidence and decide whether monitoring needs attention."
        )
        replacement = None
        if official and official.relation_type == "replaces":
            successor_law, successor_watch = self._mapped_law(session, candidate.source_work_id)
            source_work = session.get(RegulatoryWork, candidate.source_work_id)
            replacement = {
                "predecessor": {
                    "work_id": target.id,
                    "law_id": law.id,
                    "title": watch.display_name,
                    "timeline": f"/laws/{law.id}",
                },
                "successor": {
                    "work_id": source_work.id,
                    "law_id": successor_law.id if successor_law else None,
                    "title": source_work.title,
                    "url": source_work.stable_official_url,
                    "monitored": bool(successor_watch and successor_watch.active),
                    "timeline": f"/laws/{successor_law.id}" if successor_law else None,
                },
            }
        return {
            "organization_candidate_id": delivery.id,
            "candidate_id": candidate.id,
            "watch_id": watch.id,
            "law_id": law.id,
            "law_title": watch.display_name,
            "law_active": watch.active,
            "target_work_id": target.id,
            "status": status,
            "severity": self._severity(status, event, current),
            "why": why,
            "potential_effect": effect,
            "suggested_next_step": next_step,
            "coverage": (current or latest).coverage if (current or latest) else {},
            "current_analysis_id": current.id if current else None,
            "latest_attempt_id": latest.id if latest else None,
            "latest_attempt_status": latest.status if latest else None,
            "latest_attempt_error": latest.error if latest and latest.status == "failed" else None,
            "analysis_history_count": history_count,
            "official_relation": (
                {
                    "id": official.id,
                    "type": official.relation_type,
                    "provenance": official.provenance_method,
                }
                if official
                else None
            ),
            "organization_review": (
                {
                    "id": review.id,
                    "decision": review.decision,
                    "note": review.note,
                    "created_at": _iso(review.created_at),
                }
                if review
                else None
            ),
            "latest_review": (
                {
                    "id": latest_review.id,
                    "decision": latest_review.decision,
                    "note": latest_review.note,
                    "created_at": _iso(latest_review.created_at),
                }
                if latest_review
                else None
            ),
            "review_history_count": review_history_count,
            "replacement": replacement,
            "links": {
                "timeline": f"/laws/{law.id}",
                "comparison": self._comparison_url(session, law.id),
                "relation_evidence": (
                    f"/api/relations/{official.id}"
                    if official
                    else citations[0].get("url") if citations else None
                ),
                "analysis_history": f"/api/relation-candidates/{delivery.id}/analyses",
            },
        }

    def _deliveries(self, filters: ImpactInboxFilters):
        query = (
            select(OrganizationRelationCandidate)
            .join(RelationCandidate, RelationCandidate.id == OrganizationRelationCandidate.candidate_id)
            .join(RegulatoryEvent, RegulatoryEvent.id == RelationCandidate.event_id)
            .join(RegulatoryWork, RegulatoryWork.id == RelationCandidate.source_work_id)
            .where(OrganizationRelationCandidate.organization_id == self.organization_id)
        )
        if filters.detected_from is not None:
            query = query.where(RegulatoryEvent.detected_at >= filters.detected_from)
        if filters.detected_before is not None:
            query = query.where(RegulatoryEvent.detected_at < filters.detected_before)
        if filters.event_ids is not None:
            query = query.where(RegulatoryEvent.id.in_(filters.event_ids))
        if filters.admitted_before is not None:
            query = query.where(OrganizationRelationCandidate.created_at < filters.admitted_before)
        if filters.sources:
            query = query.where(or_(RegulatoryEvent.connector.in_(filters.sources),
                                    RegulatoryEvent.authority.in_(filters.sources)))
        if filters.source:
            query = query.where(or_(RegulatoryEvent.connector == filters.source, RegulatoryEvent.authority == filters.source))
        if filters.item_type:
            query = query.where(or_(RegulatoryEvent.event_type == filters.item_type, RegulatoryWork.kind == filters.item_type))
        if filters.state:
            states = select(RegulatoryEventUserState.id).where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id,
            )
            query = query.where(~states.where(RegulatoryEventUserState.state != "unread").exists()
                                if filters.state == "unread" else states.where(RegulatoryEventUserState.state == filters.state).exists())
        if filters.candidate:
            delivery, candidate = aliased(OrganizationRelationCandidate), aliased(RelationCandidate)
            linked = select(delivery.id).join(candidate, candidate.id == delivery.candidate_id).where(
                delivery.organization_id == self.organization_id, delivery.id == filters.candidate,
                candidate.event_id == RegulatoryEvent.id,
            )
            if filters.admitted_before is not None:
                linked = linked.where(delivery.created_at < filters.admitted_before)
            query = query.where(linked.exists())
        if filters.watched_law:
            delivery, candidate = aliased(OrganizationRelationCandidate), aliased(RelationCandidate)
            watched = select(delivery.id).join(candidate, candidate.id == delivery.candidate_id).join(
                DocumentWatch, DocumentWatch.id == delivery.watch_id,
            ).where(delivery.organization_id == self.organization_id,
                    candidate.event_id == RegulatoryEvent.id,
                    or_(DocumentWatch.id == filters.watched_law, DocumentWatch.law_id == filters.watched_law))
            if filters.admitted_before is not None:
                watched = watched.where(delivery.created_at < filters.admitted_before)
            # Keep every law in selected events until severity is evaluated, so the
            # legacy severity-before-watched-law semantics do not change silently.
            query = query.where(watched.exists())

        if filters.excluded_states:
            excluded = select(RegulatoryEventUserState.id).where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id,
                RegulatoryEventUserState.state.in_(filters.excluded_states),
            ).exists()
            query = query.where(~excluded)
        return query

    def source_options(self, session: Session) -> list[str]:
        # Keep the full available source menu without hydrating candidate/evidence
        # histories, even when the selected digest window or source filter is empty.
        query = self._deliveries(ImpactInboxFilters()).with_only_columns(
            RegulatoryEvent.connector, RegulatoryEvent.authority,
            maintain_column_froms=True,
        ).distinct()
        return sorted({value for row in session.execute(query) for value in row if value})

    def event_page(self, session: Session, filters: ImpactInboxFilters, *, cursor: dict | None = None, page_size: int = 50) -> dict:
        """Read one event keyset page, including a scalar overflow sentinel."""
        if not 1 <= page_size <= 50:
            raise ValueError("Choose an event page size between 1 and 50.")
        filters = replace(filters, admitted_before=filters.admitted_before or datetime.now(UTC))
        keys = self._deliveries(filters).with_only_columns(
            RegulatoryEvent.id, RegulatoryEvent.detected_at, maintain_column_froms=True,
        ).distinct().order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
        if cursor:
            detected_at, event_id = datetime.fromisoformat(cursor["detected_at"]), cursor["id"]
            keys = keys.where(or_(
                RegulatoryEvent.detected_at < detected_at,
                (RegulatoryEvent.detected_at == detected_at) & (RegulatoryEvent.id < event_id),
            ))
        keys = list(session.execute(keys.limit(page_size + 1)))
        selected = keys[:page_size]
        page = self.page(session, replace(filters, event_ids=tuple(row.id for row in selected))) if selected else {"items": []}
        return {
            **page, "scanned": len(selected), "has_more": len(keys) > page_size,
            "admitted_before": _iso(filters.admitted_before),
            "cursor": {"detected_at": _iso(selected[-1].detected_at), "id": selected[-1].id} if selected else cursor,
        }

    def law_options(self, session: Session, *, query: str = "", selected: str = "") -> dict:
        """Small scalar-only watch search, independent of the displayed inbox page."""
        base = select(DocumentWatch.id, DocumentWatch.law_id, DocumentWatch.display_name).where(
            DocumentWatch.organization_id == self.organization_id,
        )
        search = base.where(DocumentWatch.display_name.icontains(query.strip(), autoescape=True)) if query.strip() else base
        rows = session.execute(search.order_by(func.lower(DocumentWatch.display_name), DocumentWatch.id).limit(51)).all()
        chosen = session.execute(base.where(or_(DocumentWatch.id == selected, DocumentWatch.law_id == selected))).first() if selected else None
        def option(row):
            return {"id": row.law_id, "watch_id": row.id, "title": row.display_name}
        return {"items": [option(row) for row in rows[:50]], "has_more": len(rows) > 50,
                "selected": option(chosen) if chosen else None}

    def _cursor_scope(self, filters: ImpactInboxFilters) -> str:
        context = [self.organization_id, self.principal,
                   filters.source, filters.severity, filters.item_type, filters.watched_law, filters.state, filters.candidate]
        return hashlib.sha256(json.dumps(context, ensure_ascii=True).encode()).hexdigest()

    def paginated(self, session: Session, filters: ImpactInboxFilters, *, cursor: str = "", limit: int = 50) -> dict:
        """Public bounded-page contract; counts describe returned groups only.

        Cursors select positions, never permissions. Every read remains scoped to
        the authenticated organization/principal, independently of token contents.
        """
        if not 1 <= limit <= 50:
            raise DomainError("Choose a page size between 1 and 50.", 422, "invalid_inbox_page_size")
        after = None
        if cursor:
            try:
                if len(cursor) > 4096:
                    raise ValueError("Cursor too large")
                payload = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
                if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("scope") != self._cursor_scope(filters):
                    raise ValueError("Different cursor context")
                captured = datetime.fromisoformat(payload["captured_at"])
                after = payload["after"]
                position = datetime.fromisoformat(after["detected_at"])
                if captured.tzinfo is None or position.tzinfo is None or not isinstance(after["id"], str) or not 1 <= len(after["id"]) <= 36:
                    raise ValueError("Invalid cursor position")
                filters = replace(filters, admitted_before=captured)
            except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
                raise DomainError("This inbox page link is invalid for the current filters or account. Open the first page.",
                                  422, "invalid_inbox_cursor") from exc
        page = self.event_page(session, filters, cursor=after, page_size=limit)
        next_cursor = None
        if page["has_more"]:
            payload = {"version": 1, "scope": self._cursor_scope(filters), "captured_at": page["admitted_before"], "after": page["cursor"]}
            next_cursor = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        return {"items": page["items"], "total_events": page.get("total_events", 0),
                "total_impacts": page.get("total_impacts", 0), "unread": page.get("unread", 0),
                "counts_scope": "page", "scanned_event_count": page["scanned"], "limit": limit,
                "captured_at": page["admitted_before"], "has_more": page["has_more"], "next_cursor": next_cursor}

    def iter_groups(self, session: Session, filters: ImpactInboxFilters, *, page_size: int = 50) -> Iterator[dict]:
        """Visit bounded event pages without retaining a full-history list."""
        cursor = None
        while True:
            page = self.event_page(session, filters, cursor=cursor, page_size=page_size)
            yield from page["items"]
            if not page["has_more"]:
                return
            cursor = page["cursor"]
            filters = replace(filters, admitted_before=datetime.fromisoformat(page["admitted_before"]))
            del page

    def page(self, session: Session, filters: ImpactInboxFilters) -> dict:
        query = self._deliveries(filters)
        selected_events = query.with_only_columns(RelationCandidate.event_id, maintain_column_froms=True)
        states = {
            item.event_id: item
            for item in session.scalars(
                select(RegulatoryEventUserState).where(
                    RegulatoryEventUserState.organization_id == self.organization_id,
                    RegulatoryEventUserState.principal_key == self.principal,
                    RegulatoryEventUserState.event_id.in_(selected_events),
                )
            )
        }
        grouped: dict[str, dict] = {}
        deliveries = list(
            session.scalars(
                query.order_by(
                    OrganizationRelationCandidate.created_at.desc(),
                    OrganizationRelationCandidate.id.desc(),
                )
            )
        )
        for start in range(0, len(deliveries), 100):
            batch = deliveries[start:start + 100]
            analyses, reviews = self._page_histories(session, [delivery.id for delivery in batch])
            for delivery in batch:
                candidate = session.get(RelationCandidate, delivery.candidate_id)
                event = session.get(RegulatoryEvent, candidate.event_id) if candidate else None
                source = session.get(RegulatoryWork, candidate.source_work_id) if candidate else None
                if not candidate or not event or not source:
                    continue
                item = self._law_item(session, delivery, candidate, event,
                                      analyses.get(delivery.id, (None, None, 0)), reviews.get(delivery.id, (None, None, 0)))
                state_record = states.get(event.id)
                state = state_record.state if state_record else "unread"
                group = grouped.setdefault(
                    event.id,
                    {
                        "event_id": event.id,
                        "title": source.title or "Untitled regulatory item",
                        "source": event.connector or event.authority,
                        "authority": event.authority,
                        "type": event.event_type,
                        "document_kind": source.kind,
                        "detected_at": _iso(event.detected_at),
                        "source_url": event.source_url or source.stable_official_url,
                        "source_artifact_url": None,
                        "read_state": state,
                        "items": [],
                    },
                )
                if event.document_version_id:
                    source_version = session.get(RegulatoryDocumentVersion, event.document_version_id)
                    if source_version and source_version.legacy_version_id:
                        group["source_artifact_url"] = f"/evidence/{source_version.legacy_version_id}"
                group["items"].append(item)
        groups = []
        order = {"high": 0, "medium": 1, "low": 2, "none": 3, "unknown": 4}
        for group in grouped.values():
            group["items"].sort(key=lambda item: (order.get(item["severity"], 4), item["law_title"]))
            group["severity"] = group["items"][0]["severity"] if group["items"] else "unknown"
            group["coverage"] = {
                "analysed": sum(bool(item["current_analysis_id"]) for item in group["items"]),
                "total": len(group["items"]),
            }
            if filters.source and filters.source not in {group["source"], group["authority"]}:
                continue
            if filters.item_type and filters.item_type not in {group["type"], group["document_kind"]}:
                continue
            if filters.state and filters.state != group["read_state"]:
                continue
            if filters.severity and not any(
                item["severity"] == filters.severity for item in group["items"]
            ):
                continue
            if filters.watched_law:
                group["items"] = [
                    item
                    for item in group["items"]
                    if filters.watched_law in {item["law_id"], item["watch_id"]}
                ]
                if not group["items"]:
                    continue
            groups.append(group)
        groups.sort(key=lambda item: (item["detected_at"] or "", item["event_id"]), reverse=True)
        return {
            "items": groups,
            "total_events": len(groups),
            "total_impacts": sum(len(item["items"]) for item in groups),
            "unread": sum(item["read_state"] == "unread" for item in groups),
        }

    def set_state(self, session: Session, event_id: str, state: str) -> dict:
        if state not in {"unread", "read", "dismissed", "muted"}:
            raise DomainError("Choose unread, read, dismissed, or muted.", 422, "invalid_inbox_state")
        event = session.get(RegulatoryEvent, event_id)
        if not event:
            raise DomainError("The requested event was not found.", 404, "not_found")
        visible = session.scalar(
            select(OrganizationRelationCandidate.id)
            .join(RelationCandidate, RelationCandidate.id == OrganizationRelationCandidate.candidate_id)
            .where(RelationCandidate.event_id == event_id)
            .limit(1)
        )
        if not visible:
            raise DomainError("This event is not in the organization's impact inbox.", 404, "not_found")
        record = session.scalar(
            select(RegulatoryEventUserState).where(
                RegulatoryEventUserState.event_id == event_id,
                RegulatoryEventUserState.principal_key == self.principal,
            )
        )
        if not record:
            record = RegulatoryEventUserState(
                event_id=event_id,
                user_id=self.user_id,
                principal_key=self.principal,
            )
            session.add(record)
        record.state = state
        record.updated_at = datetime.now(UTC)
        session.commit()
        return {"event_id": event_id, "state": state, "updated_at": _iso(record.updated_at)}
