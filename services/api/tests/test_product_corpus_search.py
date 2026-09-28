"""Whole-ledger search recovers older evidence and never turns a cache into ACL."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from test_product_dossiers import signed as signed
from test_product_evidence_search import QUOTE, local, retained, search
from test_product_web_research import setup

from helvetic_lens import decision_engines as decisions
from helvetic_lens import evidence_embeddings as embeddings
from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_investigation_models import DossierClaim, InvestigationSource
from helvetic_lens.product_models import DossierEntry, DossierMember
from helvetic_lens.product_retrieval_models import EvidenceVector


def encoder(monkeypatch, service, hook=None, failure=None):
    service.environment_settings.evidence_embedding_url = "http://127.0.0.1:18762/v1/embeddings"
    calls = []
    async def encode(self, texts):
        calls.append(texts)
        if hook:
            hook(len(calls))
        if failure:
            raise decisions.DecisionUnavailable(failure)
        return [{"vector": tuple(([1.0, 0.0] if text.startswith("query:") or "two and eight" in text else [0.0, 1.0]) + [0.0] * 382),
                 "input_tokens": 30, "truncated": False} for text in texts]
    monkeypatch.setattr(embeddings.LocalEmbeddings, "encode", encode)
    async def forbidden(*args, **kwargs):
        raise AssertionError("Private corpus retrieval must not use hosted Jev")
    monkeypatch.setattr(decisions.JevEngine, "choose", forbidden)
    return calls


def complete(client, root, **values):
    values = {"mode": "corpus", **values}
    pages = []
    for _ in range(20):
        response = search(client, root, **values)
        assert response.status_code == 200, response.text
        page = response.json()
        pages.append(page)
        if not page["preparing"]:
            return page, pages
        values.update(as_of=page["as_of"], fingerprint=page["fingerprint"])
    raise AssertionError("Preparation did not finish")


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("audience", ["draft", "workspace", "team"])
def test_older_cross_language_evidence_ranks_across_all_records_and_resumes(signed, monkeypatch, product, audience):
    client, service, _, _ = signed
    doc, root = setup(client, product, audience)
    texts = [f"Unrelated administration paragraph {i}." for i in range(41)]
    texts[39] = QUOTE
    run_id, source_id = retained(service, doc, texts, finding=False)
    calls = encoder(monkeypatch, service)
    opinions = local(monkeypatch, service)
    # One request saves a real checkpoint; a new request resumes it.
    first = search(client, root, mode="corpus").json()
    assert first["preparing"] and first["prepared_records"] == 16 and first["items"] == []
    assert first["examined_records"] == 0 and not opinions
    page, checkpoints = complete(client, root, as_of=first["as_of"], fingerprint=first["fingerprint"])
    assert [p["prepared_records"] for p in checkpoints] == [32, 41, 41]
    assert page["examined_records"] == page["total_records"] == 41
    assert page["items"][0]["quote"] == QUOTE and page["items"][0]["locator"] == "p39"
    assert page["items"][0]["investigation_id"] == run_id and page["items"][0]["source_id"] == source_id
    assert page["items"][0]["semantic_match"] and not page["items"][0]["literal_match"]
    assert len(calls) == 4 and len(opinions) == 12
    with service.db.session() as session:
        rows = list(session.scalars(select(EvidenceVector)))
        assert len(rows) == 41 and all(len(row.vector) == 1536 for row in rows)
        assert all(row.model == embeddings.MODEL and row.dossier_id == doc["id"] for row in rows)
    seen = [item["id"] for item in page["items"]]
    while page["next_offset"] is not None:
        page, checkpoints = complete(client, root, offset=page["next_offset"], as_of=page["as_of"], fingerprint=page["fingerprint"])
        assert len(checkpoints) == 1
        seen += [item["id"] for item in page["items"]]
    assert len(seen) == len(set(seen)) == 41
    before = len(calls)
    assert search(client, root, mode="corpus", check_only=True, as_of=page["as_of"], fingerprint=page["fingerprint"]).json() == {"current": True}
    assert len(calls) == before and page["measurement"]["estimated_cost_usd"] is None
    assert client.get(f"/api/products/{product}/public-knowledge?q=Celsius").json()["total"] == 0
    assert client.post(root + "/evidence-search", json={"query": "Celsius", "mode": "corpus"}).status_code == 403
    assert search(client, root.replace(product, "loyer" if product == "pharma" else "pharma"), mode="corpus").status_code == 404


@pytest.mark.parametrize("phase", ["preparation", "query", "opinion"])
@pytest.mark.parametrize("change", ["membership", "source", "claim", "account", "session"])
def test_revocation_and_mutation_during_every_local_phase_never_return_stale_evidence(signed, monkeypatch, phase, change):
    client, service, identity, _ = signed
    doc, root = setup(client, audience="workspace")
    retained(service, doc)
    encoder(monkeypatch, service)
    local(monkeypatch, service)
    if phase != "preparation":
        assert search(client, root, mode="corpus").json()["preparing"]
    def revoke(count):
        if count != 1:
            return
        with service.db.session() as session:
            if change == "membership":
                session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            elif change == "source":
                session.add(DossierEntry(dossier_id=doc["id"], actor_user_id=identity["user"]["id"],
                    request_key=str(uuid4()), kind="source_review", url="https://example.org/source",
                    data_json={"revision": 1, "decision": "exclude"}))
            elif change == "claim":
                row = session.scalar(select(DossierClaim))
                row.statement, row.revision = "Changed claim after inference began", row.revision + 1
            elif change == "account":
                session.get(User, identity["user"]["id"]).active = False
            else:
                for row in session.scalars(select(UserSession).where(UserSession.user_id == identity["user"]["id"])):
                    row.revoked_at = utcnow()
            session.commit()
    if phase == "opinion":
        local(monkeypatch, service, revoke)
    else:
        encoder(monkeypatch, service, revoke)
    response = search(client, root, mode="corpus")
    assert response.status_code in {401, 403, 404, 409}, response.text
    assert QUOTE not in response.text
    if phase == "preparation":
        with service.db.session() as session:
            assert session.scalar(select(func.count()).select_from(EvidenceVector)) == 0


def test_source_revocation_filters_warmed_cache_before_counts_and_rank(signed, monkeypatch):
    client, service, identity, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    calls = encoder(monkeypatch, service)
    local(monkeypatch, service)
    page, _ = complete(client, root)
    before = len(calls)
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], actor_user_id=identity["user"]["id"],
            request_key=str(uuid4()), kind="source_review", url="https://example.org/source",
            data_json={"revision": 1, "decision": "exclude"}))
        session.commit()
    assert search(client, root, mode="corpus", check_only=True, as_of=page["as_of"], fingerprint=page["fingerprint"]).status_code == 409
    empty, _ = complete(client, root)
    assert empty["total_records"] == empty["prepared_records"] == 0 and empty["items"] == []
    assert len(calls) == before


def test_changed_claim_rebuilds_only_exact_changed_input_and_retains_original_citations(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    calls = encoder(monkeypatch, service)
    local(monkeypatch, service)
    page, _ = complete(client, root)
    with service.db.session() as session:
        claim = session.scalar(select(DossierClaim))
        claim.statement = "The source now has a revised interpretation."
        claim.revision += 1
        session.commit()
    assert search(client, root, mode="corpus", as_of=page["as_of"], fingerprint=page["fingerprint"]).status_code == 409
    before = len(calls)
    updated, phases = complete(client, root)
    assert len(calls) == before + 2 and len(calls[-2]) == 1
    assert len(phases) == 2 and updated["fingerprint"] != page["fingerprint"]
    assert all(item["quote"] == QUOTE for item in updated["items"])


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_dossier_only_guests_can_prepare_but_cannot_reuse_cache_after_revocation(signed, monkeypatch, role):
    from test_product_guests import accept, guest, invitation
    from test_product_teams import switch

    client, service, _, _ = signed
    account, cookies = guest(client, service)
    doc, root = setup(client, audience="team")
    _, sibling = setup(client, audience="team")
    retained(service, doc)
    invite = invitation(client, root, account, role)
    switch(client, cookies)
    accept(client, root, invite)
    calls = encoder(monkeypatch, service)
    local(monkeypatch, service)
    page, _ = complete(client, root)
    assert page["total_records"] == 2
    assert search(client, sibling, mode="corpus").status_code == 404
    with service.db.session() as session:
        session.execute(delete(DossierMember).where(DossierMember.dossier_id == doc["id"], DossierMember.user_id == account["user"]["id"]))
        session.commit()
    before = len(calls)
    response = search(client, root, mode="corpus")
    assert response.status_code in {403, 404} and QUOTE not in response.text and len(calls) == before


def test_capacity_and_service_failures_preserve_words_and_uncertain_candidates(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    calls = encoder(monkeypatch, service, failure="timeout")
    local(monkeypatch, service)
    assert search(client, root, mode="corpus").status_code == 503
    assert search(client, root, "two eight", mode="literal").json()["matching_records"] == 2
    monkeypatch.setattr(embeddings, "MAX_RECORDS", 1)
    assert search(client, root, mode="corpus").status_code == 409 and len(calls) == 1
    monkeypatch.setattr(embeddings, "MAX_RECORDS", 20000)
    encoder(monkeypatch, service)
    local(monkeypatch, service, failure="timeout")
    page, _ = complete(client, root)
    assert len(page["items"]) == page["examined_records"] == 2
    assert page["measurement"]["error"] == "timeout"
    assert all(item["relevance_probability"] is None for item in page["items"])


def test_vector_migration_containment_and_source_erasure(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.db import Base

    client, service, _, _ = signed
    doc, root = setup(client)
    run_id, source_id = retained(service, doc)
    with service.db.engine.connect() as connection:
        command.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, compare_to: kind == "table" and name == "product_evidence_vectors" or kind != "table"})
        assert compare_metadata(context, Base.metadata) == []
        command.downgrade(config(connection), "05d495bef125")
        command.upgrade(config(connection), "head")
    with service.db.session() as session:
        session.add(EvidenceVector(dossier_id=doc["id"], organization_id=service.organization_id,
            investigation_id=run_id, source_id=source_id, record_key=source_id + ":0", model=embeddings.MODEL,
            input_sha256="a" * 64, vector=embeddings.pack([1.0] + [0.0] * 383), input_tokens=3, truncated=False))
        session.commit()
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="Discard the derived"):
            command.downgrade(config(connection), "05d495bef125")
    with service.db.session() as session:
        session.delete(session.get(InvestigationSource, source_id))
        session.commit()
        assert session.scalar(select(func.count()).select_from(EvidenceVector)) == 0


@pytest.mark.parametrize("withdrawal", ["current_corpus", "previous_corpus", "earlier_url"])
def test_both_retained_page_versions_filter_already_prepared_vectors(signed, monkeypatch, withdrawal):
    from test_product_document_history import setup as pages
    from test_product_investigations import complete as finish
    from test_product_monitoring_research import due, enable, model
    from test_product_page_research import changed, last_run

    from helvetic_lens.models import Organization, Version

    client, service, _, target = signed
    _, root, law_id, baseline, _ = pages(client)
    earlier_url = "https://example.ch/earlier-original"
    with service.db.session() as session:
        session.get(Version, baseline).source_url = earlier_url
        session.commit()
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "The saved page describes a new private evidence requirement.")
    model(monkeypatch, target)
    due(service)
    finish(client, service, root + "/investigations", last_run(client, root))
    calls = encoder(monkeypatch, service)
    local(monkeypatch, service)
    page, _ = complete(client, root)
    assert page["total_records"] > 0
    count = len(calls)
    with service.db.session() as session:
        if withdrawal == "earlier_url":
            session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                url=earlier_url, data_json={"decision": "exclude", "revision": 1}))
        else:
            other = Organization(name="Revoked corpus", slug="revoked-index-corpus")
            session.add(other)
            session.flush()
            session.get(Version, current if withdrawal == "current_corpus" else baseline).owner_organization_id = other.id
        session.commit()
    empty, _ = complete(client, root)
    assert empty["total_records"] == empty["prepared_records"] == 0 and not empty["items"]
    assert len(calls) == count


def test_concurrent_preparation_commits_one_cache_per_record(signed, monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor

    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    encoder(monkeypatch, service)
    original = embeddings.LocalEmbeddings.encode
    barrier = threading.Barrier(2)
    async def concurrent(self, texts):
        await asyncio.to_thread(barrier.wait, 10)
        return await original(self, texts)
    monkeypatch.setattr(embeddings.LocalEmbeddings, "encode", concurrent)
    with ThreadPoolExecutor(2) as executor:
        futures = [executor.submit(search, client, root, mode="corpus") for _ in range(2)]
        replies = [future.result(20) for future in futures]
    assert [reply.status_code for reply in replies] == [200, 200], [reply.text for reply in replies]
    assert all(reply.json()["prepared_records"] == 2 for reply in replies)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceVector)) == 2
