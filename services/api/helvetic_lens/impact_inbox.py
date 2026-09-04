"""Organization impact inbox assembled from saved events, candidates and analyses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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


class ImpactInboxReader:
    def __init__(self, organization_id: str, user_id: str | None):
        self.organization_id = organization_id
        self.user_id = user_id
        self.principal = principal_key(user_id)

    @staticmethod
    def _latest_analyses(
        session: Session, organization_candidate_id: str
    ) -> tuple[RelationImpactAnalysis | None, RelationImpactAnalysis | None, int]:
        records = list(
            session.scalars(
                select(RelationImpactAnalysis)
                .where(
                    RelationImpactAnalysis.organization_candidate_id
                    == organization_candidate_id
                )
                .order_by(RelationImpactAnalysis.created_at.desc(), RelationImpactAnalysis.id.desc())
            )
        )
        current = next((item for item in records if item.status == "succeeded"
                        and relation_ai.result_uses_current_rules(item.result)), None)
        return current, records[0] if records else None, len(records)

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
    ) -> dict:
        watch, law, target = self._watch_context(session, delivery)
        relation = session.get(RegulatoryRelation, candidate.relation_id) if candidate.relation_id else None
        review = session.scalar(
            select(OrganizationRelationReview)
            .where(
                OrganizationRelationReview.organization_candidate_id == delivery.id,
                OrganizationRelationReview.decision.in_(("confirmed", "rejected")),
            )
            .order_by(
                OrganizationRelationReview.created_at.desc(),
                OrganizationRelationReview.id.desc(),
            )
            .limit(1)
        )
        latest_review = session.scalar(
            select(OrganizationRelationReview)
            .where(OrganizationRelationReview.organization_candidate_id == delivery.id)
            .order_by(
                OrganizationRelationReview.created_at.desc(),
                OrganizationRelationReview.id.desc(),
            )
            .limit(1)
        )
        review_history_count = session.scalar(
            select(func.count())
            .select_from(OrganizationRelationReview)
            .where(OrganizationRelationReview.organization_candidate_id == delivery.id)
        ) or 0
        current, latest, history_count = self._latest_analyses(session, delivery.id)
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

    def page(self, session: Session, filters: ImpactInboxFilters) -> dict:
        states = {
            item.event_id: item
            for item in session.scalars(
                select(RegulatoryEventUserState).where(
                    RegulatoryEventUserState.principal_key == self.principal
                )
            )
        }
        grouped: dict[str, dict] = {}
        deliveries = list(
            session.scalars(
                select(OrganizationRelationCandidate).order_by(
                    OrganizationRelationCandidate.created_at.desc(),
                    OrganizationRelationCandidate.id.desc(),
                )
            )
        )
        for delivery in deliveries:
            candidate = session.get(RelationCandidate, delivery.candidate_id)
            event = session.get(RegulatoryEvent, candidate.event_id) if candidate else None
            source = session.get(RegulatoryWork, candidate.source_work_id) if candidate else None
            if not candidate or not event or not source:
                continue
            item = self._law_item(session, delivery, candidate, event)
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
