"""Isolated safety checks; never connects to the production database."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helvetic_lens import models as m
from helvetic_lens.config import Settings
from helvetic_lens.db import Base
from helvetic_lens.service import HelveticLens
from refresh_production_content import (
    CONTENT_TABLES,
    IDENTITY_TABLES,
    identity_digest,
    reset_content,
)
from sqlalchemy import func, select


class ContentRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="refresh-safety-")
        # Explicit test settings override every production environment boundary.
        settings = Settings().model_copy(
            update={
                "database_url": "sqlite:///:memory:",
                "data_dir": Path(self.directory.name),
                "app_environment": "test",
            }
        )
        self.service = HelveticLens(settings, organization_id="test-org")
        Base.metadata.create_all(self.service.db.engine)
        with self.service.db.session() as session:
            session.add(
                m.Organization(
                    id="test-org", slug="test", name="Unchanged organization"
                )
            )
            session.flush()
            session.add(
                m.User(
                    id="test-user",
                    email="test@example.invalid",
                    name="Unchanged user",
                    password_hash="unchanged-password-hash",
                    platform_admin=True,
                )
            )
            session.flush()
            session.add(
                m.OrganizationMembership(user_id="test-user", role="organization_admin")
            )
            session.add(m.Source(name="Old content", url="https://example.invalid"))
            session.commit()

    def tearDown(self):
        self.service.db.engine.dispose()
        self.directory.cleanup()

    def reset(self, **overrides):
        args = {
            "organization_id": "test-org",
            "expected_users": 1,
            "backup_id": "20260905T000000Z",
        }
        args.update(overrides)
        return reset_content(self.service, **args)

    def test_protected_tables_never_in_delete_allowlist(self):
        self.assertFalse(CONTENT_TABLES.intersection(IDENTITY_TABLES))

    def test_preserves_accounts_and_deletes_only_content(self):
        with self.service.db.session() as session:
            before = identity_digest(session)
        result = self.reset()
        self.assertEqual(result["deleted"]["sources"], 1)
        self.assertEqual(result["artifact_files_deleted"], 0)
        with self.service.db.session() as session:
            self.assertEqual(identity_digest(session), before)
            self.assertEqual(
                session.get(m.User, "test-user").password_hash,
                "unchanged-password-hash",
            )

    def test_refuses_changed_account_count(self):
        with self.assertRaisesRegex(ValueError, "scope changed"):
            self.reset(expected_users=2)

    def test_refuses_different_tenant(self):
        with self.assertRaisesRegex(ValueError, "scope changed"):
            self.reset(organization_id="other-org")

    def test_refuses_missing_backup_reference(self):
        with self.assertRaisesRegex(ValueError, "backup ID"):
            self.reset(backup_id=None)

    def test_refuses_running_work(self):
        with self.service.db.session() as session:
            session.add(
                m.Job(
                    type="scan",
                    target_type="scan",
                    target_id="test-target",
                    queue="ingest",
                    idempotency_key="test-job",
                    state="running",
                )
            )
            session.commit()
        with self.assertRaisesRegex(ValueError, "Background jobs"):
            self.reset()

    def test_identity_invariant_failure_rolls_back_deletion(self):
        with (
            patch(
                "refresh_production_content.identity_digest",
                side_effect=["before", "changed"],
            ),
            self.assertRaisesRegex(RuntimeError, "rolling back"),
        ):
            self.reset()
        with self.service.db.session() as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(m.Source)), 1
            )


if __name__ == "__main__":
    unittest.main()
