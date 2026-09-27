"""Guest event reconnects and a native viewer's editor grant stay dossier-bound."""
from uuid import uuid4

from sqlalchemy import select
from test_product_contributions import submit
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_teams import managed, switch

from helvetic_lens import product_investigation_api
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierMember


def test_guest_stream_rechecks_current_role_after_authorized_batch(signed, monkeypatch):
    client, service, _, _ = signed
    account, cookies = guest(client, service)
    doc, root = managed(client)
    item = invitation(client, root, account, "CONTRIBUTOR")
    switch(client, cookies)
    accept(client, root, item)
    entry, _ = submit(client, root)
    detail = root + "/investigations/" + entry["analysis"]["id"]
    first = client.get(detail + "/events?wait=0")
    assert first.status_code == 200 and "contribution_queued" in first.text
    assert "no-store" in first.headers["cache-control"]
    original = product_investigation_api.record
    checks = []

    def checked(session, *args, **kwargs):
        result = original(session, *args, **kwargs)
        checks.append(True)
        if len(checks) == 2:
            session.delete(session.get(DossierMember, (doc["id"], account["user"]["id"])))
            session.commit()
        return result

    monkeypatch.setattr(product_investigation_api, "record", checked)
    response = client.get(detail + "/events?wait=3")
    assert response.status_code == 200 and "event: access_changed" in response.text
    assert len(checks) == 2
    assert client.get(detail + "/events?wait=0", headers={"last-event-id": "1"}).status_code == 404


def test_guest_editor_grant_works_for_native_viewer_without_workspace_privileges(signed):
    client, service, _, _ = signed
    account, cookies = guest(client, service)
    with service.db.session(include_all_organizations=True) as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"]))
        membership.role = "viewer"
        session.commit()
    _, root = managed(client)
    item = invitation(client, root, account, "EDITOR")
    switch(client, cookies)
    accept(client, root, item)
    response = post(client, root + "/investigations", {"request_key": str(uuid4()),
        "question": "Public Swiss evidence", "public_query_confirmed": True})
    assert response.status_code == 202, response.text
    run = response.json()
    control = root + "/investigations/" + run["id"] + "/control"
    paused = post(client, control, {"expected_revision": run["revision"], "action": "pause"})
    assert paused.status_code == 200, paused.text
    resumed = post(client, control, {"expected_revision": paused.json()["revision"], "action": "resume"})
    assert resumed.status_code == 200 and resumed.json()["status"] == "queued", resumed.text
    assert post(client, root + "/improve", {}).status_code == 403
    assert post(client, "/api/organization/invitations", {}).status_code == 403
