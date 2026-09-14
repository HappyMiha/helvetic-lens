"""Explicit verified-owner email consent, separate from trademark interest settings."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update

from . import jobs
from .business_monitor_access import require_private_owner
from .models import User
from .monitoring_subjects import _savepoint
from .pollen_contracts import PollenDelivery
from .trademark_email_models import TrademarkDelivery, TrademarkEmailPolicy
from .trademark_repository import _fail, _version, owned
from .trademark_sources import _clock as clock
from .trademark_sources import _utc
from .trademark_workflow import monitor_for


class EmailConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    timezone: str = Field(default="Europe/Zurich", min_length=1, max_length=64)
    delivery: PollenDelivery = Field(default_factory=PollenDelivery)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a known IANA timezone") from None
        return value


def policy(session, monitor):
    return session.get(TrademarkEmailPolicy, (monitor.id, monitor.email_revision)) if monitor.email_revision else None


def cancel_email_work(session, monitor):
    session.execute(update(TrademarkDelivery).where(TrademarkDelivery.monitor_id == monitor.id,
        TrademarkDelivery.organization_id == monitor.organization_id, TrademarkDelivery.state == "pending")
        .values(state="suppressed").execution_options(synchronize_session=False))
    session.execute(update(jobs.Job).where(jobs.Job.organization_id == monitor.organization_id,
        jobs.Job.target_type == "trademark_monitor", jobs.Job.target_id == monitor.id,
        jobs.Job.type == "trademark_email", jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))


def view(session, user_id, monitor_id):
    monitor = owned(session, user_id, monitor_id)
    require_private_owner(monitor, user_id)
    current = policy(session, monitor)
    config = EmailConfiguration.model_validate(current.configuration) if current else EmailConfiguration()
    user = session.get(User, user_id)
    uncertain = session.scalar(select(func.count()).select_from(TrademarkDelivery).where(
        TrademarkDelivery.monitor_id == monitor.id, TrademarkDelivery.organization_id == monitor.organization_id,
        TrademarkDelivery.state == "uncertain"))
    return {"revision": monitor.email_revision, "monitor_version": monitor.version,
        "configuration": config.model_dump(mode="json"), "email_verified": user.email_verified_at is not None,
        "consent_active": bool(current and config.delivery.email != "off" and user.email_verified_at is not None
                               and current.recipient_email == user.email),
        "recipient_email": user.email, "uncertain_deliveries": uncertain,
        "consented_at": _utc(current.created_at).isoformat() if current and config.delivery.email != "off" else None}


def configure(session, user_id, monitor_id, *, expected_version, configuration, consent, now):
    from .trademark_delivery import prepare_monitor
    now = clock(now)
    _version(expected_version)
    config = EmailConfiguration.model_validate(configuration)
    wants_email = config.delivery.email != "off"
    if type(consent) is not bool or consent != wants_email:
        _fail("trademark_email_consent_required", 422)
    with _savepoint(session):
        monitor = monitor_for(session, user_id, monitor_id, write=True)
        require_private_owner(monitor, user_id)
        user = session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if monitor.version != expected_version:
            _fail("trademark_version_conflict")
        if wants_email and (monitor.status == "archived" or user.email_verified_at is None):
            _fail("trademark_email_unavailable")
        if wants_email and monitor.email_revision >= 1000:
            _fail("trademark_email_revision_limit")
        monitor.email_revision, monitor.version = monitor.email_revision + 1, monitor.version + 1
        session.add(TrademarkEmailPolicy(monitor_id=monitor.id, organization_id=monitor.organization_id,
            revision=monitor.email_revision, configuration=config.model_dump(mode="json"),
            recipient_email=user.email if wants_email else None, created_at=now))
        cancel_email_work(session, monitor)
        session.flush()
        prepare_monitor(session, monitor, now=now)
    return view(session, user_id, monitor_id)
