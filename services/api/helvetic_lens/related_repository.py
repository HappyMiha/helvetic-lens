"""Private story references. Caller owns transaction; resolver is server supplied.

Grouping never changes a domain event, review, consent or delivery record.
Source facts are resolved afresh and are never copied into story snapshots.
"""
import json
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .hazard_models import HazardMonitor
from .monitoring_subjects import _actor, _savepoint
from .related_contracts import MAX_MEMBERS, EventReference, fingerprint, story_associations
from .related_models import RelatedStory, RelatedStoryRevision
from .river_models import RiverMonitor
from .road_models import RoadMonitor

MONITORS = {"warnings": HazardMonitor, "river": RiverMonitor, "traffic": RoadMonitor}
MAX_STORIES = 1000
MAX_REVISIONS = 500


def fail(code, status=409):
    raise DomainError("Reload the related events and check their source evidence.", status, code)


def clock(now):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware story clock")
    return now.astimezone(UTC)


def key(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 100 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        fail("related_request_invalid", 422)
    return value


def title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200 or any(ord(c) < 32 for c in value):
        fail("related_title_invalid", 422)
    return value.strip()


def references(values, *, minimum=2):
    if not isinstance(values, (list, tuple)) or not minimum <= len(values) <= MAX_MEMBERS:
        fail("related_members_invalid", 422)
    try:
        refs = tuple(EventReference.model_validate_json(value.model_dump_json() if isinstance(value, EventReference)
            else json.dumps(value)) for value in values)
    except (ValidationError, ValueError, TypeError):
        fail("related_members_invalid", 422)
    if len({(r.domain, r.monitor_id, r.event_id) for r in refs}) != len(refs):
        fail("related_duplicate_member", 422)
    return tuple(sorted(refs, key=lambda ref: ref.model_dump_json()))


def owned(session, user_id, story_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(select(RelatedStory).where(RelatedStory.id == story_id,
        RelatedStory.organization_id == organization, RelatedStory.owner_user_id == user_id)
        .execution_options(populate_existing=True))
    if row is None:
        fail("related_story_not_found", 404)
    return row


def reference_owner(session, user_id, ref):
    organization = _actor(session, user_id)
    model = MONITORS[ref.domain]
    monitor = session.scalar(select(model.id).where(model.id == str(ref.monitor_id),
        model.organization_id == organization, model.owner_user_id == user_id))
    if monitor is None:
        fail("related_event_not_found", 404)


def revision(session, row, number=None):
    number = row.version if number is None else number
    saved = session.scalar(select(RelatedStoryRevision).where(RelatedStoryRevision.story_id == row.id,
        RelatedStoryRevision.organization_id == row.organization_id, RelatedStoryRevision.revision == number))
    if saved is None:
        fail("related_revision_not_found", 404)
    if fingerprint(saved.snapshot) != saved.fingerprint:
        fail("related_revision_invalid", 503)
    previous = session.scalar(select(RelatedStoryRevision.fingerprint).where(RelatedStoryRevision.story_id == row.id,
        RelatedStoryRevision.organization_id == row.organization_id, RelatedStoryRevision.revision == number - 1))
    if saved.previous_fingerprint != previous or (number > 1 and previous is None):
        fail("related_revision_chain_invalid", 503)
    return saved


def resolve_members(session, user_id, refs, *, resolve, now, required=False):
    members = []
    for ref in refs:
        try:
            reference_owner(session, user_id, ref)
            member = resolve(session, user_id, ref, now=now)
            fact = member.get("fact")
            if fact is not None and fact.reference != ref:
                fail("related_event_changed")
            if required and (fact is None or fact.availability != "available"):
                fail("related_evidence_unavailable")
        except DomainError:
            if required:
                raise
            # The owner can retain the reference they previously saved, but no
            # title, location, authority details or link survives failed access.
            member = {"reference": ref.model_dump(mode="json"), "fact": None,
                      "availability": "unavailable", "href": None}
        members.append(member)
    return members


def snapshot(session, user_id, label, refs, *, resolve, now):
    members = resolve_members(session, user_id, refs, resolve=resolve, now=now, required=True)
    try:
        links = story_associations(tuple(member["fact"] for member in members), now=now) if len(refs) > 1 else ()
    except ValueError:
        fail("related_members_invalid", 422)
    if any(link.state != "possible" for link in links):
        fail("related_association_unverified")
    return {"title": label, "members": [ref.model_dump(mode="json") for ref in refs],
            "links": [link.model_dump(mode="json") for link in links]}


def _record(session, row, data, action, request_key, request_hash, previous, now):
    session.add(RelatedStoryRevision(story_id=row.id, organization_id=row.organization_id,
        revision=row.version, request_key=request_key, request_hash=request_hash, action=action,
        snapshot=data, fingerprint=fingerprint(data), previous_fingerprint=previous, created_at=now))
    session.flush()


def create(session, user_id, label, values, request_key, *, resolve, now=None):
    organization = _actor(session, user_id, write=True)
    now, label, request_key = clock(now), title(label), key(request_key)
    refs = references(values)
    request_hash = fingerprint({"title": label, "members": [ref.model_dump(mode="json") for ref in refs]})
    query = select(RelatedStory).where(RelatedStory.organization_id == organization,
        RelatedStory.owner_user_id == user_id, RelatedStory.request_key == request_key)
    previous = session.scalar(query)
    if previous:
        if previous.request_hash != request_hash:
            fail("related_request_conflict")
        return previous
    count = session.scalar(select(func.count()).select_from(RelatedStory).where(
        RelatedStory.organization_id == organization, RelatedStory.owner_user_id == user_id))
    if count >= MAX_STORIES:
        fail("related_story_limit")
    data = snapshot(session, user_id, label, refs, resolve=resolve, now=now)
    try:
        with _savepoint(session):
            row = RelatedStory(organization_id=organization, owner_user_id=user_id, request_key=request_key,
                request_hash=request_hash, title=label, version=1, status="active", created_at=now, updated_at=now)
            session.add(row)
            session.flush()
            _record(session, row, data, "create", request_key, request_hash, None, now)
    except IntegrityError:
        previous = session.scalar(query)
        if previous and previous.request_hash == request_hash:
            return previous
        fail("related_request_conflict")
    return row


def change(session, user_id, story_id, expected_version, request_key, *, resolve, label=None, values=None,
           action="revise", now=None):
    row = owned(session, user_id, story_id, write=True)
    now, request_key = clock(now), key(request_key)
    if type(expected_version) is not int or expected_version < 1 or action not in {"revise", "archive", "restore"}:
        fail("related_action_invalid", 422)
    if action != "revise" and (label is not None or values is not None):
        fail("related_action_invalid", 422)
    refs = references(values, minimum=1) if action == "revise" else None
    label = title(label) if action == "revise" else None
    request_hash = fingerprint({"version": expected_version, "action": action, "title": label,
        "members": [ref.model_dump(mode="json") for ref in refs] if refs else None})
    retry = session.scalar(select(RelatedStoryRevision).where(RelatedStoryRevision.story_id == row.id,
        RelatedStoryRevision.organization_id == row.organization_id, RelatedStoryRevision.request_key == request_key))
    if retry:
        if retry.request_hash != request_hash:
            fail("related_request_conflict")
        return row
    if row.version != expected_version or row.version >= MAX_REVISIONS:
        fail("related_version_conflict")
    prior = revision(session, row)
    if action == "revise":
        if row.status != "active":
            fail("related_action_invalid")
        data = snapshot(session, user_id, label, refs, resolve=resolve, now=now)
        old = {(r["domain"], r["monitor_id"], r["event_id"]) for r in prior.snapshot["members"]}
        new = {(str(r.domain), str(r.monitor_id), str(r.event_id)) for r in refs}
        action = "split" if new < old else "merge" if new > old else "revise"
        status = row.status
    else:
        if (action == "archive") != (row.status == "active"):
            fail("related_action_invalid")
        data, status = deepcopy(prior.snapshot), "archived" if action == "archive" else "active"
        # Restoring a saved grouping does not reassert its old association. Every
        # subsequent view resolves current rights and marks changed proof unknown.
    with _savepoint(session):
        changed = session.execute(update(RelatedStory).where(RelatedStory.id == row.id,
            RelatedStory.organization_id == row.organization_id, RelatedStory.owner_user_id == user_id,
            RelatedStory.version == expected_version).values(title=data["title"], status=status,
                version=expected_version + 1, updated_at=now).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            fail("related_version_conflict")
        session.refresh(row)
        _record(session, row, data, action, request_key, request_hash, prior.fingerprint, now)
    return row


def view(session, user_id, story_id, *, resolve, now=None, number=None):
    row = owned(session, user_id, story_id)
    now = clock(now)
    saved = revision(session, row, number)
    refs = references(saved.snapshot["members"], minimum=1)
    members = resolve_members(session, user_id, refs, resolve=resolve, now=now)
    facts = tuple(member["fact"] for member in members if member.get("fact") is not None)
    links = story_associations(facts, now=now) if len(facts) == len(refs) and len(refs) > 1 else ()
    current = [link.model_dump(mode="json") for link in links]
    verified = bool(links) and all(link.state == "possible" for link in links) and current == saved.snapshot["links"]
    return {"id": row.id, "version": row.version, "revision": saved.revision, "title": saved.snapshot["title"],
        "status": row.status, "historical": saved.revision != row.version,
        "association_state": "possible" if verified else "separate" if len(refs) == 1 else "unverified",
        "members": [{k: v for k, v in member.items() if k != "fact"} for member in members],
        "links": current if verified else [], "action": saved.action,
        "created_at": clock(saved.created_at.replace(tzinfo=UTC) if saved.created_at.tzinfo is None else saved.created_at).isoformat()}


def listing(session, user_id, *, after=None, limit=20, archived=False):
    organization = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 50 or type(archived) is not bool:
        fail("related_page_invalid", 422)
    query = select(RelatedStory).where(RelatedStory.organization_id == organization,
        RelatedStory.owner_user_id == user_id, RelatedStory.status == ("archived" if archived else "active"))
    if after is not None:
        anchor = owned(session, user_id, str(UUID(str(after))))
        query = query.where(RelatedStory.id > anchor.id)
    rows = list(session.scalars(query.order_by(RelatedStory.id).limit(limit + 1)))
    return {"items": [{"id": row.id, "title": row.title, "version": row.version, "status": row.status} for row in rows[:limit]],
        "next": rows[limit - 1].id if len(rows) > limit else None}


def history(session, user_id, story_id, *, before=None, limit=20):
    row = owned(session, user_id, story_id)
    if type(limit) is not int or not 1 <= limit <= 50 or (before is not None and (type(before) is not int or before < 1)):
        fail("related_page_invalid", 422)
    query = select(RelatedStoryRevision.revision, RelatedStoryRevision.action, RelatedStoryRevision.created_at).where(
        RelatedStoryRevision.story_id == row.id, RelatedStoryRevision.organization_id == row.organization_id)
    if before is not None:
        query = query.where(RelatedStoryRevision.revision < before)
    rows = list(session.execute(query.order_by(RelatedStoryRevision.revision.desc()).limit(limit + 1)))
    return {"items": [{"revision": item.revision, "action": item.action, "created_at": item.created_at} for item in rows[:limit]],
        "next": rows[limit - 1].revision if len(rows) > limit else None}
