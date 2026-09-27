"""Retained native page changes, standing scope, revision races and source privacy."""
from uuid import uuid4

import pytest
from conftest import LAW_URL, policy
from sqlalchemy import select
from test_private_dossier_monitoring import private
from test_product_contributions import no_discovery
from test_product_document_history import setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, tick
from test_product_monitoring_research import due, enable, model

from helvetic_lens.models import DocumentWatch, Law, Organization, OrganizationMembership, Version
from helvetic_lens.product_investigation_models import MonitoringResearchTrigger as Trigger
from helvetic_lens.product_models import DossierEntry


def changed(client, service, law_id, text):
    service.fetcher.values[LAW_URL] = policy(text)
    response = post(client, "/api/scans", {"law_ids": [law_id]})
    assert response.status_code == 202 and response.json()["status"] == "complete", response.text
    with service.db.session() as session:
        return session.get(Law, law_id).current_version_id


def last_run(client, root):
    page = client.get(root + "/monitoring-research").json()
    assert page["items"] and page["items"][0]["investigation"], page
    return page["items"][0]["investigation"]


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_real_page_acquisition_to_private_research_and_paired_comparison(signed, monkeypatch, product):
    client, service, _, target = signed
    doc, root, law_id, baseline, history = setup(client, product)
    saved, command = enable(client, root, include_page_changes=True)
    assert saved["policy"]["page_readiness"]["active"] == 1
    assert post(client, root + "/monitoring-research", command).json() == saved
    assert due(service)["started"] == 0
    first_id = changed(client, service, law_id, "Citizenship requires five years of continuous residence.")
    calls = model(monkeypatch, target)
    external = no_discovery(monkeypatch)
    fetched = len(service.fetcher.calls)
    assert due(service)["started"] == 1
    first = complete(client, service, root + "/investigations", last_run(client, root))
    assert first["status"] == "completed" and first["claims"], first
    second_id = changed(client, service, law_id, "Citizenship now requires six years of continuous residence.")
    fetched = len(service.fetcher.calls)
    assert due(service)["started"] == 1
    second = complete(client, service, root + "/investigations", last_run(client, root))
    assert second["status"] == "completed" and second["claims"], second
    item = client.get(root + "/monitoring-research").json()["items"][0]
    assert item["source_kind"] == "watched_page" and item["match_id"] is None
    assert item["page"]["version_id"] == second_id and item["page"]["previous"]["version_id"] == first_id
    assert "five years" in item["page"]["before"] and "six years" in item["page"]["after"]
    assert item["source_revision"] == str(item["page"]["revision"])
    source = second["sources"][0]
    assert source["kind"] == "saved_page_extract" and source["snapshot"]["saved_page"]["version_id"] == second_id
    assert len(calls) == 3 and "current" in calls[-1] and external == []
    assert "five years" not in str(calls[1]) and len(service.fetcher.calls) == fetched
    assert calls[1]["existing_claims"] == []
    evolution = client.get(root + "/evidence-changes").json()
    assert evolution["total"] == 1 and evolution["items"][0]["kind"] == "UPDATES"
    assert client.get(history + "/" + first_id, params={"expected_revision": item["page"]["previous"]["revision"]}).status_code == 200
    assert client.get(history + "/" + baseline).status_code == 200
    assert due(service)["started"] == 0 and len(calls) == 3
    export = client.get(root + "/export").json()
    assert len(export["monitoring_research"]["items"]) == 2
    assert client.get(root.split("/dossiers/")[0] + "/public-dossiers").json()["total"] == 0


def test_old_scope_never_analyzes_page_bodies_and_private_scope_is_unavailable(signed, monkeypatch):
    client, service, _, target = signed
    _, root, law_id, _, _ = setup(client)
    saved, _ = enable(client, root)
    assert saved["policy"]["include_page_changes"] is False
    calls = model(monkeypatch, target)
    changed(client, service, law_id, "New page content outside the topic-only authorization.")
    assert due(service)["started"] == 0 and not calls
    enable(client, root, include_page_changes=True)
    assert due(service)["started"] == 0  # Settings do not replay earlier captures.
    _, private_root, _ = private(client)
    read = client.get(private_root + "/monitoring-research").json()
    assert read["policy"]["page_readiness"]["allowed"] is False
    result = post(client, private_root + "/monitoring-research", {"request_key": str(uuid4()),
        "expected_revision": 0, "enabled": True, "daily_limit": 3,
        "standing_authority_confirmed": True, "include_page_changes": True})
    assert result.status_code == 409


@pytest.mark.parametrize("race", ["disable", "watch", "unlink", "revision", "previous_revision", "corpus", "exclude", "membership"])
def test_inflight_page_revocation_or_revision_discards_response(signed, monkeypatch, race):
    client, service, identity, target = signed
    _, root, law_id, baseline, _ = setup(client)
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "A newly retained page about citizenship and residence.")
    assert due(service)["started"] == 1
    run = last_run(client, root)
    revoked = []
    def revoke(_):
        if race == "disable":
            enable(client, root, enabled=False, include_page_changes=True)
            revoked.append(True)
            return
        with service.db.session() as session:
            if race == "watch":
                session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id)).auto_check_enabled = False
            elif race == "unlink":
                session.delete(session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == root.split('/')[-1], DossierEntry.kind == "monitor")))
            elif race in {"revision", "previous_revision"}:
                session.get(Version, current if race == "revision" else baseline).text = "Text corrected during inference."
            elif race == "corpus":
                other = Organization(name="Different corpus owner", slug="different-corpus")
                session.add(other)
                session.flush()
                session.get(Version, current).owner_organization_id = other.id
            elif race == "exclude":
                session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                    url=LAW_URL, data_json={"decision": "exclude", "revision": 1}))
            else:
                session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])).role = "viewer"
            session.commit()
        revoked.append(True)
    calls = model(monkeypatch, target, revoke)
    tick(service, run["id"])
    tick(service, run["id"])
    read = client.get(root + "/investigations/" + run["id"])
    assert read.status_code == 404 or (read.status_code == 200 and read.json()["claims"] == [])
    assert len(calls) == 1 and revoked == [True]


@pytest.mark.parametrize("withdrawal", ["current_corpus", "previous_corpus", "earlier_url"])
def test_completed_page_evidence_is_removed_from_readers_after_corpus_withdrawal(signed, monkeypatch, withdrawal):
    client, service, _, target = signed
    _, root, law_id, baseline, _ = setup(client)
    earlier_url = "https://example.ch/earlier-original"
    with service.db.session() as session:
        session.get(Version, baseline).source_url = earlier_url
        session.commit()
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "A private corpus text retained for an authorized dossier.")
    model(monkeypatch, target)
    due(service)
    run = complete(client, service, root + "/investigations", last_run(client, root))
    assert run["claims"]
    with service.db.session() as session:
        if withdrawal == "earlier_url":
            session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                url=earlier_url, data_json={"decision": "exclude", "revision": 1}))
        else:
            other = Organization(name="Revoked corpus", slug="revoked-corpus")
            session.add(other)
            session.flush()
            session.get(Version, current if withdrawal == "current_corpus" else baseline).owner_organization_id = other.id
        session.commit()
    path = root + "/investigations/" + run["id"]
    assert client.get(path).status_code == client.get(path + "/events?wait=0").status_code == 404
    page = client.get(root + "/monitoring-research").json()
    assert page["items"][0]["page"] is None and not page["items"][0]["source"]["title"]
    exported = client.get(root + "/export").json()
    assert "private corpus text" not in str(exported)


def test_page_receipts_and_topic_triggers_share_daily_capacity(signed, monkeypatch):
    from test_product_monitoring_research import signal

    client, service, _, target = signed
    doc, root, law_id, _, _ = setup(client)
    enable(client, root, include_page_changes=True, daily_limit=1)
    model(monkeypatch, target)
    changed(client, service, law_id, "A page change reaches the shared daily budget first.")
    due(service)
    complete(client, service, root + "/investigations", last_run(client, root))
    topic = client.get(root).json()["profile"]["topics"][0]
    signal(service, topic)
    assert due(service)["started"] == 0
    page = client.get(root + "/monitoring-research").json()
    assert page["policy"]["used_today"] == 1 and page["items"][0]["state"] == "pending"
    assert {v["source_kind"] for v in page["items"]} == {"topic_match", "watched_page"}
    with service.db.session() as session:
        rows = list(session.scalars(select(Trigger)))
        assert len(rows) == 2 and all(row.source_identifier and row.source_revision for row in rows)


@pytest.mark.parametrize("case", ["paused", "manual", "synthetic", "import", "excluded", "oversized", "same_text"])
def test_unready_page_versions_never_start_paid_work(signed, monkeypatch, case):
    client, service, _, target = signed
    _, root, law_id, baseline, _ = setup(client)
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "A different retained source text for readiness verification.")
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
        version = session.get(Version, current)
        if case == "paused":
            watch.active = False
        elif case == "manual":
            watch.auto_check_enabled = False
        elif case == "synthetic":
            version.synthetic = True
        elif case == "import":
            version.origin = "import"
        elif case == "excluded":
            session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                url=LAW_URL, data_json={"decision": "exclude", "revision": 1}))
        elif case == "oversized":
            version.text = "Long evidence " * 20000
        else:
            version.text = session.get(Version, baseline).text
        session.commit()
    calls = model(monkeypatch, target)
    assert due(service)["started"] == 0 and not calls
    items = client.get(root + "/monitoring-research").json()["items"]
    assert all(item["state"] == "skipped" for item in items)
    if case in {"oversized", "same_text", "excluded"}:
        assert len(items) == 1 and items[0]["reason"]
        assert due(service)["started"] == 0
        assert client.get(root + "/monitoring-research").json()["total"] == 1


def test_upgrade_preserves_live_topic_receipts_and_existing_authorization(signed):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from test_product_monitoring_research import signal

    from alembic import command as migrate
    from helvetic_lens.db import Base
    from helvetic_lens.product_investigation_models import MonitoringResearchPolicy as Policy
    from helvetic_lens.product_operations import fingerprint

    client, service, identity, _ = signed
    _, root, topic = private(client)
    _, body = enable(client, root)
    signal(service, topic)
    due(service)
    before = client.get(root + "/monitoring-research").json()
    with service.db.session() as session:
        saved = session.scalar(select(Policy))
        saved.last_request_fingerprint = fingerprint({**body, "actor": identity["user"]["id"]})
        session.commit()
    def config(connection):
        value = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        value.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
        value.attributes["connection"] = connection
        return value
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "02d495bef125")
        assert "source_identifier" not in [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(product_monitoring_research_triggers)")]
        connection.rollback()
        migrate.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name in {Policy.__tablename__, Trigger.__tablename__}})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    after = client.get(root + "/monitoring-research").json()
    assert after == before
    assert not after["policy"]["include_page_changes"]
    assert post(client, root + "/monitoring-research", body).status_code == 200
    assert due(service)["started"] == 0


def test_page_scope_requires_current_explicit_consent_and_cannot_be_downgraded(signed):
    from test_account_deletion_migration import config

    from alembic import command as migrate

    client, service, _, _ = signed
    _, root, _, _, _ = setup(client)
    _, body = enable(client, root)
    proposed = {**body, "request_key": str(uuid4()), "expected_revision": 1, "include_page_changes": True,
        "standing_authority_confirmed": False}
    assert post(client, root + "/monitoring-research", proposed).status_code == 422
    proposed["standing_authority_confirmed"] = True
    assert post(client, root + "/monitoring-research", {**proposed, "expected_revision": 0}).status_code == 409
    assert post(client, root + "/monitoring-research", {**proposed, "include_page_changes": "true"}).status_code == 422
    assert post(client, root + "/monitoring-research", proposed).status_code == 200
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retained monitoring research"):
        migrate.downgrade(config(connection), "02d495bef125")
