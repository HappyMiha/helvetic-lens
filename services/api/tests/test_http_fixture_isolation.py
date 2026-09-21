"""Schema reuse must retain independent data and real foreign-key enforcement."""

import hashlib
import shutil

import pytest
from conftest import LAW_URL, FakeFetcher, ScriptedModel, add_law, policy
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from helvetic_lens.main import create_app


def test_schema_copies_keep_writes_fetchers_and_foreign_keys_private(harness, migrated_schema, tmp_path):
    client, fetcher, service, model = harness
    template_hash = hashlib.sha256(migrated_schema.read_bytes()).digest()
    first = add_law(client)
    fetcher.values[LAW_URL] = policy(99)
    model.fail = True

    second_path = tmp_path / "second.db"
    shutil.copyfile(migrated_schema, second_path)
    settings = service.settings.model_copy(deep=True, update={
        "database_url": "sqlite:///" + second_path.as_posix(),
        "data_dir": tmp_path / "second-data",
    })
    second_fetcher, second_model = FakeFetcher(), ScriptedModel()
    app = create_app(settings, fetcher=second_fetcher, model_client=second_model)
    with TestClient(app) as second:
        assert second.get("/api/laws").json() == []
        assert second.get("/api/laws/" + first["id"]).status_code == 404
        other = add_law(second)
        assert other["id"] != first["id"]
        assert second_fetcher.values[LAW_URL] == policy(30)
        assert second_model.fail is False
        assert [law["id"] for law in client.get("/api/laws").json()] == [first["id"]]
        assert client.get("/api/laws/" + other["id"]).status_code == 404

        with app.state.service.db.session() as session:
            assert session.scalar(text("PRAGMA foreign_keys")) == 1
            with pytest.raises(IntegrityError):
                session.execute(text("UPDATE document_watches SET organization_id = 'absent-organization'"))
            session.rollback()
        assert second.get("/api/laws/" + other["id"]).status_code == 200

    assert hashlib.sha256(migrated_schema.read_bytes()).digest() == template_hash
