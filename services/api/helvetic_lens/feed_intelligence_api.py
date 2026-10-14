"""Explicit public-search refinement and feedback; model work remains background-only."""
from copy import deepcopy
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Request
from pydantic import Field, field_validator
from sqlalchemy import select

from . import feed_intelligence as intelligence
from . import feed_operations as ops
from . import jobs, legal_profiles
from .db import utcnow
from .feed_models import FeedCheck, FeedDossierLink, FeedUpdate
from .membership_locks import lock_organization
from .models import Job
from .product_api import Product, dossier, fail
from .product_provenance import principal


class Command(legal_profiles.Input):
    request_key: UUID
    expected_revision: int = Field(ge=1, strict=True)


class Precision(Command):
    include: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=20)
    exclude: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=20)
    languages: list[Annotated[str, Field(pattern=r"^[a-z]{2,3}$")]] = Field(default_factory=lambda: intelligence.DEFAULT_LANGUAGES[:], min_length=1, max_length=8)

    @field_validator("include", "exclude", "languages")
    @classmethod
    def unique(cls, values):
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class Feedback(Command):
    verdict: Literal["relevant", "not_relevant"]
    reason: str = Field(default="", max_length=500)


class Learn(legal_profiles.Input):
    request_key: UUID
    expected_feed_revision: int = Field(ge=1, strict=True)
    expected_link_revision: int = Field(ge=1, strict=True)
    context_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def invalidate(session, feed, config, settings, request_key):
    config = deepcopy(config)
    config.pop("cached_plan", None)
    feed.config_json = {**(feed.config_json or {}), "intelligence": {**config, "contract": intelligence.CONTRACT}}
    feed.revision += 1
    feed.updated_at, feed.next_check_at, feed.error = utcnow(), utcnow(), None
    current = session.get(Job, feed.job_id) if feed.job_id else None
    if current and current.state not in jobs.TERMINAL_STATES:
        jobs.cancel(session, current.id)
        check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == current.id))
        if check and check.status in {"queued", "running"}:
            check.status, check.finished_at = "cancelled", utcnow()
    if feed.status == "active":
        from .feed_worker import enqueue_check
        enqueue_check(session, feed, settings, request_key)


def routes(router, service, actor):
    def editable(session, identity, feed_id):
        lock_organization(session, identity.organization_id)
        principal(session, identity, utcnow(), write=True)
        return ops.owned(session, feed_id, identity.user_id, write=True)

    @router.patch("/feeds/{feed_id}/intelligence")
    def precision(feed_id: str, data: Precision, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            feed = editable(session, identity, feed_id)
            action = f"precision:{feed_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(feed, data.expected_revision)
                config = intelligence.settings(feed)
                selected = {name: getattr(data, name) for name in ("include", "exclude", "languages")}
                if any(config[name] != value for name, value in selected.items()):
                    invalidate(session, feed, {**config, **selected}, service.settings, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"feed_id": feed.id})
                session.commit()
            return ops.payload(session, feed, identity.user_id)

    @router.post("/feeds/{feed_id}/updates/{update_id}/feedback")
    def feedback(feed_id: str, update_id: str, data: Feedback, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            feed = editable(session, identity, feed_id)
            update = session.get(FeedUpdate, update_id)
            if not update or update.feed_id != feed.id:
                fail("Feed observation not found.", 404, "not_found")
            action = f"feedback:{update_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(feed, data.expected_revision)
                config = intelligence.settings(feed)
                selected = {"update_id": update.id, "url": update.url, "title": update.title,
                    "summary": update.summary[:1200], "verdict": data.verdict, "reason": data.reason}
                previous = next((item for item in config["feedback"] if item["update_id"] == update.id), None)
                if previous != selected:
                    config["feedback"] = [item for item in config["feedback"] if item["update_id"] != update.id] + [selected]
                    invalidate(session, feed, config, service.settings, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"feed_id": feed.id})
                session.commit()
            return ops.payload(session, feed, identity.user_id)

    base = "/products/{product}/dossiers/{dossier_id}/feeds/{link_id}/learn"

    def link_context(session, identity, product, dossier_id, link_id, *, write=False):
        if write:
            lock_organization(session, identity.organization_id)
        principal(session, identity, utcnow(), write=write)
        parent, _ = dossier(session, product, dossier_id, identity.user_id)
        link = session.get(FeedDossierLink, link_id, populate_existing=True)
        if not link or link.dossier_id != parent.id:
            fail("Feed link not found.", 404, "not_found")
        feed = ops.owned(session, link.feed_id, identity.user_id, write=True)
        return feed, link, intelligence.dossier_context(session, link)

    @router.get(base)
    def preview(product: Product, dossier_id: str, link_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            _, _, context = link_context(session, identity, product, dossier_id, link_id)
            return context

    @router.post(base)
    def learn(product: Product, dossier_id: str, link_id: str, data: Learn, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            feed, link, context = link_context(session, identity, product, dossier_id, link_id, write=True)
            action = f"learn:{link_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(feed, data.expected_feed_revision)
                ops.revision(link, data.expected_link_revision)
                if context["context_fingerprint"] != data.context_fingerprint:
                    fail("Public dossier context changed. Preview it again before applying.", 409, "feed_context_changed")
                config = intelligence.settings(feed)
                pin = intelligence.context_pin(context)
                previous = next((item for item in config["contexts"] if item["link_id"] == link.id), None)
                if previous != pin:
                    config["contexts"] = [item for item in config["contexts"] if item["link_id"] != link.id] + [pin]
                    invalidate(session, feed, config, service.settings, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"feed_id": feed.id})
                session.commit()
            return ops.payload(session, feed, identity.user_id)
