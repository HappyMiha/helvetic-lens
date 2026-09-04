from helvetic_lens.source_capabilities import (
    CAPABILITY_CATALOG_REVISION,
    CAPABILITY_SCHEMA_VERSION,
    SOURCE_CAPABILITIES,
)
from helvetic_lens.synchronization import DEFAULT_SCHEDULES


def test_capability_catalogue_covers_every_scheduled_stream_once():
    scheduled = {(item.connector, item.stream) for item in DEFAULT_SCHEDULES}
    catalogued = {(item.connector, item.stream) for item in SOURCE_CAPABILITIES}

    assert len(catalogued) == len(SOURCE_CAPABILITIES)
    assert catalogued == scheduled
    assert {item.authority for item in SOURCE_CAPABILITIES} >= {
        "fedlex",
        "swiss_parliament",
        "federal_supreme_court",
        "federal_criminal_court",
        "swiss_confederation",
        "finma",
    }


def test_capabilities_are_versioned_bounded_and_fail_closed():
    for item in SOURCE_CAPABILITIES:
        payload = item.serialize()
        assert payload["schema_version"] == CAPABILITY_SCHEMA_VERSION
        assert payload["catalogue_revision"] == CAPABILITY_CATALOG_REVISION
        assert payload["document_kinds"]
        assert payload["languages"]
        assert payload["cadence"]
        assert payload["incremental_cursor"]
        assert payload["historical_window"]
        assert payload["artifact_behavior"]
        assert payload["provenance_behavior"]
        assert payload["reuse_attribution"]
        assert payload["known_gaps"]
        assert payload["catalogue_state"] in {"available", "partial"}
        assert payload["evidence"]["promotion_ready"] == (
            payload["catalogue_state"] == "available"
        )
        if payload["catalogue_state"] == "available":
            assert payload["last_verified_live_check"]


def test_capability_api_and_operator_schedule_share_the_same_manifest(harness):
    client, *_ = harness

    catalogue_response = client.get("/api/connectors/capabilities")
    assert catalogue_response.status_code == 200
    catalogue = catalogue_response.json()
    assert catalogue["schema_version"] == CAPABILITY_SCHEMA_VERSION
    assert catalogue["catalogue_revision"] == CAPABILITY_CATALOG_REVISION
    by_key = {
        (item["connector"], item["stream"]): item for item in catalogue["items"]
    }

    schedule_response = client.get("/api/admin/connectors")
    assert schedule_response.status_code == 200
    schedules = schedule_response.json()["items"]
    assert schedules
    for schedule in schedules:
        key = (schedule["connector"], schedule["stream"])
        assert schedule["capability"] == by_key[key]
        assert schedule["availability"] in {
            "available",
            "syncing",
            "healthy",
            "degraded",
            "unavailable",
            "partial",
        }
