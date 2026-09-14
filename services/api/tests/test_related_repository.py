"""Durable story workflow; source adapter integration is tested separately."""
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_related_contracts import NOW, fact
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import related_repository as stories
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job, OrganizationMembership, OutboxMessage
from helvetic_lens.related_models import RelatedStory, RelatedStoryRevision

db = _database_fixture
template = _template_fixture


@pytest.fixture
def events(db):
    values = [fact("warnings", 1), fact("river", 2), fact("traffic", 3)]
    with db.session() as session:
        for value in values:
            model = stories.MONITORS[value.reference.domain]
            session.add(model(id=str(value.reference.monitor_id), organization_id="org-a", owner_user_id="owner",
                request_key=str(value.reference.monitor_id), request_hash="0" * 64,
                configuration={"name": "Private fixture monitor"}, status="active"))
        session.commit()
    return values


def resolver(events, denied=None):
    def resolve(session, user_id, ref, *, now):
        value = next(item for item in events if item.reference.event_id == ref.event_id)
        if denied == ref.domain:
            raise DomainError("No source display rights", 403, "fixture_denied")
        return {"fact": value, "reference": ref.model_dump(mode="json"), "availability": "available",
            "authority": value.authority.model_dump(), "source_state": value.source_state,
            "href": f"/fixture/{ref.event_id}"}
    return resolve


def create(session, events, request="create"):
    return stories.create(session, "owner", "Flood and road evidence", [event.reference for event in events],
        request, resolve=resolver(events), now=NOW)


def test_create_split_restore_members_archive_and_history_survive_reload_without_domain_writes(db, events):
    with db.session() as session:
        row = create(session, events)
        identifier = row.id
        assert create(session, events).id == row.id
        session.commit()
    with db.session() as session:
        original = stories.view(session, "owner", identifier, resolve=resolver(events), now=NOW)
        assert original["association_state"] == "possible" and len(original["members"]) == 3
        split = stories.change(session, "owner", identifier, 1, "split", label="Flood and road evidence",
            values=[event.reference for event in events[:2]], resolve=resolver(events), now=NOW)
        assert split.version == 2
        # Replaying after the version advanced must not make another revision.
        assert stories.change(session, "owner", identifier, 1, "split", label="Flood and road evidence",
            values=[event.reference for event in events[:2]], resolve=resolver(events), now=NOW).version == 2
        merged = stories.change(session, "owner", identifier, 2, "restore-members", label="Flood and road evidence",
            values=[event.reference for event in events], resolve=resolver(events), now=NOW)
        assert merged.version == 3
        old = stories.view(session, "owner", identifier, resolve=resolver(events), now=NOW, number=2)
        assert old["historical"] and len(old["members"]) == 2 and old["action"] == "split"
        stories.change(session, "owner", identifier, 3, "archive", action="archive", resolve=resolver(events), now=NOW)
        assert stories.listing(session, "owner")["items"] == []
        assert stories.listing(session, "owner", archived=True)["items"][0]["id"] == identifier
        stories.change(session, "owner", identifier, 4, "unarchive", action="restore", resolve=resolver(events), now=NOW)
        actions = stories.history(session, "owner", identifier)["items"]
        assert [entry["action"] for entry in actions] == ["restore", "archive", "merge", "split", "create"]
        assert stories.history(session, "owner", identifier, before=4, limit=2)["next"] == 2
        for event in events:
            assert session.get(stories.MONITORS[event.reference.domain], str(event.reference.monitor_id)).version == 1
        for model in (Job, OutboxMessage):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        session.commit()


def test_correction_revocation_and_expired_geography_redact_proofs_in_current_and_historical_reads(db, events):
    with db.session() as session:
        row = create(session, events)
        session.commit()
        value = stories.view(session, "owner", row.id, resolve=resolver(events, "traffic"), now=NOW)
        assert value["association_state"] == "unverified" and value["links"] == []
        denied = next(member for member in value["members"] if member["reference"]["domain"] == "traffic")
        assert denied["href"] is None and "authority" not in denied and "source_state" not in denied
        expired = stories.view(session, "owner", row.id, resolve=resolver(events), now=NOW + timedelta(days=2))
        assert expired["association_state"] == "unverified"
        corrected = events[2].model_copy(update={"reference": events[2].reference.model_copy(update={"revision": 2, "evidence_hash": "e" * 64})})
        changed = [*events[:2], corrected]
        old = stories.view(session, "owner", row.id, resolve=resolver(changed), now=NOW)
        assert old["links"] == [] and old["association_state"] == "unverified"
        stories.change(session, "owner", row.id, 1, "correction", label=row.title,
            values=[event.reference for event in changed], resolve=resolver(changed), now=NOW)
        assert stories.view(session, "owner", row.id, resolve=resolver(changed), now=NOW)["association_state"] == "possible"
        assert stories.view(session, "owner", row.id, resolve=resolver(changed), now=NOW, number=1)["association_state"] == "unverified"


def test_splitting_to_one_preserves_source_and_can_be_reversed(db, events):
    with db.session() as session:
        row = create(session, events)
        stories.change(session, "owner", row.id, 1, "split-one", label=row.title,
            values=[events[0].reference], resolve=resolver(events), now=NOW)
        assert stories.view(session, "owner", row.id, resolve=resolver(events), now=NOW)["association_state"] == "separate"
        stories.change(session, "owner", row.id, 2, "restore-three", label=row.title,
            values=[event.reference for event in events], resolve=resolver(events), now=NOW)
        assert stories.view(session, "owner", row.id, resolve=resolver(events), now=NOW)["association_state"] == "possible"


def test_foreign_owner_role_revocation_and_cursors_are_private(db, events):
    with db.session() as session:
        row = create(session, events)
        session.commit()
        for user in ("peer", "viewer"):
            assert stories.listing(session, user)["items"] == []
            with pytest.raises(DomainError) as error:
                stories.view(session, user, row.id, resolve=resolver(events), now=NOW)
            assert error.value.status == 404
            with pytest.raises(DomainError):
                stories.listing(session, user, after=row.id)
            with pytest.raises(DomainError):
                stories.create(session, user, "Foreign", [event.reference for event in events], "foreign", resolve=resolver(events), now=NOW)
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner",
            OrganizationMembership.organization_id == "org-a"))
        session.commit()
        with pytest.raises(DomainError) as error:
            stories.view(session, "owner", row.id, resolve=resolver(events), now=NOW)
        assert error.value.status == 403


def test_incompatible_geography_stale_versions_and_request_reuse_do_not_mutate(db, events):
    with db.session() as session:
        row = create(session, events)
        with pytest.raises(DomainError):
            stories.create(session, "owner", "Changed title", [event.reference for event in events], "create", resolve=resolver(events), now=NOW)
        unrelated = events[2].model_copy(update={"place": events[2].place.model_copy(update={"place_id": "2771"})})
        with pytest.raises(DomainError) as error:
            stories.change(session, "owner", row.id, 1, "wrong-location", label=row.title,
                values=[event.reference for event in events], resolve=resolver([*events[:2], unrelated]), now=NOW)
        assert error.value.code == "related_association_unverified"
        with pytest.raises(DomainError):
            stories.change(session, "owner", row.id, 2, "stale", label=row.title,
                values=[event.reference for event in events], resolve=resolver(events), now=NOW)
        assert session.scalar(select(func.count()).select_from(RelatedStoryRevision)) == 1
        assert session.get(RelatedStory, row.id).version == 1
        session.rollback()
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RelatedStory)) == 0
