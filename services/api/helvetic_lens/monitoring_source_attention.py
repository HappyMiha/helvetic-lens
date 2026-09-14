"""Source renewal/failure attention from metadata, with personal exact-state receipts."""
import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from .config import DomainError
from .membership_locks import lock_platform_users
from .models import MonitoringSourceAcknowledgement as Receipt
from .models import User
from .monitoring_source_operations import snapshot, stamp, utc


def fail(code, status=409):
    raise DomainError("Source attention changed or is unavailable. Refresh the list.", status, code)


def administrator(session, user_id):
    user = session.get(User, user_id, populate_existing=True)
    if user is None or not user.active or not user.platform_admin:
        fail("platform_admin_required", 403)


def binding(session, settings, domain, channel):
    # IDs are hashed into the fingerprint, never returned. Credentials/policy
    # text must not enter acknowledgement storage or the attention response.
    keys = {"warnings": "hazard_source_permission_id", "traffic": "road_source_permission_id",
        "auctions": "aste_source_permission_id", "ip": "ipi_source_permission_id"}
    if domain == "commute":
        return getattr(settings, "commute_gtfs_rt_permission_id" if channel == "trip_updates" else "commute_gtfs_sa_permission_id")
    if domain == "pollen":
        return sorted((c.source_id, c.version, c.review_sha256, c.method_version, c.status,
            str(c.valid_from), str(c.valid_until)) for c in settings.pollen_source_policy.channels)
    identifier = getattr(settings, keys[domain], None) if domain in keys else None
    if domain in {"ip", "auctions", "warnings", "traffic"}:
        if domain == "ip":
            from .trademark_source_models import TrademarkSourceSelection as Selection
        elif domain == "auctions":
            from .auction_source_models import AuctionSourceSelection as Selection
        elif domain == "warnings":
            from .hazard_native_source import permission_id
            from .hazard_source_models import HazardSourceSelection as Selection
            identifier = permission_id(session, settings)
        else:
            from .road_models import RoadSourceHead as Selection
        key = Selection.source if domain == "traffic" else Selection.source_key
        rows = session.execute(select(key, Selection.generation).where(
            Selection.permission_id == identifier).order_by(key).limit(101)).all() if identifier else []
        if len(rows) > 100:
            fail("source_attention_capacity", 503)
        return [identifier, [list(row) for row in rows]]
    return identifier or domain


def issues(session, data, settings, now):
    result = []
    for source in data["items"]:
        for channel in source.get("channels") or [source]:
            domain, channel_id = source["id"], channel["id"]
            access, acquisition = channel["access"], channel["acquisition"]
            values = []
            source_binding = binding(session, settings, domain, channel_id)
            if not source["section_enabled"]:
                values.append(("section_disabled", "warning"))
            if channel["collector"] != "configured":
                values.append(("collector_unavailable", "warning"))
            if access["state"] not in {"record_current", "public_contract", "per_channel"}:
                values.append(("access_" + access["state"], "urgent" if access["state"] in {"expired", "revoked"} else "warning"))
            if domain == "pollen" and access["state"] == "partial":
                policies = settings.pollen_source_policy.channels
                if any(c.status == "revoked" for c in policies):
                    values.append(("access_revoked", "urgent"))
                if any(c.status == "approved" and c.valid_until <= now for c in policies):
                    values.append(("access_expired", "urgent"))
            if access["state"] in {"record_current", "partial"} and access["expires_at"]:
                remaining = utc(datetime.fromisoformat(access["expires_at"])) - now
                if remaining <= timedelta(days=7):
                    values.append(("renewal_7_days", "urgent"))
                elif remaining <= timedelta(days=30):
                    values.append(("renewal_30_days", "warning"))
            state = acquisition["state"]
            if state != "recorded":
                values.append(("acquisition_" + state, "urgent" if state in {"errors", "invalid_clock"} else "warning"))
            clocks = {key: value for key, value in acquisition.items() if not key.endswith("_age_seconds")}
            for code, severity in values:
                key = f"{domain}:{channel_id}:{code}"
                fingerprint = hashlib.sha256(json.dumps([key, severity, access, channel["collector"],
                    source["section_enabled"], clocks, source_binding],
                    sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
                result.append({"key": key, "domain": domain, "channel": channel_id, "code": code,
                    "severity": severity, "fingerprint": fingerprint, "expires_at": access["expires_at"],
                    "latest_success_at": acquisition["latest_success_at"], "next_request_at": acquisition["next_request_at"],
                    "href": f"/monitoring/settings?category={domain}"})
    return sorted(result, key=lambda row: (row["severity"] != "urgent", row["domain"], row["key"]))


def read(session, settings, user_id, *, now=None):
    now = now or datetime.now(UTC)
    administrator(session, user_id)
    data = snapshot(session, settings, now=now)
    items = issues(session, data, settings, now)
    receipts = {row.issue_key: row for row in session.scalars(select(Receipt).where(
        Receipt.user_id == user_id, Receipt.issue_key.in_([item["key"] for item in items])))}
    for item in items:
        receipt = receipts.get(item["key"])
        item["acknowledged_at"] = stamp(receipt.acknowledged_at) if receipt and receipt.fingerprint == item["fingerprint"] else None
    return {"checked_at": data["checked_at"], "items": items,
        "unacknowledged": sum(row["acknowledged_at"] is None for row in items)}


def acknowledge(session, settings, user_id, key, fingerprint, *, now=None):
    lock_platform_users(session, user_id)
    now = now or datetime.now(UTC)
    data = read(session, settings, user_id, now=now)
    current = next((row for row in data["items"] if row["key"] == key), None)
    if current is None or current["fingerprint"] != fingerprint:
        fail("source_attention_changed")
    row = session.get(Receipt, (user_id, key))
    if row is None:
        row = Receipt(user_id=user_id, issue_key=key, fingerprint=fingerprint, acknowledged_at=now)
        session.add(row)
    elif row.fingerprint != fingerprint:
        row.fingerprint, row.acknowledged_at = fingerprint, now
    session.flush()
    return {"key": key, "fingerprint": fingerprint, "acknowledged_at": stamp(row.acknowledged_at)}


class Acknowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_:]+$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def source_attention_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            fail("authentication_required", 401)
        if not actor.platform_admin:
            fail("platform_admin_required", 403)
        return actor

    router = APIRouter(prefix="/api/admin/monitoring-sources/attention")

    @router.get("")
    def current(actor=Depends(identity)):
        with service.db.session() as session:
            return read(session, settings, actor.user_id)

    @router.post("/acknowledge")
    def accept(body: Acknowledge, actor=Depends(identity)):
        try:
            with service.db.session() as session:
                result = acknowledge(session, settings, actor.user_id, body.key, body.fingerprint)
                session.commit()
                return result
        except OperationalError:
            fail("source_attention_retry", 503)

    return router
