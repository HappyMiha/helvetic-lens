"""Always discoverable private related-story workflow under app auth and CSRF."""
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import related_repository as repository
from .auth import Identity
from .config import DomainError
from .hazard_boundary_store import BoundaryStore
from .models import User
from .monitoring_subjects import _actor
from .related_bindings import BindingStore, administrator
from .related_contracts import Hash, PlaceBinding, fingerprint, story_associations
from .related_models import RelatedPlaceBinding
from .related_readers import RelatedReader

Domain = Literal["warnings", "river", "traffic"]


def clock():
    return datetime.now(UTC)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reference(Input):
    domain: Domain
    monitor_id: UUID
    event_id: UUID
    revision: int = Field(strict=True, ge=1)
    evidence_hash: Hash


class Members(Input):
    members: list[Reference] = Field(min_length=1, max_length=12)


class Create(Members):
    title: str = Field(min_length=1, max_length=200)
    request_key: UUID


class Change(Input):
    expected_version: int = Field(strict=True, ge=1)
    request_key: UUID
    action: Literal["revise", "archive", "restore"]
    title: str | None = Field(default=None, min_length=1, max_length=200)
    members: list[Reference] | None = Field(default=None, min_length=1, max_length=12)


class Inspect(Input):
    reference: Reference


class ReviewBinding(Inspect):
    id: UUID
    municipality_code: str = Field(pattern=r"^[0-9]{1,4}$")
    boundary_version: str = Field(pattern=r"^\d{4}-\d{2}$")
    boundary_hash: Hash
    evidence_hash: Hash
    source_revision: Hash
    source_feature_hash: Hash
    valid_until: datetime
    reviewed: Literal[True]


def refs(values, minimum=1):
    return repository.references([value.model_dump(mode="json") for value in values], minimum=minimum)


def related_router(service, settings):
    boundaries = BoundaryStore(settings.storage_path)
    bindings = BindingStore(boundaries)
    reader = RelatedReader(settings, boundaries, bindings.select)

    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/related-developments", tags=["related-developments"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities(actor: Identity = Depends(identity)):
        with service.db.session() as session:
            user = session.get(User, actor.user_id)
            try:
                _actor(session, actor.user_id, write=True)
                writable = True
            except DomainError:
                writable = False
            return {"available": True, "can_write": writable,
                "can_review_bindings": writable and user.active and user.platform_admin,
                "domains": ["warnings", "river", "traffic"]}

    @router.get("/candidates")
    def candidates(domain: Domain, after: UUID | None = None, limit: int = Query(default=20, ge=1, le=50),
                   actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return reader.candidates(session, actor.user_id, domain, now=clock(), after=after, limit=limit)

    @router.post("/preview")
    def preview(data: Members, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            now = clock()
            members = repository.resolve_members(session, actor.user_id, refs(data.members), resolve=reader.resolve, now=now)
            facts = tuple(member["fact"] for member in members if member.get("fact") is not None)
            try:
                links = story_associations(facts, now=now) if len(facts) == len(members) and len(facts) > 1 else ()
            except ValueError:
                repository.fail("related_members_invalid", 422)
            valid = len(members) == 1 and bool(facts) and facts[0].availability == "available" or bool(links) and all(link.state == "possible" for link in links)
            return {"can_save": valid, "members": [{k: v for k, v in member.items() if k != "fact"} for member in members],
                    "links": [link.model_dump(mode="json") for link in links]}

    @router.get("/events/{domain}/{monitor_id}/{event_id}")
    def latest(domain: Domain, monitor_id: UUID, event_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = reader.load(session, actor.user_id, domain, monitor_id, event_id, now=clock())
            return {key: value for key, value in result.items() if key != "fact"}

    @router.get("/stories")
    def listing(after: UUID | None = None, archived: bool = False, limit: int = Query(default=20, ge=1, le=50),
                actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.listing(session, actor.user_id, after=after, archived=archived, limit=limit)

    @router.post("/stories", status_code=201)
    def create(data: Create, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            now = clock()
            row = repository.create(session, actor.user_id, data.title, refs(data.members, minimum=2),
                str(data.request_key), resolve=reader.resolve, now=now)
            result = repository.view(session, actor.user_id, row.id, resolve=reader.resolve, now=now)
            session.commit()
            return result

    @router.get("/stories/{identifier}")
    def detail(identifier: UUID, revision: int | None = Query(default=None, ge=1), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.view(session, actor.user_id, str(identifier), number=revision, resolve=reader.resolve, now=clock())

    @router.get("/stories/{identifier}/history")
    def history(identifier: UUID, before: int | None = Query(default=None, ge=1), limit: int = Query(default=20, ge=1, le=50),
                actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.history(session, actor.user_id, str(identifier), before=before, limit=limit)

    @router.post("/stories/{identifier}")
    def change(identifier: UUID, data: Change, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            now = clock()
            row = repository.change(session, actor.user_id, str(identifier), data.expected_version, str(data.request_key),
                resolve=reader.resolve, label=data.title, values=refs(data.members) if data.members else None,
                action=data.action, now=now)
            result = repository.view(session, actor.user_id, row.id, resolve=reader.resolve, now=now)
            session.commit()
            return result

    @router.post("/bindings/inspect")
    def inspect_binding(data: Inspect, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            administrator(session, actor.user_id)
            ref = refs([data.reference])[0]
            selected = reader.load(session, actor.user_id, ref.domain, ref.monitor_id, ref.event_id,
                revision=ref.revision, geographic_evidence=True, now=clock())
            fact = selected["fact"]
            if fact.reference != ref:
                repository.fail("related_event_changed")
            rows = list(session.scalars(select(RelatedPlaceBinding).where(
                RelatedPlaceBinding.feature_key == fingerprint(fact.source_feature.model_dump(mode="json")),
                RelatedPlaceBinding.source_revision == fact.source_revision,
                RelatedPlaceBinding.revoked_at.is_(None)).order_by(RelatedPlaceBinding.id).limit(101)))
            return {"fact": {**fact.model_dump(mode="json"), "geographic_evidence": selected["geographic_evidence"]},
                "source_feature_hash": fingerprint(fact.source_feature.model_dump(mode="json")),
                "bindings": [{"id": row.id, "valid_until": row.binding.get("valid_until"), "place_id": row.binding.get("place_id")} for row in rows[:100]],
                "truncated": len(rows) > 100}

    @router.get("/bindings/municipalities/{code}")
    def municipality(code: str, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            administrator(session, actor.user_id)
            if not code.isascii() or not code.isdigit() or not 1 <= len(code) <= 4:
                repository.fail("related_area_invalid", 422)
            return boundaries.municipality_identity(code, now=clock())

    @router.post("/bindings", status_code=201)
    def publish_binding(data: ReviewBinding, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            administrator(session, actor.user_id)
            now, reference = clock(), refs([data.reference])[0]
            fact = reader.resolve(session, actor.user_id, reference, now=now)["fact"]
            if (data.source_revision != fact.source_revision
                    or data.source_feature_hash != fingerprint(fact.source_feature.model_dump(mode="json"))
                    or data.valid_until.tzinfo is None or data.valid_until <= now):
                repository.fail("related_binding_invalid", 422)
            # Accepted time comes from the review action, never a backdated form.
            binding = PlaceBinding(id=data.id, source_feature=fact.source_feature, source_revision=fact.source_revision,
                place_namespace="swisstopo:bfs_municipality", place_id=data.municipality_code,
                boundary_version=data.boundary_version, boundary_hash=data.boundary_hash,
                evidence_hash=data.evidence_hash, accepted_at=now, valid_until=data.valid_until)
            previous = session.get(RelatedPlaceBinding, str(data.id), populate_existing=True)
            if previous is not None:
                if previous.reviewed_by != actor.user_id:
                    repository.fail("related_binding_conflict")
                binding = binding.model_copy(update={"accepted_at": datetime.fromisoformat(previous.binding["accepted_at"])})
            result = bindings.publish(session, actor.user_id, reader=reader, reference=reference, binding=binding, now=now)
            session.commit()
            return result

    @router.post("/bindings/{identifier}/revoke")
    def revoke_binding(identifier: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = bindings.revoke(session, actor.user_id, identifier, now=clock())
            session.commit()
            return result

    return router
