"""Reviewed public Swiss channel defaults; never renews an operator decision.

The owner authorized activation of public Monitoring sources. The first worker
records the actual reviewed redistribution contract, not a synthetic API grant.
Explicit configured permissions win. Existing selections, unselected prior grants
and revoked/expired records are preserved for explicit operator resolution.
"""

from datetime import UTC, datetime
from typing import get_args

from sqlalchemy import select

from .config import DomainError
from .hazard_cap import digest
from .hazard_contracts import Canton
from .hazard_meteoalarm import ATTRIBUTION, FEED_URL, POLL_SECONDS, TERMS_URL
from .hazard_source_models import HazardSourcePermission, HazardSourceSelection
from .hazard_sources import (
    HazardCoverage,
    HazardRule,
    HazardSourcePolicy,
    activate_permission,
    record_permission,
)
from .monitoring_subjects import _savepoint

SOURCE_KEY = "meteoswiss-meteoalarm"
REVIEWED_AT = datetime(2026, 9, 14, tzinfo=UTC)
VALID_UNTIL = datetime(2027, 1, 1, tzinfo=UTC)
TERMS_SHA256 = "7b317929f32b5f7903b574e6c54be822bfe0e30677b3f6155a55d522cc87957c"
SCOPE_REVIEW = {
    "reviewed_at": REVIEWED_AT.isoformat(),
    "provider": "Federal Office of Meteorology and Climatology MeteoSwiss",
    "provider_directory_sha256": "2486a23cf78007848d5aef477d3833a4b353fe756656f404cf8c76403fdd8b04",
    "redistribution_hub_sha256": "b84a5d1a50cd2c7824deb46c45e45d1b0b7a6ff66d72a20c75dddf55cf32af4e",
    "jurisdiction": "https://www.meteoswiss.admin.ch/about-us/legal-mandate.html",
    "types": "https://www.meteoswiss.admin.ch/weather/hazards/how-severe-weather-warnings-are-prepared.html",
    "channel": FEED_URL,
    "supported_selection": "storm: typed wind and thunderstorm warnings within Switzerland",
    "excluded": "No inferred snow/ice separation, flood, fire, civil protection or power-outage coverage",
}


def permission_id(session, settings):
    explicit = getattr(settings, "hazard_source_permission_id", "")
    if explicit:
        return explicit
    selected = session.get(HazardSourceSelection, SOURCE_KEY, populate_existing=True)
    return selected.permission_id if selected is not None else ""


def policy():
    cantons = get_args(Canton)
    return HazardSourcePolicy(source_key=SOURCE_KEY, protocol="meteoalarm-v2", endpoint=FEED_URL,
        sender="meteoalarm-switzerland-channel", attribution=ATTRIBUTION,
        reference=f"Public Information redistribution review 2026-09-14; {TERMS_URL}; CMS SHA256 {TERMS_SHA256}",
        accepted_at=REVIEWED_AT, valid_until=VALID_UNTIL, min_poll_seconds=POLL_SECONDS,
        max_age_seconds=300, raw_retention_seconds=7 * 86400, normalized_retention_seconds=31 * 86400,
        store_full_message=True, retain_minimal_audit=True, matching_allowed=True, display_allowed=True,
        notifications_allowed=True, private_decisions_allowed=True, covered_cantons=cantons,
        rules=(HazardRule(hazard="storm", value_name="awareness_type", value="1; Wind"),
               HazardRule(hazard="storm", value_name="awareness_type", value="3; Thunderstorm")),
        importance=(("Extreme", "alarm"), ("Severe", "warning"), ("Moderate", "warning"), ("Minor", "information")),
        coverage=(HazardCoverage(hazard="storm", cantons=cantons, evidence_reference=SCOPE_REVIEW["types"],
            evidence_sha256=digest(SCOPE_REVIEW), checked_at=REVIEWED_AT, valid_until=VALID_UNTIL),))


def initialize(database, settings, *, now):
    if (not settings.hazard_watch_enabled or not settings.hazard_source_enabled
            or settings.hazard_source_permission_id or not REVIEWED_AT <= now < VALID_UNTIL):
        return {"state": "unchanged"}
    with database.session() as session:
        if permission_id(session, settings):
            return {"state": "existing_selection"}
        seen = session.scalar(select(HazardSourcePermission.id).limit(1))
        if seen is not None:
            return {"state": "operator_selection_required"}
        try:
            with _savepoint(session):
                identifier = record_permission(session, policy=policy())
                activate_permission(session, identifier, expected_generation=0, now=now)
            session.commit()
            return {"state": "installed"}
        except DomainError as error:
            if error.code != "hazard_source_selection_conflict":
                raise
            session.rollback()
            return {"state": "selection_changed"}
