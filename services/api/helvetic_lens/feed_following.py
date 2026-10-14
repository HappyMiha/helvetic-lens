"""In-app notifications independent of dossier research and email delivery."""
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, or_, select

from .db import utcnow
from .feed_following_models import FeedFollow
from .feed_models import Feed, FeedUpdate
from .product_api import fail
from .product_provenance import principal


class FollowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    following: StrictBool


class ReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
    through_sequence: int = Field(ge=0, strict=True)


def saved_follow(session, feed, user_id):
    return session.scalar(select(FeedFollow).where(FeedFollow.feed_id == feed.id,
        FeedFollow.owner_user_id == user_id).execution_options(populate_existing=True))


def initialize(session, feed, user_id):
    """A newly created feed delivers in-app updates without sending email."""
    return change(session, feed, user_id, FollowInput(expected_revision=0, following=True))


def state(session, feed, user_id):
    from .feed_assessments import current_binding, verdict_expression

    saved = saved_follow(session, feed, user_id)
    latest = session.scalar(select(func.max(FeedUpdate.sequence)).where(FeedUpdate.feed_id == feed.id)) or 0
    seen = saved.seen_sequence if saved else 0
    verdict = verdict_expression(current_binding(session, feed))
    unread = session.scalar(select(func.count()).select_from(FeedUpdate).where(
        FeedUpdate.feed_id == feed.id, FeedUpdate.sequence > seen,
        or_(verdict.is_(None), verdict != "unrelated"))) if saved and saved.following else 0
    return {"following": bool(saved and saved.following), "revision": saved.revision if saved else 0,
        "latest_sequence": latest, "seen_sequence": seen, "unread_count": unread}


def selected(session, identifier, identity, *, write=False):
    from .feed_operations import owned
    if write:
        session.scalar(select(Feed).where(Feed.id == str(identifier)).with_for_update())
    principal(session, identity, utcnow())
    return owned(session, str(identifier), identity.user_id)


def change(session, feed, user_id, data):
    current = state(session, feed, user_id)
    if current["following"] == data.following:
        return current
    if current["revision"] != data.expected_revision:
        fail("Your update preferences changed. Refresh before trying again.", 409)
    saved = saved_follow(session, feed, user_id)
    if saved is None:
        saved = FeedFollow(organization_id=feed.organization_id, feed_id=feed.id,
            owner_user_id=user_id, following=data.following, seen_sequence=current["latest_sequence"])
        session.add(saved)
    else:
        saved.following, saved.revision, saved.updated_at = data.following, saved.revision + 1, utcnow()
    session.flush()
    return state(session, feed, user_id)


def acknowledge(session, feed, user_id, data):
    current = state(session, feed, user_id)
    saved = saved_follow(session, feed, user_id)
    if not saved or not saved.following or data.through_sequence > current["latest_sequence"]:
        fail("Refresh this feed before marking updates as seen.", 409)
    if data.through_sequence <= saved.seen_sequence:
        return current
    if saved.revision != data.expected_revision:
        fail("Your update preferences changed. Refresh before trying again.", 409)
    saved.seen_sequence, saved.revision, saved.updated_at = data.through_sequence, saved.revision + 1, utcnow()
    session.flush()
    return state(session, feed, user_id)


def routes(router, service, actor):
    root = "/feeds/{feed_id}/follow"

    @router.get(root)
    def read(feed_id: UUID, request: Request):
        with service.db.session() as session:
            identity = actor(request)
            return state(session, selected(session, feed_id, identity), identity.user_id)

    @router.post(root)
    def follow(feed_id: UUID, data: FollowInput, request: Request):
        with service.write_guard, service.db.session() as session:
            identity = actor(request)
            result = change(session, selected(session, feed_id, identity, write=True), identity.user_id, data)
            session.commit()
            return result

    @router.post(root + "/read")
    def mark_read(feed_id: UUID, data: ReadInput, request: Request):
        with service.write_guard, service.db.session() as session:
            identity = actor(request)
            result = acknowledge(session, selected(session, feed_id, identity, write=True), identity.user_id, data)
            session.commit()
            return result
