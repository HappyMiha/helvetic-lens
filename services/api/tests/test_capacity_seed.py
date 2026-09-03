import json

from sqlalchemy import func, select

from helvetic_lens.capacity_cleanup import cleanup_capacity
from helvetic_lens.capacity_seed import seed_capacity
from helvetic_lens.config import Settings
from helvetic_lens.db import Database
from helvetic_lens.models import Comparison, DocumentWatch, Organization, User, Version


def test_capacity_seed_is_idempotent_and_never_exports_the_password(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "capacity.db").as_posix(),
        data_dir=tmp_path / "capacity-data",
        app_environment="test",
        allow_anonymous_dev=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
    )
    db = Database(settings)
    db.migrate()

    first = seed_capacity(
        db,
        settings,
        password="capacity-only-password",
        organizations=3,
        users_per_organization=4,
        prefix="test-capacity",
    )
    second = seed_capacity(
        db,
        settings,
        password="capacity-only-password",
        organizations=3,
        users_per_organization=4,
        prefix="test-capacity",
    )

    assert first["account_count"] == 12
    assert len(first["organizations"]) == 3
    assert "capacity-only-password" not in json.dumps(first)
    assert [item["organization_id"] for item in first["organizations"]] == [
        item["organization_id"] for item in second["organizations"]
    ]
    assert all(
        organization["accounts"][0]["role"] == "organization_admin"
        and organization["accounts"][2]["role"] == "viewer"
        for organization in first["organizations"]
    )

    with db.session(include_all_organizations=True) as session:
        assert session.scalar(
            select(func.count()).select_from(Organization).where(
                Organization.slug.like("test-capacity-%")
            )
        ) == 3
        assert session.scalar(
            select(func.count()).select_from(User).where(User.email.like("test-capacity-%"))
        ) == 12
        assert session.scalar(select(func.count()).select_from(Version)) == 6
        assert session.scalar(select(func.count()).select_from(Comparison)) == 3
        assert session.scalar(select(func.count()).select_from(DocumentWatch)) == 3
        comparisons = list(session.scalars(select(Comparison)))
        assert all(item.identity_json["status"] == "probable" for item in comparisons)
        assert all(item.diff["counts"]["modified"] >= 2 for item in comparisons)

    assert len(list((settings.storage_path / "artifacts").glob("*.html"))) == 2

    cleanup = cleanup_capacity(db, settings, prefix="test-capacity")
    assert cleanup["organizations"] == 3
    assert cleanup["users"] == 12
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(
            select(func.count()).select_from(Organization).where(
                Organization.slug.like("test-capacity-%")
            )
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(User).where(User.email.like("test-capacity-%"))
        ) == 0
    assert not list((settings.storage_path / "artifacts").glob("*.html"))
