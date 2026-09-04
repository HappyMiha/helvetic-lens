import json
from datetime import UTC, datetime

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    MonitoringTopic,
    MonitoringTopicDraft,
    MonitoringTopicRevision,
    Organization,
    OrganizationMembership,
)
from helvetic_lens.regulatory_corpus import DocumentInput, EventInput, ExpressionInput, IdentifierInput


def plan(**overrides):
    result = {
        "name": "Simplified naturalisation",
        "goal": "Follow material developments about simplified naturalisation in Switzerland.",
        "concepts": ["naturalisation"],
        "synonyms": ["citizenship"],
        "exclusions": ["sport"],
        "jurisdictions": ["CH"],
        "languages": ["de", "fr", "it", "rm", "en"],
        "source_pack_ids": ["fedlex-legislation"],
        "document_kinds": ["act"],
        "event_kinds": ["amended", "new_version"],
        "importance_floor": "low",
    }
    result.update(overrides)
    return result


class TopicDraftModel:
    def __init__(self, *, invalid_first: bool = False):
        self.calls = []
        self.invalid_first = invalid_first

    async def complete(self, system, user, **kwargs):
        self.calls.append((system, user, kwargs))
        if self.invalid_first and len(self.calls) == 1:
            return "not json"
        return json.dumps(plan(name="AI-proposed naturalisation watch"))


def add_candidate(service, *, title="Naturalisation Act amendment", stream="rss-de"):
    key = stream.replace("/", "-")
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="act",
                authority="fedlex",
                identifiers=(IdentifierInput("eli", f"https://fedlex.data.admin.ch/eli/cc/topic-{key}"),),
                title=title,
                expression=ExpressionInput(language="de", key=f"topic-{key}:de", title=title),
                metadata={"jurisdiction": "CH"},
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=merged.work.id,
                expression_id=merged.expression.id,
                authority="fedlex",
                event_type="amended",
                detected_at=datetime.now(UTC),
                provenance_method="official_metadata",
                source_url=f"https://fedlex.data.admin.ch/eli/cc/topic-{key}",
                evidence={"stream": stream, "language": "de"},
                external_key=f"topic:{key}",
                connector="fedlex",
                connector_health="healthy",
                impact="medium",
            ),
        )
        session.commit()
        return event.id


def test_manual_topic_creation_is_idempotent_and_revisions_are_immutable(harness):
    client, _, service, _ = harness
    payload = {**plan(), "idempotency_key": "topic-create-0001"}
    created = client.post("/api/monitoring-topics", json=payload)
    assert created.status_code == 201, created.text
    topic = created.json()
    assert topic["status"] == "active" and topic["current_revision"] == 1
    assert topic["plan"]["ai_assisted"] is False
    repeated = client.post("/api/monitoring-topics", json=payload)
    assert repeated.status_code == 201 and repeated.json()["id"] == topic["id"]
    assert repeated.json()["reused"] is True

    updated = client.put(
        f"/api/monitoring-topics/{topic['id']}",
        json={**plan(synonyms=["citizenship", "Einbürgerung"]), "expected_revision": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["current_revision"] == 2
    assert len(updated.json()["revisions"]) == 2
    assert updated.json()["revisions"][1]["synonyms"] == ["citizenship"]
    conflict = client.put(
        f"/api/monitoring-topics/{topic['id']}",
        json={**plan(), "expected_revision": 1},
    )
    assert conflict.status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 1
        assert session.scalar(select(func.count()).select_from(MonitoringTopicRevision)) == 2


def test_ai_draft_is_repaired_previewed_and_only_recorded_after_confirmation(harness):
    client, _, service, _ = harness
    model = TopicDraftModel(invalid_first=True)
    service.model_client = model

    response = client.post(
        "/api/monitoring-topics/draft",
        json={"goal": plan()["goal"], "locale": "en-CH"},
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["requires_confirmation"] is True
    assert draft["plan"]["name"] == "AI-proposed naturalisation watch"
    assert len(model.calls) == 2
    with service.db.session() as session:
        stored = session.get(MonitoringTopicDraft, draft["id"])
        assert stored is not None and stored.used_at is None
        assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 0

    previewed = client.post("/api/monitoring-topics/preview", json=draft["plan"])
    assert previewed.status_code == 200
    confirmed = client.post(
        "/api/monitoring-topics",
        json={
            **draft["plan"],
            "idempotency_key": "ai-topic-create-0001",
            "ai_draft_id": draft["id"],
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["plan"]["ai_assisted"] is True
    assert confirmed.json()["plan"]["ai_model"]
    with service.db.session() as session:
        assert session.get(MonitoringTopicDraft, draft["id"]).used_at is not None


def test_preview_is_bounded_explained_and_never_claims_a_legal_relation(harness):
    client, _, service, _ = harness
    matching_id = add_candidate(service)
    add_candidate(service, title="Unrelated sport act", stream="rss-fr")
    response = client.post("/api/monitoring-topics/preview", json=plan())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scanned_event_limit"] == 500
    assert result["representative_limit"] == 10
    assert result["candidate_count"] == 1
    assert result["items"][0]["event_id"] == matching_id
    assert result["items"][0]["match_type"] == "topic_candidate"
    assert result["items"][0]["legal_relation_confirmed"] is False
    assert {item["type"] for item in result["items"][0]["reason_signals"]} >= {
        "concept",
        "source_pack",
    }


def test_pause_resume_and_archive_are_revisioned_and_archival_is_soft(harness):
    client, *_ = harness
    topic = client.post(
        "/api/monitoring-topics",
        json={**plan(), "idempotency_key": "topic-status-0001"},
    ).json()
    for revision, status in [(1, "paused"), (2, "active"), (3, "archived")]:
        changed = client.patch(
            f"/api/monitoring-topics/{topic['id']}/status",
            json={"status": status, "expected_revision": revision},
        )
        assert changed.status_code == 200, changed.text
        topic = changed.json()
        assert topic["status"] == status
        assert topic["current_revision"] == revision + 1
    assert client.get("/api/monitoring-topics").json() == []
    archived = client.get("/api/monitoring-topics?include_archived=true").json()
    assert len(archived) == 1 and archived[0]["archived_at"]
    detail = client.get(f"/api/monitoring-topics/{topic['id']}").json()
    assert [item["status"] for item in reversed(detail["revisions"])] == [
        "active",
        "paused",
        "active",
        "archived",
    ]


def test_topic_rows_are_organization_isolated(harness):
    client, _, service, _ = harness
    created = client.post(
        "/api/monitoring-topics",
        json={**plan(), "idempotency_key": "topic-tenant-0001"},
    ).json()
    with service.db.session(include_all_organizations=True) as session:
        second = Organization(name="Second topic organization", slug="second-topic-organization")
        session.add(second)
        session.commit()
    with service.db.organization_context(second.id):
        assert service.monitoring_topics() == []
        try:
            service.monitoring_topic(created["id"])
        except Exception as error:
            assert getattr(error, "status", None) == 404
        else:
            raise AssertionError("Another organization read the topic")


def auth_settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "topics-auth.db").as_posix(),
        data_dir=tmp_path / "topics-auth-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
    )


def test_viewer_can_inspect_but_cannot_create_or_change_topics(tmp_path):
    app = create_app(auth_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "email": "topic-viewer@example.ch",
                "password": "correct horse battery staple",
                "name": "Topic Viewer",
                "organization_name": "Topic viewer organization",
            },
        ).json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == registered["user"]["id"]
                )
            )
            membership.role = "viewer"
            session.commit()
        headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}
        assert client.get("/api/monitoring-topics").status_code == 200
        blocked_draft = client.post(
            "/api/monitoring-topics/draft",
            json={"goal": "Follow naturalisation", "locale": "en-CH"},
            headers=headers,
        )
        assert blocked_draft.status_code == 403
        blocked = client.post(
            "/api/monitoring-topics",
            json={**plan(), "idempotency_key": "viewer-topic-0001"},
            headers=headers,
        )
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "viewer_read_only"
