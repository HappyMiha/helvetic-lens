"""Real API/privacy/revision tests with clearly fictional retained source fixtures."""
import copy
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_product_community import command
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_public_research import setup
from test_product_teams import switch

from helvetic_lens.db import utcnow
from helvetic_lens.product_investigation_models import (
    DossierEntity,
    EntityIdentityReview,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_models import (
    DossierEntry,
    DossierMember,
    ProductDossier,
    ProductPublication,
    PublicContribution,
)

QUOTE = "Fictional register: Alpine Example, ID DEMO-123, issued by Demo Registry in Switzerland."


def seed(signed, *, public=False, product="pharma"):
    client, service, identity, _ = signed
    if public:
        doc, publication, root = setup(client, service, identity, product=product)
    else:
        doc, _ = create(client)
        with service.db.session() as session:
            session.get(ProductDossier, doc["id"]).product = product
            session.commit()
        publication, root = None, ROOT.replace("pharma", product) + "/" + doc["id"]
    ids, source_ids, run_ids = [], [], []
    for index in range(2):
        contribution = None
        if public:
            body = command(kind="comment", analyse_publicly=True)
            body["content"].update(body=QUOTE, sources=[])
            response = post(client, root + "/discussion", body)
            assert response.status_code == 201, response.text
            contribution = response.json()["contribution"]
        with service.db.session() as session:
            if public:
                run = session.get(Investigation, contribution["research"]["id"])
                run.status = "completed"
            else:
                run = Investigation(dossier_id=doc["id"], organization_id=identity["organization"]["id"],
                    status="completed", request_key=str(uuid4()), question="Fictional identity example", external_discovery=False)
                session.add(run)
            session.flush()
            source = InvestigationSource(dossier_id=doc["id"], organization_id=run.organization_id, investigation_id=run.id,
                source_key="fixture", kind="public_contribution" if public else "contribution", title=f"Fictional registry capture {index}",
                url=f"https://example.test/registry/{index}", sha256=hashlib.sha256(QUOTE.encode()).hexdigest(),
                snapshot={"excerpts": [{"passage": "p1", "text": QUOTE}]})
            session.add(source)
            session.flush()
            entity = DossierEntity(dossier_id=doc["id"], organization_id=run.organization_id, investigation_id=run.id,
                name="Alpine Example", kind="organization", evidence={"source_id": source.id, "sha256": source.sha256,
                    "quote": QUOTE, "locator": "p1", "identity": "source_identifier", "mentions": [{"name": "Alpine Example", "quote": QUOTE}],
                    "identifier": {"value": "DEMO-123", "issuer": "Demo Registry", "jurisdiction": "Switzerland", "kind": "organization"}})
            session.add(entity)
            session.commit()
            ids.append(entity.id)
            source_ids.append(source.id)
            run_ids.append(run.id)
    root = root.replace("/loyer/", "/legal/")
    return client, service, doc, root, ids, source_ids, run_ids, publication


def proposal(client, root):
    response = client.get(root + "/entity-identities")
    assert response.status_code == 200, response.text
    return response.json()["suggestions"]["items"][0]


def review_body(value, **changes):
    return {"entity_id": value["entity_id"], "previous_entity_id": value["previous_entity_id"],
        "request_key": str(uuid4()), "expected_revision": value["revision"],
        "evidence_fingerprint": value["evidence_fingerprint"], "decision": "same",
        "reason": "Both fictional captures cite the same complete registry identity.", **changes}


@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_review_journey_preserves_originals_replays_and_separates_acceptance(signed, public, product):
    client, service, doc, root, ids, _, _, _ = seed(signed, public=public, product=product)
    with service.db.session() as session:
        originals = [copy.deepcopy(session.get(DossierEntity, key).evidence) for key in ids]
    value = proposal(client, root)
    assert value["revision"] == 0 and value["decision"] == "unreviewed"
    assert value["first"]["quote"] == value["second"]["quote"] == QUOTE
    route, body = root + "/entity-identities/review", review_body(value, confirm_public=public)
    assert client.post(route, json=body).status_code == 403
    if public:
        assert post(client, route, {**body, "confirm_public": False}).status_code == 409
    saved = post(client, route, body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["decision"] == "same" and not saved.json()["stale"]
    assert len(saved.json()["history"]) == 1
    assert post(client, route, body).json() == saved.json()
    assert post(client, route, {**body, "decision": "different"}).status_code == 409
    assert post(client, route, {**body, "request_key": str(uuid4())}).status_code == 409
    changed = post(client, route, review_body(saved.json(), decision="different", confirm_public=public))
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    assert [v["decision"] for v in changed.json()["history"]] == ["same", "different"]
    assert post(client, route, body).json() == changed.json(), "Old retry must show latest retained decision without adding history"
    page = client.get(root + "/entity-identities").json()
    assert page["total"] == 1 and not page["suggestions"]["items"]
    if public:
        client.cookies.clear()
        assert client.get(root + "/entity-identities").json()["items"] == page["items"]
        assert client.get(root + "/entity-identities/workspace").status_code == 401
        for secret in (doc["id"], signed[2]["organization"]["id"], signed[2]["user"]["id"], body["request_key"]):
            assert secret not in json.dumps(page)
    else:
        exported = client.get(root + "/export")
        assert exported.status_code == 200, exported.text
        assert exported.json()["entity_identity_reviews"] == page["items"]
    with service.db.session() as session:
        assert [session.get(DossierEntity, key).evidence for key in ids] == originals
        assert session.scalar(select(func.count()).select_from(EntityIdentityReview)) == 2
    assert signed[3].calls == []


@pytest.mark.parametrize("field,value", [("issuer", "Other Registry"), ("jurisdiction", ""), ("value", "DEMO-999"), ("kind", "person")])
def test_names_and_incomplete_or_different_namespaces_are_not_suggestions(signed, field, value):
    client, service, _, root, ids, _, _, _ = seed(signed)
    before = proposal(client, root)
    with service.db.session() as session:
        entity = session.get(DossierEntity, ids[0])
        entity.evidence = {**entity.evidence, "identifier": {**entity.evidence["identifier"], field: value}}
        session.commit()
    assert client.get(root + "/entity-identities").json()["suggestions"]["items"] == []
    assert post(client, root + "/entity-identities/review", review_body(before)).status_code == 409


@pytest.mark.parametrize("public", [False, True])
def test_changed_capture_stales_decision_and_recheck_is_explicit(signed, public):
    client, service, _, root, _, sources, _, _ = seed(signed, public=public)
    saved = post(client, root + "/entity-identities/review", review_body(proposal(client, root), confirm_public=public)).json()
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[0])
        source.snapshot = {"excerpts": [{"passage": "p1", "text": QUOTE + " Additional fictional context."}]}
        session.commit()
    stale = client.get(root + "/entity-identities").json()["items"][0]
    assert stale["stale"] and stale["decision"] == "same" and stale["history"] == saved["history"]
    assert post(client, root + "/entity-identities/review", review_body(saved, confirm_public=public)).status_code == 409
    fresh = post(client, root + "/entity-identities/review", review_body(stale, decision="unresolved", confirm_public=public))
    assert fresh.status_code == 200 and not fresh.json()["stale"] and fresh.json()["revision"] == 2


@pytest.mark.parametrize("gate", ["hidden", "revision", "withdrawn", "excluded"])
def test_visibility_filters_saved_counts_candidates_and_replay(signed, gate):
    client, service, _, root, _, sources, runs, publication = seed(signed, public=True)
    body = review_body(proposal(client, root), confirm_public=True)
    assert post(client, root + "/entity-identities/review", body).status_code == 200
    with service.db.session() as session:
        run = session.get(Investigation, runs[0])
        if gate == "hidden":
            session.get(PublicContribution, run.public_contribution_id).status = "hidden"
        if gate == "revision":
            session.get(ProductPublication, publication["id"]).revision += 1
        if gate == "withdrawn":
            session.get(ProductPublication, publication["id"]).status = "withdrawn"
        if gate == "excluded":
            source = session.get(InvestigationSource, sources[0])
            session.add(DossierEntry(dossier_id=run.dossier_id, kind="source_review", request_key=str(uuid4()),
                url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    response = client.get(root + "/entity-identities")
    if gate == "withdrawn":
        assert response.status_code == 404
    else:
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0 and response.json()["suggestions"]["items"] == []
        assert "DEMO-123" not in response.text
    assert post(client, root + "/entity-identities/review", body).status_code in (404, 409)


@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_current_guest_role_without_host_membership_and_revocation(signed, public, role):
    client, service, doc, root, _, _, _, _ = seed(signed, public=public)
    value = proposal(client, root)
    account, cookies = guest(client, service)
    private = ROOT + "/" + doc["id"]
    assert post(client, private + "/team/enable", {"expected_revision": 1}).status_code == 200
    invitation_row = invitation(client, private, account, role)
    switch(client, cookies)
    accept(client, private, invitation_row)
    if role == "EDITOR":
        from helvetic_lens.models import OrganizationMembership

        with service.db.session(include_all_organizations=True) as session:
            member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"]))
            member.role = "viewer"
            session.commit()
    path = root + "/entity-identities"
    controls = client.get(path + ("/workspace" if public else "")).json()
    assert controls["can_review"] is (role == "EDITOR")
    response = post(client, path + "/review", review_body(value, confirm_public=public))
    assert response.status_code == (200 if role == "EDITOR" else 403), response.text
    assert client.get("/api/auth/session").json()["organization"]["id"] == account["organization"]["id"]
    if role == "EDITOR":
        with service.db.session(include_all_organizations=True) as session:
            member = session.scalar(select(DossierMember).where(DossierMember.dossier_id == doc["id"], DossierMember.user_id == account["user"]["id"]))
            member.role = "VIEWER"
            session.commit()
        assert post(client, path + "/review", review_body(response.json(), decision="different", confirm_public=public)).status_code == 403


def test_cross_dossier_and_private_public_pairs_are_rejected(signed):
    client, service, _, private, ids, _, _, _ = seed(signed)
    _, _, _, public, public_ids, _, _, _ = seed(signed, public=True)
    value = proposal(client, private)
    assert post(client, public + "/entity-identities/review", review_body(value, confirm_public=True)).status_code == 404
    assert post(client, private + "/entity-identities/review", review_body(value, previous_entity_id=public_ids[0])).status_code == 404
    assert post(client, private + "/entity-identities/review", review_body(value, previous_entity_id=ids[0], entity_id=ids[0])).status_code == 404
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(EntityIdentityReview)) == 0


def test_saved_reviews_survive_candidate_window_and_schema_is_additive(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command as migrate
    from helvetic_lens.db import Base

    client, service, doc, root, ids, sources, runs, _ = seed(signed)
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "09d495bef125")
        migrate.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name == "product_entity_identity_reviews"})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    value = proposal(client, root)
    assert post(client, root + "/entity-identities/review", review_body(value)).status_code == 200
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retain entity reviews"):
        migrate.downgrade(config(connection), "09d495bef125")
    with service.db.session() as session:
        original = session.get(DossierEntity, ids[0])
        for index in range(121):
            session.add(DossierEntity(dossier_id=doc["id"], organization_id=original.organization_id, investigation_id=runs[0],
                name="Unresolved name", kind="organization", evidence={}, created_at=utcnow() + timedelta(seconds=index)))
        session.commit()
        review = session.scalar(select(EntityIdentityReview))
        review.previous_investigation_id = review.investigation_id
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    page = client.get(root + "/entity-identities").json()
    assert page["total"] == 1 and len(page["items"]) == 1
    assert page["suggestions"]["entities_examined"] == 120 and page["suggestions"]["entity_window_limited"]
    with service.db.session() as session:
        session.delete(session.get(InvestigationSource, sources[0]))
        session.commit()
        assert session.get(DossierEntity, ids[0]) is not None
        assert session.scalar(select(func.count()).select_from(EntityIdentityReview)) == 0
    assert client.get(root + "/entity-identities").json()["total"] == 0


def test_reviewer_account_erasure_keeps_deidentified_shared_history(signed):
    from test_account_deletion_api import confirmation

    client, service, doc, root, _, _, _, _ = seed(signed, public=True)
    value = proposal(client, root)
    account, cookies = guest(client, service)
    private = ROOT + "/" + doc["id"]
    assert post(client, private + "/team/enable", {"expected_revision": 1}).status_code == 200
    invite = invitation(client, private, account, "EDITOR")
    switch(client, cookies)
    accept(client, private, invite)
    first = post(client, root + "/entity-identities/review", review_body(value, confirm_public=True))
    assert first.status_code == 200, first.text
    second = post(client, root + "/entity-identities/review", review_body(first.json(), decision="unresolved", confirm_public=True))
    assert second.status_code == 200, second.text
    erased = post(client, "/api/account/deletion", confirmation(client))
    assert erased.status_code == 200, erased.text
    page = client.get(root + "/entity-identities").json()
    assert page["total"] == 1 and len(page["items"][0]["history"]) == 2
    assert all(entry["reviewer"] == "Former dossier editor" for entry in page["items"][0]["history"])
    with service.db.session(include_all_organizations=True) as session:
        rows = list(session.scalars(select(EntityIdentityReview)))
        assert len(rows) == 2 and all(row.reviewed_by_user_id is None for row in rows)


def test_same_dossier_public_mentions_do_not_mix_with_private_runs(signed):
    client, service, doc, root, _, _, run_ids, _ = seed(signed, public=True)
    value = proposal(client, root)
    with service.db.session() as session:
        run = session.get(Investigation, run_ids[0])
        run.publication_id = run.publication_revision = run.public_contribution_id = run.public_contribution_revision = None
        session.commit()
    private = ROOT + "/" + doc["id"]
    for route in (root, private):
        page = client.get(route + "/entity-identities").json()
        assert page["total"] == 0 and page["suggestions"]["items"] == []
        assert post(client, route + "/entity-identities/review", review_body(value, confirm_public=True)).status_code == 404


def test_saved_decision_pagination_and_source_exclusion_precede_counts(signed):
    from helvetic_lens.product_entity_identity import pair
    from helvetic_lens.product_investigations import scope

    client, service, doc, root, ids, sources, runs, _ = seed(signed)
    with service.db.session() as session:
        original, other = (session.get(DossierEntity, key) for key in ids)
        # Legacy distinct mentions can share a source identity; they remain rows.
        for _ in range(21):
            extra = DossierEntity(**scope(session.get(Investigation, runs[0])), name=original.name,
                kind=original.kind, evidence=copy.deepcopy(original.evidence))
            session.add(extra)
            session.flush()
            first, second = sorted((extra, other), key=lambda value: value.id)
            context = pair(session, first, second)
            session.add(EntityIdentityReview(**scope(session.get(Investigation, first.investigation_id)),
                entity_id=first.id, previous_entity_id=second.id, previous_investigation_id=second.investigation_id,
                source_id=context["first"]["source"]["id"], previous_source_id=context["second"]["source"]["id"],
                decision="unresolved", reason="Fictional fixture requires human research.", revision=1,
                evidence_fingerprint=context["evidence_fingerprint"], request_key=str(uuid4()), request_fingerprint="f" * 64))
        session.commit()
    first = client.get(root + "/entity-identities").json()
    second = client.get(root + "/entity-identities?offset=20").json()
    assert first["total"] == second["total"] == 21
    assert len(first["items"]) == 20 and len(second["items"]) == 1 and second["suggestions"] is None
    assert not {v["id"] for v in first["items"]} & {v["id"] for v in second["items"]}
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[0])
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
            url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    for offset in (0, 20):
        response = client.get(root + f"/entity-identities?offset={offset}").json()
        assert response["total"] == 0 and response["items"] == []
    assert client.get(root + "/export").json()["entity_identity_reviews"] == []
