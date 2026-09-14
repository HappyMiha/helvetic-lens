"""Actual private export storage and rights revalidation, with synthetic source grants."""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_tender_repository import db as _db
from test_tender_repository import template as _template
from test_trademark_sources import NOW, accept, grant
from test_trademark_workflow import review, rows, running, source_facts, sync

from helvetic_lens import trademark_exports as exports
from helvetic_lens import trademark_sources as sources
from helvetic_lens.config import DomainError
from helvetic_lens.trademark_workflow_models import TrademarkCandidateEvent, TrademarkExportPreparation

db, template = _db, _template


def setup(db, **kwargs):
    from uuid import uuid4

    from test_trademark_matching import portfolio

    from helvetic_lens import trademark_repository as profiles
    from helvetic_lens import trademark_workflow as workflow
    permission = grant(db, export_allowed=True, private_decisions_allowed=True, **kwargs)
    accept(db, permission)
    with db.session() as session:
        monitor = profiles.create_monitor(session, "owner", portfolio().model_dump(mode="json"), str(uuid4()))["id"]
        workflow.start(session, "owner", monitor, 1, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor


def prepare(db, monitor, **kwargs):
    row = kwargs.pop("candidate", None) or rows(db, monitor, kwargs.get("now", NOW))[0]
    with db.session() as session:
        result = exports.prepare(session, kwargs.pop("user", "owner"), monitor, row["id"],
            expected_version=row["version"], expected_evaluation_hash=row.get("evaluation_hash"),
            request_key=kwargs.pop("key", "first"), now=kwargs.pop("now", NOW), **kwargs)
        session.commit()
        return result


def read(db, monitor, prepared, *, download=False, now=NOW, user="owner", candidate=None, digest=None):
    row = candidate or rows(db, monitor, now)[0]
    with db.session() as session:
        result = exports.read(session, user, monitor, row["id"], prepared["id"], now=now,
            download_hash=(digest or prepared["content_sha256"]) if download else None)
        session.commit()
        return result


def test_prepare_preview_explicit_download_keep_references_not_payloads(db):
    _, monitor = setup(db)
    prepared = prepare(db, monitor)
    assert prepared == prepare(db, monitor)
    assert prepared["verification_required"]
    assert "Synthetic Owner AG" in prepared["document"] and "Verify the legal deadline" in prepared["document"]
    assert hashlib.sha256(prepared["document"].encode()).hexdigest() == prepared["content_sha256"]
    with db.session() as session:
        row = session.get(TrademarkExportPreparation, prepared["id"])
        assert row.downloaded_at is None and not hasattr(row, "document")
        assert "Synthetic" not in str({c.name:getattr(row,c.name) for c in row.__table__.columns})
    assert read(db, monitor, prepared, download=True) == prepared
    assert read(db, monitor, prepared, download=True) == prepared
    with db.session() as session:
        assert session.get(TrademarkExportPreparation, prepared["id"]).downloaded_at is not None


def test_matching_and_display_do_not_grant_export_and_preparation_cannot_bypass_revoke(db):
    _, blocked = running(db)
    with pytest.raises(DomainError, match="permission"):
        prepare(db, blocked)
    permission, monitor = setup(db, source_key="export-fixture")
    prepared = prepare(db, monitor)
    candidate = rows(db, monitor)[0]
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    for download in (False, True):
        with pytest.raises(DomainError):
            read(db, monitor, prepared, download=download, candidate=candidate)


def test_foreign_candidate_or_member_cannot_read_preparation(db):
    _, monitor = setup(db)
    prepared = prepare(db, monitor)
    candidate = rows(db, monitor)[0]
    with pytest.raises(DomainError):
        read(db, monitor, prepared, user="peer", candidate=candidate)
    _, other = setup(db, source_key="other-export")
    with pytest.raises(DomainError):
        read(db, other, prepared)
    with db.organization_context("org-b"), db.session() as session:
        assert not list(session.scalars(select(TrademarkExportPreparation)))


def test_version_source_change_expiry_hash_and_request_reuse_are_checked(db):
    permission, monitor = setup(db)
    prepared = prepare(db, monitor)
    with pytest.raises(DomainError):
        prepare(db, monitor, locale="de-CH")
    with pytest.raises(DomainError):
        read(db, monitor, prepared, download=True, digest="b"*64)
    with pytest.raises(DomainError) as expired:
        read(db, monitor, prepared, now=NOW+timedelta(minutes=15))
    assert expired.value.code == "trademark_export_expired"
    review(db, monitor)
    with pytest.raises(DomainError):
        read(db, monitor, prepared, download=True)
    second = prepare(db, monitor, key="second")
    accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
    with pytest.raises(DomainError):
        read(db, monitor, second, download=True, now=NOW+timedelta(seconds=1))
    sync(db, monitor, NOW+timedelta(seconds=1))
    with pytest.raises(DomainError):
        read(db, monitor, second, download=True, now=NOW+timedelta(seconds=1))


def test_selected_change_includes_before_after_and_redacts_nothing_silently(db):
    permission, monitor = setup(db)
    accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
    later = NOW+timedelta(seconds=1)
    sync(db, monitor, later)
    with db.session() as session:
        event = session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.sequence==2))
        event_id, previous_id = event.id, event.previous_revision_id
    prepared = prepare(db, monitor, event_id=event_id, now=later)
    assert "Synthetic Owner AG" in prepared["document"] and "Changed Owner AG" in prepared["document"]
    from helvetic_lens.trademark_source_models import TrademarkRegisterRevision
    with db.session() as session:
        session.get(TrademarkRegisterRevision, previous_id).normalized_payload = None
        session.commit()
    with pytest.raises(DomainError):
        read(db, monitor, prepared, download=True, now=later)
    current_only = prepare(db, monitor, key="current-only", now=later)
    assert "Changed Owner AG" in current_only["document"] and "Synthetic Owner AG" not in current_only["document"]


@pytest.mark.parametrize("locale", sorted(exports.LOCALES))
def test_localized_offline_document_escapes_markup_and_has_no_active_content(db, locale):
    permission, monitor = setup(db)
    accept(db, permission, cursor=1, facts=source_facts(owners=['<script>alert("owned")</script>']))
    later = NOW+timedelta(seconds=1)
    sync(db, monitor, later)
    document = prepare(db, monitor, now=later, locale=locale)["document"]
    assert f'lang="{locale}"' in document and '<script>' not in document
    assert '&lt;script&gt;' in document and "default-src 'none'" in document
    assert '<iframe' not in document and '<img' not in document and '<form' not in document


def test_preparation_capacity_and_old_expiry_allow_new_packet(db, monkeypatch):
    permission, monitor = setup(db)
    monkeypatch.setattr(exports, "MAX_PREPARATIONS", 1)
    prepare(db, monitor)
    with pytest.raises(DomainError) as full:
        prepare(db, monitor, key="second")
    assert full.value.code == "trademark_export_capacity"
    later = NOW+timedelta(minutes=16)
    accept(db, permission, cursor=1, second=16*60)
    sync(db, monitor, later)
    assert prepare(db, monitor, key="fresh", now=later)


def test_new_source_export_rights_do_not_authorize_prior_permission_versions(db):
    _, monitor = running(db)
    permission = grant(db, generation=1, export_allowed=True, private_decisions_allowed=True)
    accept(db, permission, generation=2, facts=source_facts(owners=["New permitted holder"]))
    sync(db, monitor)
    with db.session() as session:
        event = session.scalar(select(TrademarkCandidateEvent).where(TrademarkCandidateEvent.sequence==2))
        event_id = event.id
    with pytest.raises(DomainError) as denied:
        prepare(db, monitor, event_id=event_id)
    assert denied.value.code == "trademark_source_use_denied"
    current_only = prepare(db, monitor, key="current-permission-only")
    assert "New permitted holder" in current_only["document"]
