"""Account-wide dossier capacity and real durable approval-email dispatch."""
import asyncio
from uuid import uuid4

from sqlalchemy import select
from test_legal_profiles import config
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.models import Job, User
from helvetic_lens.product_models import DossierLimitRequest, ProductDossier


def test_shared_dossiers_email_approval_and_alternative_limit(signed, monkeypatch):
    client, service, identity, _ = signed
    roots = ["/api/products/legal", "/api/products/pharma"]
    dossiers = []
    for index in range(3):
        command = {"creation_key": str(uuid4()), "config": config()}
        result = post(client, roots[index % 2] + "/dossiers", command)
        assert result.status_code == 201, result.text
        dossiers.append(result.json())
        assert post(client, roots[index % 2] + "/dossiers", command).json()["id"] == result.json()["id"]
    assert all(client.get(root + "/research-allowance").json()["remaining"] == 0 for root in roots)
    command = {"request_key": str(uuid4()), "question": "A fourth independent research dossier", "public_query_confirmed": True}
    assert post(client, roots[1] + "/explore", command).status_code == 429
    # Research in an existing dossier remains available and consumes no place.
    result = post(client, roots[0] + "/dossiers/" + dossiers[0]["id"] + "/investigations", command)
    assert result.status_code == 202, result.text
    increase = {"request_key": str(uuid4()), "requested_limit": 8,
        "reason": "Compare several projects <script>untrusted</script>"}
    response = post(client, roots[1] + "/dossier-limit-requests", increase)
    assert response.status_code == 202, response.text
    request = response.json()
    assert post(client, roots[0] + "/dossier-limit-requests", increase).json()["id"] == request["id"]
    assert post(client, roots[0] + "/dossier-limit-requests", {**increase, "request_key": str(uuid4())}).status_code == 409
    review = roots[0] + "/dossier-limit-requests/" + request["id"]
    decision = {"expected_revision": 1, "action": "approve", "limit": 6}
    assert client.get(review).status_code == 403
    assert post(client, review + "/decision", decision).status_code == 403
    sent = []

    def send(_self, recipient, subject, body, html, *args, **kwargs):
        sent.append((recipient, subject, body, html))
        return "smtp"

    monkeypatch.setattr(AuthMailer, "send_message", send)
    with service.db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "dossier_limit_email"))
        job_id = job.id
        session.get(User, identity["user"]["id"]).platform_admin = True
        session.commit()
    asyncio.run(service.execute_job(job_id))
    assert len(sent) == 1 and sent[0][0] == "info@helveticlens.ch"
    assert "action=approve" in sent[0][2] and "action=reject" in sent[0][2] and "action=adjust" in sent[0][2]
    assert "<script>" not in sent[0][3] and "&lt;script&gt;" in sent[0][3]
    # GET/email prefetch is read-only, and mail replay does not send twice.
    assert client.get(review).json()["status"] == "pending"
    asyncio.run(service.execute_job(job_id))
    assert len(sent) == 1
    approved = post(client, review + "/decision", decision)
    assert approved.status_code == 200 and approved.json()["approved_limit"] == 6, approved.text
    assert post(client, review + "/decision", decision).status_code == 200
    assert post(client, review + "/decision", {**decision, "limit": 8}).status_code == 409
    assert all(client.get(root + "/research-allowance").json()["limit"] == 6 for root in roots)
    assert post(client, roots[1] + "/explore", command).status_code == 202
    with service.db.session() as session:
        assert session.get(DossierLimitRequest, request["id"]).decided_by_user_id == identity["user"]["id"]
        session.delete(session.get(ProductDossier, dossiers[2]["id"]))
        session.commit()
    assert client.get(roots[0] + "/research-allowance").json()["used"] == 3


def test_request_rejection_leaves_limit_unchanged_and_requires_current_revision(signed):
    client, service, identity, _ = signed
    root = "/api/products/pharma"
    request = post(client, root + "/dossier-limit-requests", {"request_key": str(uuid4()),
        "requested_limit": 5, "reason": "I need two more independent projects."}).json()
    with service.db.session() as session:
        session.get(User, identity["user"]["id"]).platform_admin = True
        session.commit()
    route = root + "/dossier-limit-requests/" + request["id"] + "/decision"
    assert post(client, route, {"expected_revision": 9, "action": "reject"}).status_code == 409
    assert post(client, route, {"expected_revision": 1, "action": "reject"}).json()["status"] == "rejected"
    assert client.get(root + "/research-allowance").json()["limit"] == 3
