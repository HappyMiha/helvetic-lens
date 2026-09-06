"""Saved-data registry read model and Europe/Zurich time grouping."""

from __future__ import annotations

import base64
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .config import DomainError
from .corpus_access import event_evidence_links, visible
from .models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Observation,
    RegulatoryDate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
    Version,
)

ZURICH = ZoneInfo("Europe/Zurich")


def search_text(value: str) -> str:
    """Normalize canonically equivalent text and accents for multilingual UI search."""

    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


def aware_utc(value: datetime) -> datetime:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).astimezone(UTC)


def detected_group(
    detected_at: datetime,
    *,
    now: datetime | None = None,
    custom_start: date | None = None,
    custom_end: date | None = None,
) -> str:
    local_day = aware_utc(detected_at).astimezone(ZURICH).date()
    if custom_start or custom_end:
        if custom_start and local_day < custom_start:
            return "Outside range"
        if custom_end and local_day > custom_end:
            return "Outside range"
        return "Custom range"
    today = aware_utc(now or datetime.now(UTC)).astimezone(ZURICH).date()
    age = (today - local_day).days
    if age <= 0:
        return "Today"
    if age == 1:
        return "Yesterday"
    if age <= 6:
        return "Last 7 days"
    if age <= 29:
        return "Last 30 days"
    return "Older"


def _iso(value: datetime | None) -> str | None:
    return aware_utc(value).isoformat() if value else None


def _encode_cursor(row: dict) -> str:
    raw = json.dumps([row["detected_at"], row["id"]], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, str]:
    try:
        payload = value + "=" * (-len(value) % 4)
        timestamp, item_id = json.loads(base64.urlsafe_b64decode(payload).decode())
        return aware_utc(datetime.fromisoformat(timestamp)), str(item_id)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise DomainError("The registry cursor is invalid.", 422, "invalid_registry_cursor") from exc


def _parse_day(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DomainError(f"Use YYYY-MM-DD for {field}.", 422, "invalid_registry_date") from exc


@dataclass(frozen=True)
class RegistryFilters:
    view: str = "monitored"
    query: str = ""
    cursor: str = ""
    limit: int = 30
    authority: str = ""
    connector: str = ""
    kind: str = ""
    language: str = ""
    lifecycle: str = ""
    impact: str = ""
    watched: str = ""
    read: str = ""
    health: str = ""
    start: str = ""
    end: str = ""


class RegistryReader:
    def __init__(self, organization_id: str, user_id: str | None = None):
        self.organization_id = organization_id
        self.user_id = user_id
        self.principal_key = f"user:{user_id}" if user_id else "anonymous-development"

    @staticmethod
    def _dates(session: Session, entity_ids: list[str]) -> dict[str, list[dict]]:
        if not entity_ids:
            return {}
        result: dict[str, list[dict]] = {}
        for item in session.execute(
            select(
                RegulatoryDate.kind,
                RegulatoryDate.date_value,
                RegulatoryDate.precision,
                RegulatoryDate.provenance,
                RegulatoryDate.source_url,
            ).where(RegulatoryDate.entity_id.in_(entity_ids))
        ):
            result.setdefault(item.kind, []).append(
                {
                    "value": item.date_value,
                    "precision": item.precision,
                    "provenance": item.provenance,
                    "source_url": item.source_url,
                }
            )
        return result

    def _linked_laws(self, session: Session, work_id: str) -> list[dict]:
        related = {work_id}
        for relation in session.execute(
            select(RegulatoryRelation.subject_work_id, RegulatoryRelation.object_work_id).where(
                or_(
                    RegulatoryRelation.subject_work_id == work_id,
                    RegulatoryRelation.object_work_id == work_id,
                )
            )
        ):
            related.add(relation.subject_work_id)
            related.add(relation.object_work_id)
        law_ids = list(
            session.scalars(
                select(LegacyDocumentMapping.law_id).where(
                    LegacyDocumentMapping.work_id.in_(related),
                    visible(LegacyDocumentMapping, self.organization_id),
                )
            )
        )
        if not law_ids:
            return []
        watches = session.scalars(
            select(DocumentWatch)
            .join(Law, Law.id == DocumentWatch.law_id)
            .where(
                DocumentWatch.law_id.in_(law_ids),
                DocumentWatch.organization_id == self.organization_id,
                visible(Law, self.organization_id),
            )
        ).all()
        return [
            {
                "law_id": watch.law_id,
                "watch_id": watch.id,
                "name": watch.display_name,
                "active": watch.active,
                "timeline_url": f"/laws/{watch.law_id}",
            }
            for watch in watches
        ]

    def _event_statement(self, filters, custom_start, custom_end):
        # Scalar projection: a list must never hydrate event evidence or work metadata.
        read = (
            select(RegulatoryEventUserState.id)
            .where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal_key,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id,
                RegulatoryEventUserState.state == "read",
            )
            .correlate(RegulatoryEvent)
            .exists()
        )
        related = (
            select(RegulatoryRelation.id)
            .where(
                or_(
                    and_(
                        RegulatoryRelation.subject_work_id == RegulatoryWork.id,
                        RegulatoryRelation.object_work_id == LegacyDocumentMapping.work_id,
                    ),
                    and_(
                        RegulatoryRelation.object_work_id == RegulatoryWork.id,
                        RegulatoryRelation.subject_work_id == LegacyDocumentMapping.work_id,
                    ),
                ),
            )
            .correlate(RegulatoryWork, LegacyDocumentMapping)
            .exists()
        )
        watched = (
            select(DocumentWatch.id)
            .join(Law, Law.id == DocumentWatch.law_id)
            .join(LegacyDocumentMapping, LegacyDocumentMapping.law_id == Law.id)
            .where(
                DocumentWatch.organization_id == self.organization_id,
                visible(Law, self.organization_id),
                visible(LegacyDocumentMapping, self.organization_id),
                or_(LegacyDocumentMapping.work_id == RegulatoryWork.id, related),
            )
            .correlate(RegulatoryWork)
            .exists()
        )
        lifecycle = func.coalesce(func.nullif(RegulatoryWork.lifecycle_status, ""), "unknown")
        statement = (
            select(
                RegulatoryEvent.id.label("event_id"),
                RegulatoryEvent.work_id,
                RegulatoryEvent.document_version_id,
                RegulatoryEvent.event_type,
                RegulatoryEvent.detected_at,
                RegulatoryEvent.connector,
                RegulatoryEvent.connector_health,
                RegulatoryEvent.impact,
                RegulatoryEvent.analysis_state,
                RegulatoryEvent.provenance_method,
                RegulatoryEvent.source_url,
                RegulatoryWork.title,
                RegulatoryWork.authority,
                RegulatoryWork.kind,
                RegulatoryWork.stable_official_url,
                lifecycle.label("lifecycle"),
                read.label("read"),
                watched.label("watched"),
            )
            .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
            .where(visible(RegulatoryWork, self.organization_id))
        )
        for value, column in (
            (filters.authority, RegulatoryWork.authority),
            (filters.connector, RegulatoryEvent.connector),
            (filters.kind, RegulatoryWork.kind),
            (filters.lifecycle, lifecycle),
            (filters.impact, RegulatoryEvent.impact),
            (filters.health, RegulatoryEvent.connector_health),
        ):
            if value:
                statement = statement.where(column == value)
        if filters.read:
            statement = statement.where(read if filters.read == "read" else ~read)
        if filters.watched:
            statement = statement.where(watched if filters.watched == "watched" else ~watched)
        if filters.language:
            statement = statement.where(
                select(RegulatoryExpression.id)
                .where(
                    RegulatoryExpression.work_id == RegulatoryWork.id,
                    RegulatoryExpression.language == filters.language,
                )
                .correlate(RegulatoryWork)
                .exists()
            )
        if custom_start:
            statement = statement.where(
                RegulatoryEvent.detected_at
                >= datetime.combine(custom_start, time.min, ZURICH).astimezone(UTC)
            )
        if custom_end and custom_end < date.max:
            statement = statement.where(
                RegulatoryEvent.detected_at
                < datetime.combine(custom_end + timedelta(days=1), time.min, ZURICH).astimezone(UTC)
            )
        return statement.order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())

    def _event_rows(self, session: Session, filters: RegistryFilters, custom_start, custom_end) -> list[dict]:
        return self._candidate_page(
            session,
            self._event_statement(filters, custom_start, custom_end),
            RegulatoryEvent.id,
            RegulatoryEvent.detected_at,
            "event",
            filters,
        )

    def _candidate_page(
        self, session: Session, statement, id_column, detected, prefix: str, filters: RegistryFilters
    ) -> list[dict]:
        """Bound materialization while retaining complete Unicode literal search."""
        cursor = None
        if filters.cursor:
            at, row_id = _decode_cursor(filters.cursor)
            if not row_id.startswith(prefix + ":"):
                raise DomainError("The registry cursor is invalid.", 422, "invalid_registry_cursor")
            cursor = (at, row_id.removeprefix(prefix + ":"))
        rows = []
        id_key = prefix + "_id"
        while len(rows) <= filters.limit:
            query = statement
            if cursor:
                query = query.where(
                    or_(detected < cursor[0], and_(detected == cursor[0], id_column < cursor[1]))
                )
            size = 100 if filters.query else min(100, filters.limit + 1 - len(rows))
            batch = session.execute(query.limit(size)).mappings().all()
            if not batch:
                break
            work_ids = list({row["work_id"] for row in batch if row["work_id"]})
            languages = {}
            if work_ids:
                for work_id, language in session.execute(
                    select(RegulatoryExpression.work_id, RegulatoryExpression.language)
                    .where(RegulatoryExpression.work_id.in_(work_ids))
                    .distinct()
                ):
                    languages.setdefault(work_id, []).append(language)
            for item in batch:
                row = dict(item)
                row.update(
                    id=f"{prefix}:{item[id_key]}",
                    detected_at=_iso(item["detected_at"]),
                    languages=sorted(languages.get(item["work_id"], [])),
                )
                if prefix == "watch":
                    row.update(record_type="monitored", watched=True, languages=row["languages"] or ["und"])
                else:
                    row.update(record_type="event", title=item["title"] or "Untitled regulatory document")
                if self._matches(row, filters):
                    rows.append(row)
                    if len(rows) > filters.limit:
                        break
            cursor = (aware_utc(batch[-1]["detected_at"]), batch[-1][id_key])
            if len(batch) < size:
                break
        return rows

    def _event_details(self, session: Session, rows: list[dict]):
        # Hydrate descriptive links/dates only for returned rows, never the lookahead.
        linked_by_work = {}
        expressions_by_work = {}
        for row in rows:
            work_id = row["work_id"]
            if work_id not in linked_by_work:
                linked_by_work[work_id] = self._linked_laws(session, work_id)
                expressions_by_work[work_id] = list(
                    session.scalars(
                        select(RegulatoryExpression.id).where(RegulatoryExpression.work_id == work_id)
                    )
                )
            linked = linked_by_work[work_id]
            entity_ids = [work_id, row["event_id"], *expressions_by_work[work_id]]
            version_id = row.pop("document_version_id")
            if version_id:
                entity_ids.append(version_id)
            row.update(
                law_id=linked[0]["law_id"] if linked else None,
                why=f"{row['event_type'].replace('_', ' ').title()} reported by {row.pop('provenance_method').replace('_', ' ')}.",
                linked_laws=linked,
                official_dates=self._dates(session, entity_ids),
                source_url=row["source_url"] or row.pop("stable_official_url"),
                evidence_url=None,
                timeline_url=linked[0]["timeline_url"] if linked else None,
                comparison_url=None,
            )
            row.pop("stable_official_url", None)

    def _monitored_statement(self, filters: RegistryFilters, custom_start, custom_end):
        latest_event = (
            select(RegulatoryEvent.id)
            .where(RegulatoryEvent.work_id == RegulatoryWork.id)
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
            .correlate(RegulatoryWork)
            .limit(1)
            .scalar_subquery()
        )
        read = (
            select(RegulatoryEventUserState.id)
            .where(
                RegulatoryEventUserState.organization_id == self.organization_id,
                RegulatoryEventUserState.principal_key == self.principal_key,
                RegulatoryEventUserState.event_id == RegulatoryEvent.id,
                RegulatoryEventUserState.state == "read",
            )
            .correlate(RegulatoryEvent)
            .exists()
        )
        detected = func.coalesce(
            RegulatoryEvent.detected_at, DocumentWatch.last_checked, DocumentWatch.created_at
        )
        authority = case((RegulatoryWork.id.is_not(None), RegulatoryWork.authority), else_=Law.provider)
        connector = case((RegulatoryEvent.id.is_not(None), RegulatoryEvent.connector), else_=Law.provider)
        kind = func.coalesce(RegulatoryWork.kind, "unclassified_document")
        lifecycle = func.coalesce(func.nullif(RegulatoryWork.lifecycle_status, ""), "unknown")
        health = func.coalesce(RegulatoryEvent.connector_health, "unknown")
        impact = func.coalesce(RegulatoryEvent.impact, "unknown")
        statement = (
            select(
                DocumentWatch.id.label("watch_id"),
                DocumentWatch.display_name.label("title"),
                DocumentWatch.active,
                Law.id.label("law_id"),
                Law.url.label("law_url"),
                Law.current_version_id,
                RegulatoryWork.id.label("work_id"),
                RegulatoryEvent.id.label("event_id"),
                func.coalesce(RegulatoryEvent.event_type, "monitoring_started").label("event_type"),
                detected.label("detected_at"),
                authority.label("authority"),
                connector.label("connector"),
                kind.label("kind"),
                lifecycle.label("lifecycle"),
                health.label("connector_health"),
                impact.label("impact"),
                read.label("read"),
                RegulatoryEvent.source_url,
                func.coalesce(RegulatoryEvent.analysis_state, "not_required").label("analysis_state"),
            )
            .select_from(DocumentWatch)
            .join(Law, and_(Law.id == DocumentWatch.law_id, visible(Law, self.organization_id)))
            .outerjoin(
                LegacyDocumentMapping,
                and_(
                    LegacyDocumentMapping.law_id == Law.id,
                    visible(LegacyDocumentMapping, self.organization_id),
                ),
            )
            .outerjoin(
                RegulatoryWork,
                and_(
                    RegulatoryWork.id == LegacyDocumentMapping.work_id,
                    visible(RegulatoryWork, self.organization_id),
                ),
            )
            .outerjoin(RegulatoryEvent, RegulatoryEvent.id == latest_event)
            .where(DocumentWatch.organization_id == self.organization_id)
        )
        for value, column in (
            (filters.authority, authority),
            (filters.connector, connector),
            (filters.kind, kind),
            (filters.lifecycle, lifecycle),
            (filters.impact, impact),
            (filters.health, health),
        ):
            if value:
                statement = statement.where(column == value)
        if filters.read:
            statement = statement.where(read if filters.read == "read" else ~read)
        if filters.watched and filters.watched != "watched":
            statement = statement.where(False)
        if filters.language:
            expression = (
                select(RegulatoryExpression.id)
                .where(RegulatoryExpression.work_id == RegulatoryWork.id)
                .correlate(RegulatoryWork)
            )
            language = expression.where(RegulatoryExpression.language == filters.language).exists()
            if filters.language == "und":
                language = or_(language, ~expression.exists())
            statement = statement.where(language)
        if custom_start:
            statement = statement.where(
                detected >= datetime.combine(custom_start, time.min, ZURICH).astimezone(UTC)
            )
        if custom_end and custom_end < date.max:
            statement = statement.where(
                detected < datetime.combine(custom_end + timedelta(days=1), time.min, ZURICH).astimezone(UTC)
            )
        return statement.order_by(detected.desc(), DocumentWatch.id.desc()), detected

    def _monitored_rows(
        self, session: Session, filters: RegistryFilters, custom_start, custom_end
    ) -> list[dict]:
        statement, detected = self._monitored_statement(filters, custom_start, custom_end)
        return self._candidate_page(session, statement, DocumentWatch.id, detected, "watch", filters)

    def _monitored_details(self, session: Session, rows: list[dict]):
        if not rows:
            return
        law_ids = [row["law_id"] for row in rows]
        ranked = (
            select(
                Comparison.id,
                Comparison.law_id,
                func.row_number()
                .over(
                    partition_by=Comparison.law_id,
                    order_by=(Comparison.created_at.desc(), Comparison.id.desc()),
                )
                .label("rank"),
            )
            .where(Comparison.law_id.in_(law_ids), visible(Comparison, self.organization_id))
            .subquery()
        )
        comparisons = dict(
            session.execute(select(ranked.c.law_id, ranked.c.id).where(ranked.c.rank == 1)).all()
        )
        expressions = {}
        work_ids = list({row["work_id"] for row in rows if row["work_id"]})
        if work_ids:
            for work_id, expression_id in session.execute(
                select(RegulatoryExpression.work_id, RegulatoryExpression.id).where(
                    RegulatoryExpression.work_id.in_(work_ids)
                )
            ):
                expressions.setdefault(work_id, []).append(expression_id)
        entity_ids = set(work_ids)
        entity_ids.update(row["event_id"] for row in rows if row["event_id"])
        entity_ids.update(expression_id for ids in expressions.values() for expression_id in ids)
        dates = {}
        if entity_ids:
            for item in session.execute(
                select(
                    RegulatoryDate.entity_id,
                    RegulatoryDate.kind,
                    RegulatoryDate.date_value,
                    RegulatoryDate.precision,
                    RegulatoryDate.provenance,
                    RegulatoryDate.source_url,
                ).where(RegulatoryDate.entity_id.in_(entity_ids))
            ):
                dates.setdefault(item.entity_id, []).append(
                    (
                        item.kind,
                        dict(
                            value=item.date_value,
                            precision=item.precision,
                            provenance=item.provenance,
                            source_url=item.source_url,
                        ),
                    )
                )
        for row in rows:
            work_id, law_id = row["work_id"], row["law_id"]
            entity_ids = [work_id, *expressions.get(work_id, [])] if work_id else []
            if row["event_id"]:
                entity_ids.append(row["event_id"])
            official_dates = {}
            for entity_id in dict.fromkeys(entity_ids):
                for kind, value in dates.get(entity_id, []):
                    official_dates.setdefault(kind, []).append(value)
            version_id, comparison_id = row.pop("current_version_id"), comparisons.get(law_id)
            row.update(
                why="Latest saved activity for a document in this organization's watchlist.",
                linked_laws=[
                    dict(
                        law_id=law_id,
                        watch_id=row.pop("watch_id"),
                        name=row["title"],
                        active=row.pop("active"),
                        timeline_url=f"/laws/{law_id}",
                    )
                ],
                official_dates=official_dates,
                source_url=row["source_url"] or row.pop("law_url"),
                evidence_url=f"/evidence/{version_id}" if version_id else None,
                timeline_url=f"/laws/{law_id}",
                comparison_url=f"/compare/{comparison_id}" if comparison_id else None,
            )
            row.pop("law_url", None)

    @staticmethod
    def _matches(row: dict, filters: RegistryFilters) -> bool:
        query = search_text(filters.query)
        haystack = search_text(
            " ".join(
                [
                    row.get("title") or "",
                    row.get("authority") or "",
                    row.get("event_type") or "",
                    *(row.get("languages") or []),
                ]
            )
        )
        return (
            (not query or query in haystack)
            and (not filters.authority or row["authority"] == filters.authority)
            and (not filters.connector or row["connector"] == filters.connector)
            and (not filters.kind or row["kind"] == filters.kind)
            and (not filters.language or filters.language in row["languages"])
            and (not filters.lifecycle or row["lifecycle"] == filters.lifecycle)
            and (not filters.impact or row["impact"] == filters.impact)
            and (not filters.health or row["connector_health"] == filters.health)
            and (not filters.watched or (filters.watched == "watched") == bool(row["watched"]))
            and (not filters.read or (filters.read == "read") == bool(row["read"]))
        )

    def page(self, session: Session, filters: RegistryFilters) -> dict:
        if filters.view not in {"monitored", "events"}:
            raise DomainError("Unknown registry view.", 422, "invalid_registry_view")
        custom_start = _parse_day(filters.start, "start")
        custom_end = _parse_day(filters.end, "end")
        if custom_start and custom_end and custom_start > custom_end:
            raise DomainError("The start date must precede the end date.", 422, "invalid_registry_date")
        rows = (
            self._monitored_rows(session, filters, custom_start, custom_end)
            if filters.view == "monitored"
            else self._event_rows(session, filters, custom_start, custom_end)
        )
        rows = [row for row in rows if self._matches(row, filters)]
        rows = [
            row
            for row in rows
            if detected_group(
                datetime.fromisoformat(row["detected_at"]),
                custom_start=custom_start,
                custom_end=custom_end,
            )
            != "Outside range"
        ]
        rows.sort(key=lambda row: (datetime.fromisoformat(row["detected_at"]), row["id"]), reverse=True)
        if filters.cursor:
            cursor_time, cursor_id = _decode_cursor(filters.cursor)
            rows = [
                row
                for row in rows
                if (datetime.fromisoformat(row["detected_at"]), row["id"]) < (cursor_time, cursor_id)
            ]
        selected = rows[: filters.limit]
        if filters.view == "monitored":
            self._monitored_details(session, selected)
        if filters.view == "events":
            self._event_details(session, selected)
            # Only resolve links for the visible page, without loading version bodies.
            for start in range(0, len(selected), 100):
                batch = selected[start : start + 100]
                links = event_evidence_links(
                    session, self.organization_id, [row["event_id"] for row in batch]
                )
                for row in batch:
                    row["evidence_url"] = links.get(row["event_id"])
        for row in selected:
            row["group"] = detected_group(
                datetime.fromisoformat(row["detected_at"]),
                custom_start=custom_start,
                custom_end=custom_end,
            )
        groups = []
        for name in ("Custom range", "Today", "Yesterday", "Last 7 days", "Last 30 days", "Older"):
            items = [row for row in selected if row["group"] == name]
            if items:
                groups.append({"name": name, "items": items})
        return {
            "view": filters.view,
            "groups": groups,
            "items": selected,
            "next_cursor": _encode_cursor(selected[-1]) if len(rows) > filters.limit else None,
            "count": len(selected),
        }

    def mark_read(self, session: Session, event_id: str, read: bool) -> dict:
        event = session.get(RegulatoryEvent, event_id)
        if not event:
            raise DomainError("The requested event was not found.", 404, "not_found")
        state = session.scalar(
            select(RegulatoryEventUserState).where(
                RegulatoryEventUserState.event_id == event_id,
                RegulatoryEventUserState.principal_key == self.principal_key,
            )
        )
        if not state:
            state = RegulatoryEventUserState(
                event_id=event_id,
                user_id=self.user_id,
                principal_key=self.principal_key,
            )
            session.add(state)
        state.state = "read" if read else "unread"
        state.updated_at = datetime.now(UTC)
        session.commit()
        return {"event_id": event_id, "read": read, "read_at": _iso(state.updated_at) if read else None}

    def timeline(self, session: Session, law_id: str) -> dict:
        law = session.get(Law, law_id)
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        if not law or not watch:
            raise DomainError("The requested record was not found.", 404, "not_found")
        mapping = session.scalar(select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law_id))
        work = session.get(RegulatoryWork, mapping.work_id) if mapping and mapping.work_id else None
        identifiers = (
            session.scalars(select(RegulatoryIdentifier).where(RegulatoryIdentifier.work_id == work.id)).all()
            if work
            else []
        )
        expressions = (
            session.scalars(select(RegulatoryExpression).where(RegulatoryExpression.work_id == work.id)).all()
            if work
            else []
        )
        normalized_versions = (
            session.scalars(
                select(RegulatoryDocumentVersion).where(
                    RegulatoryDocumentVersion.expression_id.in_([item.id for item in expressions])
                )
            ).all()
            if expressions
            else []
        )
        events = (
            session.scalars(
                select(RegulatoryEvent)
                .where(RegulatoryEvent.work_id == work.id)
                .order_by(RegulatoryEvent.detected_at.desc())
            ).all()
            if work
            else []
        )
        relations = (
            session.scalars(
                select(RegulatoryRelation)
                .where(
                    or_(
                        RegulatoryRelation.subject_work_id == work.id,
                        RegulatoryRelation.object_work_id == work.id,
                    )
                )
                .order_by(RegulatoryRelation.created_at.desc())
            ).all()
            if work
            else []
        )
        versions = session.scalars(
            select(Version).where(Version.law_id == law_id).order_by(Version.created_at.desc())
        ).all()
        comparisons = session.scalars(
            select(Comparison).where(Comparison.law_id == law_id).order_by(Comparison.created_at.desc())
        ).all()
        observations = session.scalars(
            select(Observation).where(Observation.law_id == law_id).order_by(Observation.created_at.desc())
        ).all()
        relation_rows = []
        for item in relations:
            outgoing = item.subject_work_id == (work.id if work else None)
            other_work_id = item.object_work_id if outgoing else item.subject_work_id
            other_work = session.get(RegulatoryWork, other_work_id)
            other_mapping = session.scalar(
                select(LegacyDocumentMapping).where(LegacyDocumentMapping.work_id == other_work_id)
            )
            other_law = session.get(Law, other_mapping.law_id) if other_mapping else None
            relation_rows.append(
                {
                    "id": item.id,
                    "direction": "outgoing" if outgoing else "incoming",
                    "type": item.relation_type,
                    "state": item.state,
                    "other_work_id": other_work_id,
                    "other_title": other_work.title if other_work else "Unknown regulatory work",
                    "other_law_id": other_law.id if other_law else None,
                    "other_timeline_url": f"/laws/{other_law.id}" if other_law else None,
                    "provenance": item.provenance_method,
                    "reciprocal_label": (
                        "successor"
                        if item.relation_type == "replaces" and not outgoing
                        else "predecessor"
                        if item.relation_type == "replaces"
                        else None
                    ),
                }
            )
        timeline = [
            {
                "id": f"event:{item.id}",
                "type": "event",
                "at": _iso(item.detected_at),
                "label": item.event_type.replace("_", " ").title(),
                "detail": item.provenance_method.replace("_", " "),
                "url": item.source_url,
            }
            for item in events
        ]
        timeline += [
            {
                "id": f"version:{item.id}",
                "type": "version",
                "at": _iso(item.created_at),
                "label": "Immutable version saved",
                "detail": item.declared_date or item.origin,
                "url": f"/evidence/{item.id}",
            }
            for item in versions
        ]
        timeline += [
            {
                "id": f"comparison:{item.id}",
                "type": "comparison",
                "at": _iso(item.created_at),
                "label": "Comparison created",
                "detail": item.mode,
                "url": f"/compare/{item.id}",
            }
            for item in comparisons
        ]
        timeline.sort(key=lambda item: (item["at"] or "", item["id"]), reverse=True)
        return {
            "monitoring": {
                "active": watch.active,
                "last_checked": _iso(watch.last_checked),
                "last_result": watch.last_result,
            },
            "work": {
                "id": work.id if work else None,
                "kind": work.kind if work else "unclassified_document",
                "authority": work.authority if work else law.provider,
                "lifecycle": (work.lifecycle_status if work else None) or "unknown",
                "stable_official_url": work.stable_official_url if work else law.url,
            },
            "identifiers": [
                {"scheme": item.scheme, "value": item.value, "source_url": item.source_url}
                for item in identifiers
            ],
            "expressions": [
                {"id": item.id, "language": item.language, "title": item.title, "url": item.official_url}
                for item in expressions
            ],
            "normalized_versions": len(normalized_versions),
            "relations": relation_rows,
            "source_provenance": [
                {"origin": item.origin, "source_url": item.source_url, "observed_at": _iso(item.created_at)}
                for item in observations[:100]
            ],
            "timeline": timeline,
        }
