"""One native visibility projection for Today counts and in-app review queues."""

from datetime import datetime

from sqlalchemy import select

from . import (
    air_today,
    auction_today,
    commute_today,
    hazard_today,
    monitoring_runtime,
    river_today,
    road_today,
    tender_today,
    trademark_today,
)
from .hazard_boundary_store import BoundaryStore
from .interest_feed import InterestFeedReader
from .monitoring_contracts import ReaderMode
from .monitoring_live_models import MonitoringReview
from .monitoring_subjects import _actor

DOMAINS = ("pollen", "air", "river", "tenders", "commute", "traffic", "warnings", "ip", "auctions", "legal")


def pair(cursor):
    return {"before": datetime.fromisoformat(cursor["before"]), "before_id": cursor["before_id"]} if cursor else {}


class ReviewQueues:
    def __init__(self, session, settings, user_id, *, now, prompts, runtime=None):
        self.session, self.settings, self.user_id, self.now = session, settings, user_id, now
        self.organization = _actor(session, user_id)
        self.boundaries = BoundaryStore(settings.storage_path)
        self.legal = InterestFeedReader(self.organization, user_id, settings=settings, prompts=prompts, runtime=runtime)

    def enabled(self, domain):
        settings = self.settings
        return {
            "pollen": settings.deployment_instance in {"main", "monitoring-v2"}
            and monitoring_runtime._mode(settings, self.organization) == ReaderMode.ENABLED,
            "air": settings.air_watch_enabled, "river": settings.river_watch_enabled,
            "tenders": settings.tender_watch_enabled, "commute": settings.commute_watch_enabled,
            "traffic": settings.road_watch_enabled and settings.road_source_enabled,
            "warnings": settings.hazard_watch_enabled, "ip": settings.trademark_watch_enabled,
            "auctions": settings.auction_watch_enabled, "legal": True,
        }[domain]

    def page(self, domain, cursor=None):
        if not self.enabled(domain):
            return {"items": [], "next_cursor": None, "state": "unavailable"}
        session, settings, user, now = self.session, self.settings, self.user_id, self.now
        if domain == "pollen":
            result = monitoring_runtime.today(session, settings=settings, user_id=user, now=now, before_id=cursor)
            ids = [item["id"] for item in result["items"]]
            reviewed = set(session.scalars(select(MonitoringReview.entry_id).where(MonitoringReview.entry_id.in_(ids)))) if ids else set()
            result["items"] = [item for item in result["items"] if item["id"] not in reviewed]
        elif domain == "air":
            result = air_today.today(session, user, **pair(cursor))
            result = {"items": [item for item in result["items"] if item["decision"] is None], "next_cursor": result["next"]}
        elif domain == "river":
            result = river_today.today(session, user, now=now, unreviewed=True, limit=20, **pair(cursor))
            result = {**result, "next_cursor": result["next"]}
        elif domain == "tenders":
            result = tender_today.today(session, user, now=now, review_state="pending", limit=20, after_version=cursor)
        elif domain == "commute":
            result = commute_today.today(session, settings, user, now=now, before_id=cursor, limit=50)
        elif domain == "traffic":
            result = road_today.today(session, settings, user, now=now, cursor=cursor, limit=50)
        elif domain == "warnings":
            result = hazard_today.page(session, settings, user, store=self.boundaries, now=now, cursor=cursor, limit=20)
        elif domain == "ip":
            result = trademark_today.page(session, settings, user, now=now, cursor=cursor, limit=50)
        elif domain == "auctions":
            result = auction_today.page(session, settings, user, now=now, cursor=cursor, limit=50)
        else:
            result = self.legal.feed(session, state="unread", cursor=cursor or "", limit=50)
        return {**result, "state": "available"}
