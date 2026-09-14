"""Selected private native evidence; no raw provider feed or original download.

These are the same normalized, permission-checked projections used by native
history readers. The download service must additionally bind identity, selection
and content and recheck them when the browser requests the file.
"""

import hashlib
import json
from copy import deepcopy

from sqlalchemy import select

from .monitoring_evidence_ask import Record, native
from .monitoring_evidence_versions import fail
from .monitoring_subjects import _actor

DOMAINS = {"pollen", "air", "river", "warnings", "commute", "traffic"}


def _commute(session, settings, user_id, record, now):
    from .commute_events import owned_development
    from .commute_today import evidence

    _actor(session, user_id)
    if not settings.commute_watch_enabled:
        fail("monitoring_evidence_not_found", 404)
    monitor, row = owned_development(session, user_id, record.item_id, now=now)
    if monitor.id != record.monitor_id:
        fail("monitoring_evidence_not_found", 404)
    # The native Today reader also reads the latest version for current labels.
    # A historical download has no dependency on those unrelated newer bytes.
    snapshot = evidence(session, row, record.sequence or row.sequence)
    return {"snapshot": snapshot,
        "event": {name: getattr(row, name) for name in ("configuration_revision", "reviewed_sequence", "muted", "version")},
        "newer_available": snapshot["sequence"] < row.sequence,
        "current_configuration": row.configuration_revision == monitor.revision}


def configuration(session, domain, monitor_id, organization, revision):
    if domain == "pollen":
        from .models import MonitoringSubjectRevision as Revision
        from .monitoring_subjects import _configuration
        row = session.scalar(select(Revision).where(Revision.subject_id == monitor_id,
            Revision.organization_id == organization, Revision.revision == revision))
        if row is None:
            fail("monitoring_export_configuration_unavailable", 503)
        value, digest = _configuration(row.configuration_json)
        if digest != row.configuration_hash:
            fail("monitoring_export_configuration_unavailable", 503)
        return {"revision": revision, "sha256": digest, "value": value, "retained_hash": True}
    if domain == "air":
        from .air_contracts import AirConfiguration as Contract
        from .air_models import AirRevision as Revision
    elif domain == "river":
        from .river_contracts import RiverConfiguration as Contract
        from .river_models import RiverRevision as Revision
    elif domain == "warnings":
        from .hazard_contracts import HazardConfiguration as Contract
        from .hazard_models import HazardConfigurationRevision as Revision
    elif domain == "commute":
        from .commute_contracts import CommuteConfiguration as Contract
        from .commute_models import CommuteConfigurationRevision as Revision
    else:
        from .road_contracts import RoadConfiguration as Contract
        from .road_models import RoadConfigurationRevision as Revision
    row = session.scalar(select(Revision).where(Revision.monitor_id == monitor_id,
        Revision.organization_id == organization, Revision.revision == revision))
    if row is None:
        fail("monitoring_export_configuration_unavailable", 503)
    try:
        checked = Contract.model_validate(row.configuration)
        retained = getattr(row, "configuration_hash", None)
        if retained and checked.fingerprint() != retained:
            fail("monitoring_export_configuration_unavailable", 503)
    except ValueError:
        fail("monitoring_export_configuration_unavailable", 503)
    # Air/River did not store a configuration digest. Do not present a newly
    # calculated download hash as historic integrity evidence from those sources.
    value = deepcopy(row.configuration)
    digest = retained or hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return {"revision": revision, "sha256": digest, "value": value, "retained_hash": retained is not None}


def selected(session, settings, user_id, record: Record, *, now):
    if record.domain not in DOMAINS:
        fail("monitoring_export_domain_invalid", 422)
    if record.sequence is not None and (type(record.sequence) is not int or not 1 <= record.sequence <= 10000):
        fail("monitoring_export_sequence_invalid", 422)
    organization = session.info.get("organization_id")
    # Pin the current hazard revision before reading. A stale live channel must
    # not deny still-permitted historical evidence merely because it is not fresh.
    if record.domain == "warnings":
        from .hazard_events import _owned_development
        monitor, development = _owned_development(session, user_id, record.monitor_id, record.item_id)
        record = Record(record.domain, record.monitor_id, record.item_id, record.sequence or development.revision)
    if record.domain == "commute":
        view = _commute(session, settings, user_id, record, now)
    else:
        view, _ = native(session, settings, user_id, record, now=now)
    previous = None
    review = {}
    if record.domain == "pollen":
        value = deepcopy(view["entry"])
        review = value.pop("review", None)
        revision, sequence = value["configuration_revision"], value["sequence"]
    elif record.domain in {"air", "river"}:
        value = deepcopy(view["event"])
        review = {"decision": value.pop("decision"), "version": value.pop("review_version")}
        revision, sequence = value["revision"], value["sequence"]
    elif record.domain == "warnings":
        value = {name: deepcopy(view[name]) for name in ("revision", "material_sequence", "state", "decision", "source", "proof")}
        review = {name: view[name] for name in ("reviewed", "dismissed", "needs_review", "muted")}
        revision, sequence = development.configuration_revision, record.sequence
        if sequence > 1:
            old, _ = native(session, settings, user_id,
                Record(record.domain, record.monitor_id, record.item_id, sequence - 1), now=now)
            previous = {name: deepcopy(old[name]) for name in value}
        view = {**view, "newer_available": sequence < development.revision,
            "current_configuration": revision == monitor.revision}
    else:
        value = deepcopy(view["snapshot"])
        revision, sequence = view["event"]["configuration_revision"], value["sequence"]
        review = {name: view["event"].get(name) for name in ("reviewed_sequence", "muted", "version")}
        if record.domain == "traffic":
            previous = deepcopy(view["previous"])
            if previous and previous.get("availability") != "available":
                fail()
            if sequence > 1 and previous is None:
                fail()
        elif sequence > 1:
            old = _commute(session, settings, user_id,
                Record(record.domain, record.monitor_id, record.item_id, sequence - 1), now)
            previous = deepcopy(old["snapshot"])
    return {"selected_revision_id": value.get("id", str(sequence)), "sequence": sequence,
        "profile_revision": revision, "configuration": configuration(session, record.domain, record.monitor_id,
            organization, revision), "native_record": value, "previous_record": previous,
        "private_review": review, "newer_available": bool(view.get("newer_available")),
        "current_configuration": view.get("current_configuration"), "raw_provider_payload_included": False}
