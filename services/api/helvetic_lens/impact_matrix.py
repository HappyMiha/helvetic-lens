"""Read-only business-area matrix assembled from saved Impact reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import analysis as ai
from . import matrix_selection
from .corpus_access import visible
from .models import Comparison, DocumentWatch, Law, Profile

IMPACTS = {"high", "medium", "low"}
IMPACT_ORDER = {"high": 3, "medium": 2, "low": 1}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def _area_key(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _text(value: object, limit: int = 600) -> str | None:
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit] or None


class ImpactMatrixReader:
    """Batch saved-history reads; the complete response still grows with watches."""

    def __init__(
        self,
        *,
        organization_id: str,
        profile_id: str,
        settings: Any,
        prompts: Any,
        output_locale: str,
        runtime_identity: dict | None = None,
    ):
        self.organization_id = organization_id
        self.profile_id = profile_id
        self.settings = settings
        self.prompts = prompts
        self.output_locale = output_locale
        self.runtime_identity = runtime_identity

    @staticmethod
    def _reason(result: dict) -> str | None:
        applicability = result.get("organization_applicability")
        return _text(
            (applicability or {}).get("explanation") if isinstance(applicability, dict) else None
        ) or _text(result.get("reason"))

    def _row(
        self,
        *,
        watch: DocumentWatch,
        law: Law,
        comparison: Comparison | None,
        profile: Profile,
        selection: tuple,
    ) -> dict:
        report_state, report, latest_attempt = selection
        result = report.result if report and isinstance(report.result, dict) else {}
        report_areas = {_area_key(area) for area in result.get("business_areas", []) if _area_key(area)}
        impact = result.get("impact") if result.get("impact") in IMPACTS else None
        reason = self._reason(result)
        cells = []
        for area in profile.business_areas:
            matched = _area_key(area) in report_areas
            if report_state == "current" and matched and impact:
                state, current_impact, previous_impact = "assessed", impact, None
            elif report_state == "stale":
                state, current_impact = "stale", None
                previous_impact = impact if matched else None
            elif report_state == "failed":
                state, current_impact, previous_impact = "failed", None, None
            elif report_state == "unanalysed":
                state, current_impact, previous_impact = "unanalysed", None, None
            else:
                state, current_impact, previous_impact = "unknown", None, None
            if report_state == "current" and (not matched or not impact):
                state = "unknown"
            cells.append(
                {
                    "area": area,
                    "state": state,
                    "impact": current_impact,
                    "previous_impact": previous_impact,
                    "reason": reason if matched and report_state in {"current", "stale"} else None,
                }
            )
        return {
            "law_id": law.id,
            "law_title": watch.display_name,
            "comparison_id": comparison.id if comparison else None,
            "comparison_url": f"/compare/{comparison.id}" if comparison else None,
            "comparison_created_at": _iso(comparison.created_at) if comparison else None,
            "report_state": report_state,
            "analysis_id": report.id if report and report.status == "succeeded" else None,
            "analysis_created_at": _iso(report.created_at) if report else None,
            "analysis_output_locale": (result.get("output_locale") or None),
            "latest_attempt_status": latest_attempt.status if latest_attempt else None,
            "headline": _text(result.get("headline") or result.get("summary"), 300),
            "overall_impact": impact if report_state == "current" else None,
            "previous_overall_impact": impact if report_state == "stale" else None,
            "cells": cells,
        }

    def page(self, session: Session) -> dict:
        profile = session.scalar(
            select(Profile).where(
                Profile.id == self.profile_id, Profile.organization_id == self.organization_id
            )
        )
        if profile is None:
            return {
                "output_locale": self.output_locale,
                "profile": {"revision": 0, "business_areas": []},
                "rows": [],
                "summary": {
                    "documents": 0,
                    "current_reports": 0,
                    "stale_reports": 0,
                    "failed_reports": 0,
                    "unanalysed_documents": 0,
                    "assessed_cells": 0,
                    "unknown_cells": 0,
                },
            }
        watches = list(
            session.scalars(
                select(DocumentWatch)
                .where(DocumentWatch.active.is_(True), DocumentWatch.organization_id == self.organization_id)
                .order_by(DocumentWatch.display_name, DocumentWatch.id)
            )
        )
        rows = []
        for offset in range(0, len(watches), matrix_selection.BATCH_SIZE):
            batch = watches[offset : offset + matrix_selection.BATCH_SIZE]
            law_ids = [watch.law_id for watch in batch]
            laws = {
                law.id: law
                for law in session.scalars(
                    select(Law).where(Law.id.in_(law_ids), visible(Law, self.organization_id))
                )
            }
            latest = matrix_selection.comparisons(session, self.organization_id, law_ids)
            keys = {
                item.id: ai.cache_key(
                    item,
                    profile,
                    self.settings,
                    self.prompts,
                    self.output_locale,
                    runtime_identity=self.runtime_identity,
                )
                for item in latest.values()
            }
            reports = matrix_selection.reports(session, self.organization_id, latest, keys)
            rows.extend(
                self._row(
                    watch=watch,
                    law=laws[watch.law_id],
                    comparison=latest.get(watch.law_id),
                    profile=profile,
                    selection=reports.get(latest[watch.law_id].id, ("unanalysed", None, None))
                    if watch.law_id in latest
                    else ("unanalysed", None, None),
                )
                for watch in batch
                if watch.law_id in laws
            )
        rows.sort(
            key=lambda row: (
                -IMPACT_ORDER.get(row["overall_impact"] or "", 0),
                row["law_title"].casefold(),
            )
        )
        cell_states = Counter(cell["state"] for row in rows for cell in row["cells"])
        report_states = Counter(row["report_state"] for row in rows)
        return {
            "output_locale": self.output_locale,
            "profile": {
                "revision": profile.revision,
                "business_areas": list(profile.business_areas),
            },
            "rows": rows,
            "summary": {
                "documents": len(rows),
                "current_reports": report_states["current"],
                "stale_reports": report_states["stale"],
                "failed_reports": report_states["failed"],
                "unanalysed_documents": report_states["unanalysed"],
                "assessed_cells": cell_states["assessed"],
                "unknown_cells": cell_states["unknown"],
            },
        }
