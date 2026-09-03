from alembic.config import Config
from conftest import LAW_URL, FakeFetcher, ScriptedModel, policy
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from helvetic_lens import jobs as durable_jobs
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app

ORG_A = "10000000-0000-0000-0000-000000000001"
ORG_B = "20000000-0000-0000-0000-000000000002"
FEDLEX_URL = "https://fedlex.data.admin.ch/eli/cc/2026/1"


def _settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "organizations.db").as_posix(),
        data_dir=tmp_path / "organization-data",
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
        allow_private_sources=False,
    )


def test_private_records_are_hidden_and_public_fedlex_artifacts_are_reused(tmp_path):
    settings = _settings(tmp_path)
    fetcher = FakeFetcher()
    fetcher.values[FEDLEX_URL] = policy()
    app_a = create_app(
        settings,
        fetcher=fetcher,
        model_client=ScriptedModel(),
        organization_id=ORG_A,
        organization_name="Organization A",
    )
    app_b = create_app(
        settings,
        fetcher=fetcher,
        model_client=ScriptedModel(),
        organization_id=ORG_B,
        organization_name="Organization B",
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        private_law = client_a.post(
            "/api/laws", json={"url": LAW_URL, "synthetic": True}
        ).json()
        private_version_id = private_law["current_version"]["id"]
        private_work = client_a.get("/api/corpus/works").json()[0]
        assert client_b.get(f"/api/corpus/works/{private_work['id']}").status_code == 404
        assert client_b.get("/api/corpus/works").json() == []
        old = client_a.post(
            f"/api/laws/{private_law['id']}/import",
            files={"file": ("private-old.html", policy(10), "text/html")},
            data={"synthetic": "true", "declared_date": "2025-01-01"},
        ).json()["version"]
        comparison = client_a.post(
            "/api/comparisons",
            json={"old_version_id": old["id"], "new_version_id": private_version_id},
        ).json()
        assert client_b.get(f"/api/laws/{private_law['id']}").status_code == 404
        assert client_b.get(f"/api/versions/{private_version_id}").status_code == 404
        assert client_b.get(f"/api/comparisons/{comparison['id']}").status_code == 404
        assert client_b.get(f"/api/comparisons/{comparison['id']}/ai-history").status_code == 404
        assert client_b.get("/api/search", params={"q": "Synthetic retention"}).status_code == 404
        assert client_b.get(f"/api/exports/{private_law['id']}").status_code == 404
        assert client_b.get("/api/laws").json() == []

        source = client_a.post(
            "/api/sources", json={"url": "https://regulator.example/laws/"}
        ).json()
        assert client_b.get("/api/sources").json() == []
        assert client_b.delete(f"/api/sources/{source['id']}").status_code == 404

        app_a.state.service.integration_logger.record(
            provider="test",
            operation="private diagnostic",
            method="POST",
            url="https://provider.example/completions",
            status="success",
            duration_ms=1,
        )
        log = client_a.get("/api/integration-logs").json()["items"][0]
        assert client_b.get("/api/integration-logs").json()["items"] == []
        assert client_b.get(f"/api/integration-logs/{log['id']}").status_code == 404
        assert client_b.delete("/api/integration-logs").json()["deleted"] == 0
        assert client_a.get(f"/api/integration-logs/{log['id']}").status_code == 200

        with app_a.state.service.db.session() as session:
            job, _ = durable_jobs.enqueue(
                session,
                job_type="test",
                target_type="private",
                target_id=private_law["id"],
                queue="maintenance",
                idempotency_key="organization-isolation",
            )
            session.commit()
            job_id = job.id
        assert client_b.get(f"/api/jobs/{job_id}").status_code == 404
        assert client_b.get("/api/jobs").json() == []

        client_a.patch(
            "/api/profile",
            json={"name": "A profile", "description": "Private", "business_areas": ["Legal"]},
        )
        assert client_b.get("/api/profile").json()["name"] == "My company"

        shared_a = client_a.post("/api/laws", json={"url": FEDLEX_URL}).json()
        calls_after_first_fetch = len([call for call in fetcher.calls if call[0] == FEDLEX_URL])
        shared_b = client_b.post("/api/laws", json={"url": FEDLEX_URL}).json()
        assert shared_b["id"] == shared_a["id"]
        assert shared_b["current_version"]["id"] == shared_a["current_version"]["id"]
        assert shared_a["corpus_scope"] == shared_b["corpus_scope"] == "shared_public"
        assert len([call for call in fetcher.calls if call[0] == FEDLEX_URL]) == calls_after_first_fetch

        imported = client_a.post(
            f"/api/laws/{shared_a['id']}/import",
            files={"file": ("private-baseline.html", policy(10), "text/html")},
            data={"synthetic": "true", "declared_date": "2025-01-01"},
        )
        assert imported.status_code == 200, imported.text
        private_baseline_id = imported.json()["version"]["id"]
        assert private_baseline_id in {
            item["id"] for item in client_a.get(f"/api/laws/{shared_a['id']}").json()["versions"]
        }
        assert private_baseline_id not in {
            item["id"] for item in client_b.get(f"/api/laws/{shared_b['id']}").json()["versions"]
        }
        assert client_b.get(f"/api/versions/{private_baseline_id}").status_code == 404

        removed = client_a.delete(f"/api/laws/{shared_a['id']}").json()
        assert removed["shared_corpus_retained"] is True
        assert client_a.get(f"/api/laws/{shared_a['id']}").status_code == 404
        assert client_b.get(f"/api/laws/{shared_b['id']}").status_code == 200


def test_legacy_migration_preserves_evidence_comparison_and_history_ids(tmp_path):
    database_path = tmp_path / "legacy.db"
    engine = create_engine("sqlite:///" + database_path.as_posix())
    config = Config("services/api/alembic.ini")
    config.set_main_option("script_location", "services/api/alembic")
    law_id = "30000000-0000-0000-0000-000000000003"
    old_id = "30000000-0000-0000-0000-000000000004"
    new_id = "30000000-0000-0000-0000-000000000005"
    comparison_id = "30000000-0000-0000-0000-000000000006"
    ask_id = "30000000-0000-0000-0000-000000000007"
    artifact_key = "a" * 64 + ".html"
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a21f8c4d9b10")
        connection.execute(
            text(
                "INSERT INTO laws (id, name, url, provider, active, created_at, last_result) "
                "VALUES (:id, 'Legacy law', :url, 'native', 1, CURRENT_TIMESTAMP, 'changed')"
            ),
            {"id": law_id, "url": LAW_URL},
        )
        for version_id, content_hash in ((old_id, "b" * 64), (new_id, "c" * 64)):
            connection.execute(
                text(
                    "INSERT INTO versions "
                    "(id, law_id, title, content_hash, extractor, text, passages, content_type, "
                    "artifact_key, filename, origin, synthetic, identity_json, created_at) VALUES "
                    "(:id, :law, 'Legacy', :hash, 'html', 'text', '[]', 'text/html', :artifact, "
                    "'law.html', 'uploaded', 0, '{}', CURRENT_TIMESTAMP)"
                ),
                {"id": version_id, "law": law_id, "hash": content_hash, "artifact": artifact_key},
            )
        connection.execute(
            text(
                "INSERT INTO comparisons "
                "(id, law_id, old_version_id, new_version_id, mode, diff, identity_json, created_at) "
                "VALUES (:id, :law, :old, :new, 'saved_versions', '{}', '{}', CURRENT_TIMESTAMP)"
            ),
            {"id": comparison_id, "law": law_id, "old": old_id, "new": new_id},
        )
        connection.execute(
            text(
                "INSERT INTO ask_records "
                "(id, comparison_id, cache_key, question, history, status, result, coverage, "
                "provenance, model, prompt_revision, context_mode, use_count, created_at) VALUES "
                "(:id, :comparison, :cache, 'What changed?', '[]', 'succeeded', '{}', '{}', '{}', "
                "'local', 1, 'automatic', 1, CURRENT_TIMESTAMP)"
            ),
            {"id": ask_id, "comparison": comparison_id, "cache": "d" * 64},
        )
        command.upgrade(config, "head")

        assert connection.scalar(text("SELECT id FROM laws WHERE id=:id"), {"id": law_id}) == law_id
        assert connection.scalar(
            text("SELECT artifact_key FROM versions WHERE id=:id"), {"id": old_id}
        ) == artifact_key
        pair = connection.execute(
            text("SELECT old_version_id, new_version_id FROM comparisons WHERE id=:id"),
            {"id": comparison_id},
        ).one()
        assert tuple(pair) == (old_id, new_id)
        assert connection.scalar(
            text("SELECT comparison_id FROM ask_records WHERE id=:id"), {"id": ask_id}
        ) == comparison_id
        assert connection.scalar(
            text("SELECT organization_id FROM document_watches WHERE law_id=:id"), {"id": law_id}
        ) == "00000000-0000-0000-0000-000000000001"
    engine.dispose()
