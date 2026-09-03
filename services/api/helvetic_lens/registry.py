"""Saved-data registry read model and Europe/Zurich time grouping."""

from __future__ import annotations

import base64
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import DomainError
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
        return datetime.fromisoformat(timestamp), str(item_id)
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

    def _states(self, session: Session) -> dict[str, RegulatoryEventUserState]:
        return {
            item.event_id: item
            for item in session.scalars(
                select(RegulatoryEventUserState).where(
                    RegulatoryEventUserState.principal_key == self.principal_key
                )
            )
        }

    @staticmethod
    def _dates(session: Session, entity_ids: list[str]) -> dict[str, list[dict]]:
        if not entity_ids:
            return {}
        result: dict[str, list[dict]] = {}
        for item in session.scalars(select(RegulatoryDate).where(RegulatoryDate.entity_id.in_(entity_ids))):
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
        for relation in session.scalars(
            select(RegulatoryRelation).where(
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
                select(LegacyDocumentMapping.law_id).where(LegacyDocumentMapping.work_id.in_(related))
            )
        )
        if not law_ids:
            return []
        watches = session.scalars(select(DocumentWatch).where(DocumentWatch.law_id.in_(law_ids))).all()
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

    def _event_rows(self, session: Session) -> list[dict]:
        states = self._states(session)
        rows = []
        for event, work in session.execute(
            select(RegulatoryEvent, RegulatoryWork).join(
                RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id
            )
        ):
            expressions = session.scalars(
                select(RegulatoryExpression).where(RegulatoryExpression.work_id == work.id)
            ).all()
            entity_ids = [work.id, event.id, *(item.id for item in expressions)]
            if event.document_version_id:
                entity_ids.append(event.document_version_id)
            dates = self._dates(session, entity_ids)
            linked = self._linked_laws(session, work.id)
            state = states.get(event.id)
            evidence_url = None
            if event.document_version_id:
                version = session.get(RegulatoryDocumentVersion, event.document_version_id)
                if version and version.legacy_version_id:
                    evidence_url = f"/evidence/{version.legacy_version_id}"
            rows.append(
                {
                    "id": f"event:{event.id}",
                    "record_type": "event",
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "detected_at": _iso(event.detected_at),
                    "work_id": work.id,
                    "law_id": linked[0]["law_id"] if linked else None,
                    "title": work.title or "Untitled regulatory document",
                    "authority": work.authority,
                    "connector": event.connector,
                    "connector_health": event.connector_health,
                    "kind": work.kind,
                    "languages": sorted({item.language for item in expressions}),
                    "lifecycle": work.lifecycle_status or "unknown",
                    "impact": event.impact,
                    "analysis_state": event.analysis_state,
                    "read": bool(state and state.state == "read"),
                    "watched": bool(linked),
                    "why": f"{event.event_type.replace('_', ' ').title()} reported by {event.provenance_method.replace('_', ' ')}.",
                    "linked_laws": linked,
                    "official_dates": dates,
                    "source_url": event.source_url or work.stable_official_url,
                    "evidence_url": evidence_url,
                    "timeline_url": linked[0]["timeline_url"] if linked else None,
                    "comparison_url": None,
                }
            )
        return rows

    def _monitored_rows(self, session: Session) -> list[dict]:
        rows = []
        for watch in session.scalars(select(DocumentWatch)):
            law = session.get(Law, watch.law_id)
            if not law:
                continue
            mapping = session.scalar(
                select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law.id)
            )
            work = session.get(RegulatoryWork, mapping.work_id) if mapping and mapping.work_id else None
            event = (
                session.scalar(
                    select(RegulatoryEvent)
                    .where(RegulatoryEvent.work_id == work.id)
                    .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
                    .limit(1)
                )
                if work
                else None
            )
            expressions = (
                session.scalars(
                    select(RegulatoryExpression).where(RegulatoryExpression.work_id == work.id)
                ).all()
                if work
                else []
            )
            detected = event.detected_at if event else watch.last_checked or watch.created_at
            comparison = session.scalar(
                select(Comparison)
                .where(Comparison.law_id == law.id)
                .order_by(Comparison.created_at.desc())
                .limit(1)
            )
            state = self._states(session).get(event.id) if event else None
            entity_ids = [work.id, *(item.id for item in expressions)] if work else []
            if event:
                entity_ids.append(event.id)
            rows.append(
                {
                    "id": f"watch:{watch.id}",
                    "record_type": "monitored",
                    "event_id": event.id if event else None,
                    "event_type": event.event_type if event else "monitoring_started",
                    "detected_at": _iso(detected),
                    "work_id": work.id if work else None,
                    "law_id": law.id,
                    "title": watch.display_name,
                    "authority": work.authority if work else law.provider,
                    "connector": event.connector if event else law.provider,
                    "connector_health": event.connector_health if event else "unknown",
                    "kind": work.kind if work else "unclassified_document",
                    "languages": sorted({item.language for item in expressions}) or ["und"],
                    "lifecycle": (work.lifecycle_status if work else None) or "unknown",
                    "impact": event.impact if event else "unknown",
                    "analysis_state": event.analysis_state if event else "not_required",
                    "read": bool(state and state.state == "read"),
                    "watched": True,
                    "why": "Latest saved activity for a document in this organization's watchlist.",
                    "linked_laws": [
                        {
                            "law_id": law.id,
                            "watch_id": watch.id,
                            "name": watch.display_name,
                            "active": watch.active,
                            "timeline_url": f"/laws/{law.id}",
                        }
                    ],
                    "official_dates": self._dates(session, entity_ids),
                    "source_url": (event.source_url if event else None) or law.url,
                    "evidence_url": f"/evidence/{law.current_version_id}" if law.current_version_id else None,
                    "timeline_url": f"/laws/{law.id}",
                    "comparison_url": f"/compare/{comparison.id}" if comparison else None,
                }
            )
        return rows

    @staticmethod
    def _matches(row: dict, filters: RegistryFilters) -> bool:
        query = search_text(filters.query)
        haystack = search_text(" ".join(
            [
                row.get("title") or "",
                row.get("authority") or "",
                row.get("event_type") or "",
                *(row.get("languages") or []),
            ]
        ))
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
        rows = self._monitored_rows(session) if filters.view == "monitored" else self._event_rows(session)
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
                select(LegacyDocumentMapping).where(
                    LegacyDocumentMapping.work_id == other_work_id
                )
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
