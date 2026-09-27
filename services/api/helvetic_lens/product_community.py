"""Personal public contributions; private workspace discussions never enter this API."""
import hashlib
import re
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool
from sqlalchemy import func, or_, select

from .db import utcnow
from .legal_profiles import Input
from .membership_locks import lock_organization
from .models import OrganizationMembership, User, UserSession
from .product_api import Product, fail, iso
from .product_models import ProductPublication, PublicContribution, PublicContributionMutation
from .product_provenance import canonical, principal
from .product_publications import PublicSource

# Only these personal public actions are exempt from workspace viewer write denial.
COMMUNITY_WRITE = re.compile(
    r"^/api/products/(pharma|loyer)/public-dossiers/[0-9a-f-]{36}/(?:discussion"
    r"(?:/[0-9a-f-]{36}(?:/action)?)?|files|research/[0-9a-f-]{36}/control|evidence-changes/[0-9a-f-]{36}/review)$")


class ContributionContent(Input):
    author_label: str = Field(min_length=2, max_length=100)
    body: str = Field(min_length=10, max_length=12000)
    sources: list[PublicSource] = Field(default_factory=list, max_length=10)


class ContributionInput(Input):
    request_key: UUID
    publication_revision: int = Field(ge=1)
    confirm_public: bool
    content: ContributionContent
    kind: Literal["comment", "url", "correction", "research_request", "file"] = "comment"
    analyse_publicly: StrictBool = False
    public_query_confirmed: StrictBool = False


class ContributionEdit(ContributionInput):
    expected_revision: int = Field(ge=1)


class ContributionAction(Input):
    request_key: UUID
    expected_revision: int = Field(ge=1)
    action: Literal["remove", "hide", "restore"]
    reason: str = Field(default="", max_length=600)


def publication(session, product, identifier, *, lock=False):
    query = select(ProductPublication).where(ProductPublication.id == str(identifier),
        ProductPublication.product == product, ProductPublication.status == "published")
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = session.scalar(query)
    if not row:
        fail("This public dossier is not available.", 404)
    return row


def participant(session, identity, product, identifier, *, write=False):
    row = publication(session, product, identifier)
    if write:
        # Serialize withdrawal, membership changes and erasure as well as other
        # contributors. The same sorted organization order is used by erasure.
        for organization in sorted({identity.organization_id, row.organization_id}):
            lock_organization(session, organization)
        session.scalar(select(User).where(User.id == identity.user_id).with_for_update())
        session.scalar(select(UserSession).where(UserSession.id == identity.session_id).with_for_update())
    principal(session, identity, utcnow())
    membership = session.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == identity.organization_id,
        OrganizationMembership.user_id == identity.user_id).execution_options(populate_existing=True))
    row = publication(session, product, identifier, lock=write)
    moderator = row.organization_id == identity.organization_id and membership.role == "organization_admin"
    if not moderator:
        from .legal_profile_models import LegalMonitoringProfile
        from .product_access import RANK, role
        from .product_models import ProductDossier

        parent = session.get(ProductDossier, row.dossier_id)
        profile = session.get(LegalMonitoringProfile, parent.profile_id)
        moderator = RANK.get(role(session, parent, profile, identity.user_id), -1) >= 2
    return row, moderator


def public_contribution(row):
    return {"id": row.id, "revision": row.revision, "publication_revision": row.publication_revision,
        "kind": row.kind, "file_name": row.file_name, "byte_size": row.byte_size, "sha256": row.sha256,
        "author_label": row.author_label, "body": row.body,
        "sources": [{"title": value["title"], "url": value["url"]} for value in row.sources_json],
        "created_at": iso(row.created_at), "updated_at": iso(row.updated_at)}


def contribution_payload(session, row, user_id=None, moderator=False):
    owned = row.author_user_id == user_id
    result = public_contribution(row)
    from .product_investigation_models import Investigation
    from .product_public_research import eligible, summary

    run = session.scalar(select(Investigation).where(Investigation.public_contribution_id == row.id, eligible()))
    result["research"] = summary(session, run) if run else None
    if user_id:
        result.update(status=row.status, can_edit=owned and row.status != "removed",
            can_remove=owned and row.status != "removed", can_moderate=moderator and row.status != "removed")
        if owned or moderator:
            result["moderation_reason"] = row.moderation_reason
            result["history"] = [{"revision": event.revision, "action": event.action,
                "reason": event.reason, "created_at": iso(event.created_at)} for event in session.scalars(
                    select(PublicContributionMutation).where(PublicContributionMutation.contribution_id == row.id)
                    .order_by(PublicContributionMutation.revision.desc()).limit(10))]
    return result


def discussion_page(session, row, offset, identity=None, moderator=False):
    query = select(PublicContribution).where(PublicContribution.publication_id == row.id)
    if not moderator:
        visible = PublicContribution.status == "visible"
        if identity:
            visible = or_(visible, PublicContribution.author_user_id == identity.user_id)
        query = query.where(visible)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(query.order_by(PublicContribution.created_at, PublicContribution.id).offset(offset).limit(20))
    return {"items": [contribution_payload(session, item, identity.user_id if identity else None, moderator)
                      for item in items], "total": total, "offset": offset, "page_size": 20,
            "publication_revision": row.revision, "can_post": identity is not None, "can_moderate": moderator}


def contribution(session, row, identifier):
    value = session.scalar(select(PublicContribution).where(PublicContribution.id == str(identifier),
        PublicContribution.publication_id == row.id).with_for_update().execution_options(populate_existing=True))
    if not value:
        fail("Contribution not found.", 404)
    return value


def replay(session, row, identity, data, action, identifier=None):
    fingerprint = hashlib.sha256(canonical({"action": action, "contribution": identifier,
        "data": data.model_dump(mode="json", exclude={"request_key"})}).encode()).hexdigest()
    event = session.scalar(select(PublicContributionMutation).where(
        PublicContributionMutation.publication_id == row.id,
        PublicContributionMutation.request_key == str(data.request_key)))
    if event and (event.actor_user_id != identity.user_id or event.fingerprint != fingerprint):
        fail("This request was already used for a different contribution change.", 409)
    return event, fingerprint


def changed(session, row, identity, data, action, fingerprint, moderator):
    session.flush()
    session.add(PublicContributionMutation(organization_id=row.organization_id, publication_id=row.publication_id,
        contribution_id=row.id, actor_user_id=identity.user_id, request_key=str(data.request_key),
        fingerprint=fingerprint, revision=row.revision, action=action, reason=getattr(data, "reason", "")))
    from .product_public_research import invalidate, queue

    invalidate(session, row.publication_id, contribution_id=row.id)
    if action in {"create", "edit", "upload"} and getattr(data, "analyse_publicly", False):
        queue(session, session.get(ProductPublication, row.publication_id), row, identity,
              external=row.kind == "research_request" and data.public_query_confirmed)
    session.commit()
    return {"contribution": contribution_payload(session, row, identity.user_id, moderator)}


def check_content(row, data):
    if data.publication_revision != row.revision:
        fail("The public dossier changed. Read its latest version before posting.", 409)
    if not data.confirm_public:
        fail("Review your contribution and confirm it may be published for everyone.", 409)
    if len({source.url for source in data.content.sources}) != len(data.content.sources):
        fail("List each source address once.")
    if row.living_research and not data.analyse_publicly:
        fail("Confirm public analysis: this contribution and its findings will be visible to everyone.", 409)
    if row.living_research and data.kind == "research_request" and (not data.public_query_confirmed or len(data.content.body) > 300):
        fail("Use a question of at most 300 characters and confirm public-source discovery.")


def check_edit(row, expected):
    if row.revision != expected:
        fail("This contribution changed. Reload the discussion before saving.", 409)
    if row.status == "removed":
        fail("This contribution was removed and cannot be restored.", 409)


def community_routes(router, service, actor):
    @router.get("/public-dossiers/{publication_id}/discussion")
    def read(product: Product, publication_id: UUID, offset: int = Query(default=0, ge=0, le=100000)):
        with service.db.session(include_all_organizations=True) as session:
            return discussion_page(session, publication(session, product, publication_id), offset)

    @router.get("/public-dossiers/{publication_id}/discussion/workspace")
    def workspace(product: Product, publication_id: UUID, request: Request,
                  offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            row, moderator = participant(session, identity, product, publication_id)
            return discussion_page(session, row, offset, identity, moderator)

    @router.post("/public-dossiers/{publication_id}/discussion", status_code=201)
    def create(product: Product, publication_id: UUID, data: ContributionInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, moderator = participant(session, identity, product, publication_id, write=True)
            event, fingerprint = replay(session, row, identity, data, "create")
            if event:
                return {"contribution": contribution_payload(session,
                    contribution(session, row, event.contribution_id), identity.user_id, moderator)}
            check_content(row, data)
            if data.kind == "file":
                fail("Use the public file upload to contribute an original.")
            item = PublicContribution(organization_id=row.organization_id, publication_id=row.id,
                author_user_id=identity.user_id, publication_revision=row.revision, revision=1,
                author_label=data.content.author_label, body=data.content.body,
                sources_json=[source.model_dump() for source in data.content.sources], kind=data.kind)
            session.add(item)
            return changed(session, item, identity, data, "create", fingerprint, moderator)

    @router.post("/public-dossiers/{publication_id}/discussion/{contribution_id}")
    def edit(product: Product, publication_id: UUID, contribution_id: UUID,
             data: ContributionEdit, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, moderator = participant(session, identity, product, publication_id, write=True)
            item = contribution(session, row, contribution_id)
            if item.author_user_id != identity.user_id:
                fail("Only the author can edit this contribution.", 403)
            event, fingerprint = replay(session, row, identity, data, "edit", str(contribution_id))
            if event:
                return {"contribution": contribution_payload(session, item, identity.user_id, moderator)}
            check_edit(item, data.expected_revision)
            check_content(row, data)
            if data.kind != item.kind:
                fail("A contribution's kind cannot change. Submit a new contribution instead.")
            item.author_label, item.body = data.content.author_label, data.content.body
            item.sources_json = [source.model_dump() for source in data.content.sources]
            item.publication_revision, item.updated_at, item.revision = row.revision, utcnow(), item.revision + 1
            # Hidden contributions remain hidden until an explicit moderator decision.
            return changed(session, item, identity, data, "edit", fingerprint, moderator)

    @router.post("/public-dossiers/{publication_id}/discussion/{contribution_id}/action")
    def action(product: Product, publication_id: UUID, contribution_id: UUID,
               data: ContributionAction, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, moderator = participant(session, identity, product, publication_id, write=True)
            item = contribution(session, row, contribution_id)
            if data.action == "remove":
                if item.author_user_id != identity.user_id:
                    fail("Only the author can remove this contribution. Moderators can hide it.", 403)
            elif not moderator:
                fail("A dossier workspace administrator must moderate this discussion.", 403)
            elif len(data.reason) < 5:
                fail("Explain the moderation decision in at least five characters.")
            event, fingerprint = replay(session, row, identity, data, data.action, str(contribution_id))
            if event:
                return {"contribution": contribution_payload(session, item, identity.user_id, moderator)}
            check_edit(item, data.expected_revision)
            artifact_to_remove = ""
            if data.action == "remove":
                item.status, item.body, item.author_label, item.sources_json = "removed", "", "", []
                item.moderation_reason = ""
                artifact_to_remove = item.artifact_key
                item.artifact_key, item.file_name, item.sha256, item.content_type, item.byte_size = "", "", "", "", 0
            else:
                expected = "visible" if data.action == "hide" else "hidden"
                if item.status != expected:
                    fail("This contribution's visibility changed. Reload the discussion.", 409)
                item.status = "hidden" if data.action == "hide" else "visible"
                item.moderation_reason = data.reason if data.action == "hide" else ""
            item.updated_at, item.revision = utcnow(), item.revision + 1
            result = changed(session, item, identity, data, data.action, fingerprint, moderator)
            if artifact_to_remove:
                from .maintenance import remove_public_originals

                remove_public_originals(service.environment_settings, [artifact_to_remove])
            return result
