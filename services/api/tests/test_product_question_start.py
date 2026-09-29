"""One question really starts existing work, with atomic consent and private retries."""
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from test_auth import _register
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_iterative_research import QUESTION, complete, pipeline
from test_product_web_research import due, enable, newest
from test_product_web_research import pipeline as recurring_pipeline

from helvetic_lens import product_question_start as start
from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.models import OrganizationMembership, UserSession
from helvetic_lens.product_investigation_models import Investigation, WebResearchPolicy
from helvetic_lens.product_models import DossierEntry, PrivateDossierFollow, ProductDossier
from helvetic_lens.product_web_research import enqueue_due


def request(**changes):
    return {"request_key": str(uuid4()), "question": QUESTION, "public_monitoring_confirmed": True, **changes}


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_one_question_creates_research_daily_monitoring_and_private_updates(signed, monkeypatch, product):
    client, service, identity, model = signed
    trace = pipeline(monkeypatch, service, model)
    service.settings.typesafe_api_key = SecretStr("fixture")
    service.settings.apertus_base_url = "http://127.0.0.1:8181/v1"
    service.settings.apertus_model = "fixture"
    command = request()
    result = post(client, f"/api/products/{product}/start", command)
    assert result.status_code == 202, result.text
    saved = result.json()
    root = f'/api/products/{product}/dossiers/{saved["dossier_id"]}'
    dossier = client.get(root).json()
    config = dossier["profile"]["config"]
    assert config["name"] == QUESTION[:160] and config["goal"] == QUESTION
    assert config["topics"] == config["source_pack_ids"] == []
    assert dossier["profile"]["status"] == "draft"  # Still creator-private.
    assert dossier["research_monitoring"] == {"enabled": True, "cadence_hours": 24}
    assert client.get(root + "/follow").json()["following"]
    assert enqueue_due(service.db, service.settings)["started"] == 0
    assert trace["models"] == trace["queries"] == trace["reads"] == []
    assert post(client, f"/api/products/{product}/start", command).json() == saved
    value = complete(client, service, root + "/investigations", saved["investigation"])
    assert value["status"] == "completed" and value["sources"] and value["claims"], value
    assert trace["queries"] and trace["reads"] and trace["models"]
    assert client.get(root + "/follow").json()["research"]["unseen"] > 0
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(ProductDossier)) == 1
        assert session.scalar(select(func.count()).select_from(PrivateDossierFollow)) == 1
        receipt = session.scalar(select(DossierEntry).where(DossierEntry.kind == "question_start"))
        assert receipt.actor_user_id == identity["user"]["id"]
        assert receipt.data_json["daily_public_research_confirmed"] is True
    # The existing policy queues later work without another setup form or browser.
    recurring_trace = recurring_pipeline(monkeypatch, service, model)
    assert due(service, next_day=True)["started"] == 1
    updated = complete(client, service, root + "/investigations", newest(client, root))
    assert updated["status"] == "completed" and updated["claims"]
    assert recurring_trace["queries"] and recurring_trace["reads"] and recurring_trace["analysis"]
    assert due(service, next_day=True)["started"] == 1
    paused, _ = enable(client, root, enabled=False, question=QUESTION)
    assert not paused["policy"]["enabled"]
    replay = post(client, f"/api/products/{product}/start", command).json()
    assert replay["dossier_id"] == saved["dossier_id"] and not replay["monitoring"]["enabled"]
    assert client.get(root).json()["research_monitoring"]["enabled"] is False
    assert client.get(root + "/investigations").json()["total"] == 3
    assert client.get(f"/api/products/{product}/public-dossiers").json()["total"] == 0
    client.cookies.clear()
    assert client.get(root).status_code == 401
    assert _register(client, f"other-{product}@example.ch").status_code == 201
    assert client.get(root).status_code == 404


def test_invalid_consent_question_and_csrf_never_create_partial_work(signed):
    client, service, _, model = signed
    for changes in ({"public_monitoring_confirmed": False}, {"public_monitoring_confirmed": 1},
                    {"public_monitoring_confirmed": "true"}, {"question": "    "}, {"question": "x" * 301},
                    {"title": "Not a required separate field"}, {"decision_order": "jev_first"}):
        assert post(client, "/api/products/legal/start", request(**changes)).status_code == 422
    assert client.post("/api/products/legal/start", json=request()).status_code == 403
    with service.db.session() as session:
        for table in (ProductDossier, LegalMonitoringProfile, Investigation, WebResearchPolicy, PrivateDossierFollow):
            assert session.scalar(select(func.count()).select_from(table)) == 0
    assert not model.calls and not service.fetcher.calls


def test_changed_retry_current_role_and_revoked_session_are_fenced(signed):
    client, service, identity, _ = signed
    command = request()
    result = post(client, "/api/products/legal/start", command)
    assert result.status_code == 202, result.text
    assert post(client, "/api/products/legal/start", {**command, "question": "Another different question"}).status_code == 409
    with service.db.session() as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
        member.role = "viewer"
        session.commit()
    assert post(client, "/api/products/legal/start", command).status_code == 403
    with service.db.session(include_all_organizations=True) as session:
        for login in session.scalars(select(UserSession).where(UserSession.user_id == identity["user"]["id"])):
            login.revoked_at = utcnow()
        session.commit()
    assert post(client, "/api/products/legal/start", command).status_code == 401


def test_queue_failure_rolls_back_the_entire_start_and_retry_recovers(signed, monkeypatch):
    client, service, _, _ = signed
    command = request()
    def unavailable(*args):
        raise RuntimeError("fixture queue failure")
    with monkeypatch.context() as patch:
        patch.setattr(start, "enqueue", unavailable)
        with pytest.raises(RuntimeError, match="fixture queue failure"):
            post(client, "/api/products/pharma/start", command)
    with service.db.session() as session:
        for table in (ProductDossier, LegalMonitoringProfile, Investigation, WebResearchPolicy, PrivateDossierFollow, DossierEntry):
            assert session.scalar(select(func.count()).select_from(table)) == 0
    result = post(client, "/api/products/pharma/start", command)
    assert result.status_code == 202, result.text
    assert post(client, "/api/products/pharma/start", command).json() == result.json()
