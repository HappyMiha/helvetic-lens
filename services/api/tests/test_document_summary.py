"""Summary metadata, exact law identity and saved scan/report selection."""

from datetime import timedelta

import pytest
from conftest import add_law
from test_analysis_selection import seed
from test_law_history_metadata import recording

from helvetic_lens import law_history
from helvetic_lens.db import utcnow
from helvetic_lens.models import Comparison, Law, Organization, Profile, Scan, ScanItem, Version
from helvetic_lens.service import version_summary


def test_saved_report_summary_loads_diff_only_for_freshness_and_never_version_body(harness):
    client, fetcher, service, model = harness
    law, comparison, current, calls = seed(harness, 1)
    with service.db.session() as session:
        expected = version_summary(session.get(Version, law["current_version_id"]))
    fetches = len(fetcher.calls)
    with recording(service) as (_, loaded):
        response = client.get(f"/api/laws/{law['id']}?paged_history=true")
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["current_version"] == expected
    assert value["analysis"]["id"] == current["id"] and value["analysis"]["stale"] is False
    assert not any(kind == "Version" for kind, _ in loaded)
    assert [id_ for kind, id_ in loaded if kind == "Comparison"] == [comparison["id"]]
    with service.db.session() as session:
        session.get(Profile, service.tenant_record_id).revision += 1
        session.commit()
    stale = client.get(f"/api/laws/{law['id']}").json()["analysis"]
    assert stale["id"] == current["id"] and stale["stale"] is True
    assert len(fetcher.calls) == fetches and len(model.calls) == calls


def scan_fixture(harness):
    _, _, service, _ = harness
    law, comparison, _, _ = seed(harness, 1)
    with service.db.session() as session:
        older = session.get(Comparison, comparison["id"])
        newer = Comparison(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            law_id=law["id"],
            owner_organization_id=service.organization_id,
            old_version_id=older.old_version_id,
            new_version_id=older.new_version_id,
            mode="latest-manual",
            diff={"counts": {"added": 9}},
            created_at=older.created_at + timedelta(days=1),
        )
        session.add(newer)
        scan = Scan(organization_id=service.organization_id, status="completed", total=1)
        session.add(scan)
        session.flush()
        item = ScanItem(
            organization_id=service.organization_id,
            scan_id=scan.id,
            law_id=law["id"],
            comparison_id=older.id,
            created_at=utcnow(),
        )
        session.add(item)
        session.commit()
        return law["id"], older.id, newer.id, item.id, scan.id


def test_summary_prefers_scan_comparison_and_uses_deterministic_scan_ties(harness):
    client, _, service, _ = harness
    law_id, older_id, newer_id, item_id, scan_id = scan_fixture(harness)
    value = client.get(f"/api/laws/{law_id}").json()
    assert value["comparison_id"] == older_id
    with service.db.session() as session:
        item = session.get(ScanItem, item_id)
        session.add(
            ScanItem(
                id="ffffffff-ffff-ffff-ffff-ffffffffffff",
                organization_id=service.organization_id,
                scan_id=scan_id,
                law_id=law_id,
                comparison_id=newer_id,
                created_at=item.created_at,
            )
        )
        session.commit()
    value = client.get(f"/api/laws/{law_id}").json()
    assert value["comparison_id"] == newer_id
    assert value["change_counts"] == {"added": 9}
    assert value["analysis"] is None


@pytest.mark.parametrize("hidden", ["item", "scan", "comparison", "wrong_law"])
def test_scan_selection_rejects_foreign_or_mismatched_links(harness, hidden):
    client, fetcher, service, _ = harness
    law_id, older_id, newer_id, item_id, scan_id = scan_fixture(harness)
    fetcher.values["https://example.test/other-summary"] = next(iter(fetcher.values.values()))
    other = add_law(client, url="https://example.test/other-summary")
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign scan", slug="foreign-scan-summary")
        session.add(foreign)
        session.flush()
        if hidden == "item":
            session.get(ScanItem, item_id).organization_id = foreign.id
        elif hidden == "scan":
            session.get(Scan, scan_id).organization_id = foreign.id
        elif hidden == "comparison":
            session.get(Comparison, older_id).owner_organization_id = foreign.id
        else:
            session.get(ScanItem, item_id).law_id = other["id"]
        session.commit()
        selected = law_history.summary_comparison(session, service.organization_id, law_id)
        assert selected.id == newer_id and selected.counts == {"added": 9}


@pytest.mark.parametrize("wrong", ["law", "owner", "missing"])
def test_current_version_metadata_cannot_follow_a_wrong_reference(harness, wrong):
    client, _, service, _ = harness
    law = add_law(client)
    with service.db.session(include_all_organizations=True) as session:
        saved = session.get(Law, law["id"])
        if wrong == "law":
            other = Law(
                name="Other source",
                url="https://example.test/other-version",
                owner_organization_id=service.organization_id,
            )
            session.add(other)
            session.flush()
            session.get(Version, saved.current_version_id).law_id = other.id
        elif wrong == "owner":
            foreign = Organization(name="Foreign version", slug="foreign-summary-version")
            session.add(foreign)
            session.flush()
            session.get(Version, saved.current_version_id).owner_organization_id = foreign.id
        else:
            saved.current_version_id = "missing"
        session.commit()
        result = service.law_summary(session, saved)
        assert result["current_version"] is None
