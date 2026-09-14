"""Private consented Air changes, bound to current pollutant/period evidence."""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import aliased

from . import jobs
from .air_contracts import DAILY_PERIODS, AirConfiguration
from .air_contracts import utc as _utc
from .air_email_models import AirDelivery
from .air_email_preferences import EmailConfiguration, cancel_email_work, clock, policy
from .air_models import AirChange, AirMonitor, AirSourceCache
from .air_runtime import fresh
from .air_runtime import preview as source_preview
from .air_sources import catalog_key, observation_key
from .air_sources import digest as fingerprint
from .auth_mail import AuthMailer
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def _now(value=None):
    return clock(value or datetime.now(UTC))


def signal(change):
    return fingerprint({"monitor": change.monitor_id, "change": change.id})


def latest(change=AirChange):
    other = aliased(AirChange)
    return ~exists(select(other.id).where(other.monitor_id == change.monitor_id,
        other.organization_id == change.organization_id, other.development_id == change.development_id,
        other.sequence > change.sequence))


def prepare_monitor(session, monitor, *, now):
    now = _now(now)
    current = policy(session, monitor)
    if current is None or monitor.status != "active" or _utc(current.created_at) > now:
        return 0
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if config.delivery.email == "off" or user is None or user.email_verified_at is None or current.recipient_email != user.email:
        return 0
    recorded = exists(select(AirDelivery.id).where(AirDelivery.change_id == AirChange.id,
        AirDelivery.monitor_id == monitor.id, AirDelivery.consent_revision == current.revision))
    changes = list(session.scalars(select(AirChange).where(
        AirChange.monitor_id == monitor.id, AirChange.organization_id == monitor.organization_id,
        AirChange.revision == monitor.revision, AirChange.decision.is_(None), latest(),
        AirChange.created_at > _utc(current.created_at), AirChange.created_at >= now - MAX_AGE,
        AirChange.created_at <= now, ~recorded).order_by(AirChange.created_at, AirChange.sequence).limit(MAX_BATCH)))
    for change in changes:
        session.add(AirDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
            owner_user_id=monitor.owner_user_id, change_id=change.id, consent_revision=current.revision,
            signal_hash=signal(change), state="suppressed" if change.evidence.get("recovered") else "pending",
            due_at=next_delivery_at(config, now), created_at=now))
    session.flush()
    return len(changes)


def context(session, settings, monitor, revision, now):
    if not settings.air_watch_enabled:
        raise ValueError("Air email is unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id).with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or current is None or current.revision != revision
            or _utc(current.created_at) > now or user is None or user.email_verified_at is None or user.email != current.recipient_email):
        raise ValueError("Air email consent is no longer applicable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise ValueError("Air email is off")
    return config, user


def current_condition(session, monitor, change, *, now):
    """Require an up-to-date stateful projection, including all rolling-mean inputs."""
    config = AirConfiguration.model_validate(monitor.configuration)
    rule = change.evidence.get("rule")
    if not rule or not any(item.model_dump(mode="json") == rule for item in config.rules):
        return "suppressed"
    metric, period = rule["metric"], rule["period"]
    if metric in config.muted_metrics:
        return "suppressed"
    condition = (monitor.state or {}).get("conditions", {}).get(fingerprint(rule))
    if condition is None or condition.get("latest_change_id") != change.id:
        return "suppressed"
    evidence = change.evidence["sample"]
    if (change.evidence.get("station_id") != config.station_id or evidence["station_id"] != config.station_id
            or evidence["metric"] != metric or evidence["period"] != period):
        return "suppressed"
    observation_age = timedelta(hours=25 if period in DAILY_PERIODS.values() else 6)
    for key, age in ((catalog_key(config.station_id, period), timedelta(hours=25)),
                     (observation_key(config.station_id, period), observation_age)):
        cache = session.get(AirSourceCache, key, populate_existing=True)
        if cache is None or cache.error or cache.fetched_at is None or not now - age <= _utc(cache.fetched_at) <= now:
            return "deferred"
    try:
        coverage = source_preview(session, monitor.configuration, now)["coverage"].get(f"{metric}:{period}")
    except DomainError:
        return "deferred"
    if not coverage or coverage["status"] != "current" or condition.get("status") != "current":
        return "deferred"
    sample = coverage["sample"]
    if (not fresh(sample, now) or sample["quality"] != "provisional"
            or sample["unit"] != evidence["unit"] or sample["method"] != evidence["method"]
            or condition.get("watermark") != sample["timestamp"]
            or condition.get("last_hash") != sample["value_hash"]):
        return "deferred"
    # Hysteresis and cooldown are stateful. A plain threshold calculation here
    # would contradict the verified projection inside the hysteresis band.
    if (condition.get("observed") != change.evidence["current_state"]
            or condition.get("reported") != change.evidence["current_state"]):
        return "suppressed"
    return "eligible"


def eligibility(session, monitor, intent, *, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or intent.organization_id != monitor.organization_id or not now - MAX_AGE <= _utc(intent.created_at) <= now):
        return "suppressed", None
    change = session.scalar(select(AirChange).where(AirChange.id == intent.change_id,
        AirChange.monitor_id == monitor.id, AirChange.organization_id == monitor.organization_id,
        latest()).execution_options(populate_existing=True))
    current = policy(session, monitor)
    if (change is None or current is None or change.revision != monitor.revision or change.decision is not None
            or change.evidence.get("recovered") or signal(change) != intent.signal_hash
            or not _utc(current.created_at) < _utc(change.created_at) <= now
            or _utc(change.created_at) < now - MAX_AGE):
        return "suppressed", None
    state = current_condition(session, monitor, change, now=now)
    if state != "eligible":
        return state, None
    duplicates = set(session.scalars(select(AirDelivery.state).where(
        AirDelivery.organization_id == monitor.organization_id, AirDelivery.owner_user_id == monitor.owner_user_id,
        AirDelivery.signal_hash == intent.signal_hash, AirDelivery.id != intent.id,
        AirDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "deferred", None
    return "eligible", {"href": f"/air-watch?monitor={monitor.id}&change={change.id}",
                        "detected_at": _utc(change.created_at).isoformat()}


def pending(monitor, now):
    return (select(AirDelivery).where(AirDelivery.monitor_id == monitor.id,
        AirDelivery.organization_id == monitor.organization_id, AirDelivery.state == "pending",
        AirDelivery.due_at <= now, AirDelivery.consent_revision == monitor.email_revision)
        .order_by(AirDelivery.due_at, AirDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(AirDelivery.sent_at, AirDelivery.claimed_at)
    return session.scalar(select(AirDelivery.id).where(AirDelivery.monitor_id == monitor.id,
        AirDelivery.organization_id == monitor.organization_id,
        AirDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def retry_at(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now + timedelta(seconds=60))


def preview(session, settings, user_id, monitor_id, *, now=None):
    from .air_runtime import owned
    now = _now(now)
    monitor = owned(session, user_id, monitor_id)
    result = {"items": [], "more_available": False, "quiet_hours": False, "status": "unavailable"}
    if settings.auth_email_mode != "smtp":
        return result
    try:
        config, _ = context(session, settings, monitor, monitor.email_revision, now)
    except (DomainError, ValueError):
        return result
    rows = list(session.scalars(pending(monitor, now).limit(MAX_BATCH + 1)))
    for row in rows[:MAX_BATCH]:
        state, item = eligibility(session, monitor, row, now=now)
        if state == "eligible":
            result["items"].append(item)
    return {**result, "more_available": len(rows) > MAX_BATCH, "quiet_hours": _quiet(config, now),
        "status": "daily_already_attempted" if daily_attempted(session, monitor, config, now) else "ready"}


def enqueue_due(database, settings, *, now=None):
    now = _now(now)
    with database.session(include_all_organizations=True) as session:
        session.execute(update(AirDelivery).where(AirDelivery.state == "sending",
            AirDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(AirDelivery).where(AirDelivery.state == "pending",
            AirDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active = exists(select(jobs.Job.id).where(jobs.Job.type == "air_email", jobs.Job.target_type == "air_monitor",
            jobs.Job.target_id == AirDelivery.monitor_id, jobs.Job.organization_id == AirDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)))
        candidates = list(session.execute(select(AirDelivery.monitor_id, AirDelivery.organization_id).where(
            AirDelivery.state == "pending", AirDelivery.due_at <= now, ~active)
            .group_by(AirDelivery.monitor_id, AirDelivery.organization_id)
            .order_by(func.min(AirDelivery.due_at), AirDelivery.monitor_id).limit(100)))
        session.commit()
    if not settings.air_watch_enabled or settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(AirMonitor).where(AirMonitor.id == identifier).with_for_update())
            if monitor is None:
                continue
            try:
                config, _ = context(session, settings, monitor, monitor.email_revision, now)
            except (DomainError, ValueError):
                cancel_email_work(session, monitor)
                session.commit()
                continue
            first = session.scalar(pending(monitor, now).limit(1))
            if first is not None and daily_attempted(session, monitor, config, now):
                session.execute(update(AirDelivery).where(AirDelivery.monitor_id == identifier,
                    AirDelivery.state == "pending", AirDelivery.due_at <= now)
                    .values(due_at=next_delivery_at(config, now + timedelta(minutes=1))))
                session.commit()
                continue
            active_job = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "air_email",
                jobs.Job.target_type == "air_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active_job is None:
                _, reused = jobs.enqueue(session, job_type="air_email", target_type="air_monitor", target_id=identifier,
                    queue="maintenance", max_attempts=1, payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"air-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("Air Quality Watch: station updates", "Review new changes at your monitored station. Observations are not personal health advice.", "Open Air Quality Watch", "Turn off email in monitor settings to unsubscribe."),
    "de": ("Air Quality Watch: Stationsänderungen", "Prüfen Sie neue Änderungen an Ihrer überwachten Station. Messungen sind keine persönliche Gesundheitsberatung.", "Air Quality Watch öffnen", "Zum Abbestellen E-Mail in den Monitoreinstellungen ausschalten."),
    "fr": ("Air Quality Watch : changements à la station", "Consultez les changements à votre station surveillée. Les observations ne sont pas des conseils de santé personnels.", "Ouvrir Air Quality Watch", "Désactivez les e-mails dans les réglages du suivi pour vous désabonner."),
    "it": ("Air Quality Watch: aggiornamenti della stazione", "Esamina le modifiche alla stazione monitorata. Le osservazioni non sono consigli sanitari personali.", "Apri Air Quality Watch", "Disattiva le e-mail nelle impostazioni del monitoraggio per annullare l’iscrizione."),
    "rm": ("Air Quality Watch: midadas da la staziun", "Controllai las novas midadas da Vossa staziun observada. Observaziuns n’èn betg cussegls persunals da sanadad.", "Avrir Air Quality Watch", "Deactivai ils e-mails en ils parameters da l’observaziun per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/air-watch?monitor={monitor.id}"
    lines = [f"{item['detected_at']}: {root}{item['href']}" for item in items]
    links = [f'<li><a href="{escape(root + item["href"], quote=True)}">{escape(item["detected_at"])}</a></li>' for item in items]
    body = "\n\n".join([monitor.configuration["name"], intro, *lines, f"{action}: {link}", stop])
    html = f"<p>{escape(monitor.configuration['name'])}</p><p>{escape(intro)}</p><ul>{''.join(links)}</ul>"
    html += f'<p><a href="{escape(link, quote=True)}">{escape(action)}</a></p><p>{escape(stop)}</p>'
    return title, body, html


def deliver(database, settings, *, monitor_id, consent_revision, now=None, mailer=None, before_send=None, checkpoint=lambda: True):
    fixed, now = now is not None, _now(now)
    if not checkpoint():
        return {"status": "cancelled"}
    if mailer is None and settings.auth_email_mode != "smtp":
        return {"status": "mail_not_live"}
    identifiers = []
    with database.session() as session:
        monitor = session.scalar(select(AirMonitor).where(AirMonitor.id == monitor_id).with_for_update())
        if monitor is None:
            return {"status": "inactive"}
        try:
            config, _ = context(session, settings, monitor, consent_revision, now)
        except (DomainError, ValueError):
            return {"status": "unavailable"}
        if daily_attempted(session, monitor, config, now):
            return {"status": "daily_already_attempted"}
        for row in session.scalars(pending(monitor, now).limit(MAX_BATCH)):
            state, _ = eligibility(session, monitor, row, now=now)
            if state == "suppressed":
                row.state = "suppressed"
            elif state == "deferred" or _quiet(config, now):
                row.due_at = retry_at(config, now)
            else:
                row.state, row.claimed_at = "sending", now
                identifiers.append(row.id)
        session.commit()
    if not identifiers:
        return {"status": "no_eligible_changes"}
    if before_send:
        before_send()
    permitted = checkpoint()
    with database.session() as session:
        monitor = session.scalar(select(AirMonitor).where(AirMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(AirDelivery).where(AirDelivery.id.in_(identifiers),
            AirDelivery.monitor_id == monitor_id, AirDelivery.state == "sending").with_for_update()))
        now = now if fixed else _now()
        try:
            if not permitted or monitor is None or len(rows) != len(identifiers):
                raise ValueError("Email claim is no longer available")
            config, user = context(session, settings, monitor, consent_revision, now)
            selected, items = [], []
            for row in rows:
                state, value = eligibility(session, monitor, row, now=now)
                if state == "eligible":
                    selected.append(row)
                    items.append(value)
                elif state == "deferred":
                    row.state, row.claimed_at, row.due_at = "pending", None, retry_at(config, now)
                else:
                    row.state = "suppressed"
            rows = selected
            if not rows:
                session.commit()
                return {"status": "suppressed"}
            if _quiet(config, now):
                for row in rows:
                    row.state, row.claimed_at, row.due_at = "pending", None, retry_at(config, now)
                session.commit()
                return {"status": "quiet_hours"}
        except (DomainError, ValueError):
            for row in rows:
                row.state = "suppressed"
            session.commit()
            return {"status": "suppressed"}
        title, body, html = render(settings, user, monitor, items)
        try:
            mode = (mailer or AuthMailer(settings)).send_message(user.email, title, body, html, user.locale,
                message_id=f"<air-{fingerprint(sorted(row.id for row in rows))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
