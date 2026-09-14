"""Private current-settings export. No evidence, credentials or external calls."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from .air_email_models import AirEmailPolicy
from .auction_workflow_models import AuctionEmailPolicy
from .commute_models import CommuteEmailPolicy
from .config import DomainError
from .hazard_models import HazardEmailPolicy
from .monitoring_centre import MODELS, scoped
from .monitoring_live_models import MonitoringRuntime
from .monitoring_subjects import _actor, _view
from .river_contracts import utc
from .river_email_models import RiverEmailPolicy
from .road_models import RoadEmailPolicy
from .tender_models import TenderEmailPolicy
from .trademark_email_models import TrademarkEmailPolicy

DOMAINS = tuple(sorted(MODELS))
POLICIES = dict(zip(
    ("air", "auctions", "commute", "warnings", "river", "traffic", "tenders", "ip"),
    (AirEmailPolicy, AuctionEmailPolicy, CommuteEmailPolicy, HazardEmailPolicy,
     RiverEmailPolicy, RoadEmailPolicy, TenderEmailPolicy, TrademarkEmailPolicy), strict=True))


def fail(code="configuration_export_changed", status=409):
    raise DomainError("The settings export could not be completed. Start a new download.", status, code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def owned(domain, organization, user):
    model = MODELS[domain]
    # Owned business monitors include those explicitly shared with colleagues;
    # a colleague's shared monitor is not this user's personal configuration.
    return scoped(model, organization, user).where(model.owner_user_id == user)


def record(session, domain, row):
    if domain == "pollen":
        view = _view(session, row)
        configuration, revision = view["configuration"], view["revision"]
        runtime = session.get(MonitoringRuntime, row.id)
        email = {"consent_recorded": bool(runtime and runtime.email_consent),
                 "muted": bool(runtime and runtime.muted),
                 "configuration": {key: configuration.get(key) for key in ("timezone", "delivery")}}
    else:
        configuration, revision = row.configuration, row.revision
        policy = session.scalar(select(POLICIES[domain]).where(
            POLICIES[domain].monitor_id == row.id,
            POLICIES[domain].organization_id == row.organization_id,
            POLICIES[domain].revision == row.email_revision)) if row.email_revision else None
        if row.email_revision and policy is None:
            fail("configuration_export_incomplete", 503)
        email = {"revision": row.email_revision, "configuration": policy.configuration if policy else None,
                 "recipient_email": policy.recipient_email if policy else None,
                 "saved_at": utc(policy.created_at).isoformat() if policy else None}
    value = {"domain": domain, "id": row.id, "created_at": utc(row.created_at).isoformat(),
             "status": row.status, "visibility": getattr(row, "visibility", "private"),
             "configuration_revision": revision, "configuration": configuration,
             "email_preferences": email}
    if domain == "commute":
        value["paused_on"] = row.paused_on.isoformat() if row.paused_on else None
    # Canonical JSON round-trip detaches mutable ORM values. Runtime samples,
    # source documents, request keys and connector settings are never selected.
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > 256 * 1024:
        fail("configuration_export_record_too_large", 422)
    return {**json.loads(encoded), "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "canonical_json": encoded}


def page(session, user, *, domain=None, cursor=None, limit=25, now=None):
    organization = _actor(session, user)
    now = now or datetime.now(UTC)
    if domain is not None and domain not in DOMAINS or type(limit) is not int or not 1 <= limit <= 50:
        fail("configuration_export_request_invalid", 422)
    selected = [domain] if domain else list(DOMAINS)
    scope = [organization, user, domain]
    started, position, after = now, 0, ""
    if cursor:
        try:
            if len(cursor) > 2048:
                raise ValueError()
            data = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if set(data) != {"v", "scope", "started", "position", "after"} or data["v"] != 1 or data["scope"] != scope:
                raise ValueError()
            started = datetime.fromisoformat(data["started"])
            position, after = data["position"], data["after"]
            if started.tzinfo is None or not now - timedelta(minutes=15) <= started <= now:
                raise ValueError()
            if type(position) is not int or not 0 <= position < len(selected) or str(UUID(after)) != after:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            fail("configuration_export_cursor_invalid", 422)
    rows = []
    for index in range(position, len(selected)):
        kind, model = selected[index], MODELS[selected[index]]
        query = owned(kind, organization, user).where(model.created_at <= started)
        if index == position and after:
            query = query.where(model.id > after)
        rows.extend((index, row) for row in session.scalars(query.order_by(model.id).limit(limit + 1 - len(rows))))
        if len(rows) > limit:
            break
    items = [record(session, selected[index], row) for index, row in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        index, last = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(canonical({"v": 1, "scope": scope,
            "started": started.isoformat(), "position": index, "after": last.id}).encode()).decode()
    _actor(session, user)
    return {"format": "helvetic-lens-monitoring-configuration-v1", "scope": scope,
            "started_at": started.isoformat(), "read_at": now.isoformat(),
            "items": items, "next_cursor": next_cursor}


def verify(session, user, bindings):
    organization = _actor(session, user)
    for binding in bindings:
        domain = binding.domain
        row = session.scalar(owned(domain, organization, user).where(MODELS[domain].id == str(binding.id))
                             .execution_options(populate_existing=True))
        if row is None or record(session, domain, row)["sha256"] != binding.sha256:
            fail()
    _actor(session, user)
    return {"verified": len(bindings), "scope": [organization, user],
            "checked_at": datetime.now(UTC).isoformat()}
