"""Private consented station-change notifications; no source collection or forecast claims."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import aliased

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at
from .river_contracts import RiverConfiguration
from .river_contracts import utc as _utc
from .river_email_models import RiverDelivery
from .river_email_preferences import EmailConfiguration, cancel_email_work, clock, policy
from .river_models import RiverChange, RiverMonitor, RiverSourceCache
from .river_runtime import _rule_value, fresh, samples
from .river_runtime import preview as source_preview
from .river_sources import digest as fingerprint

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def _now(value=None):
    return clock(value or datetime.now(UTC))


def signal(change):
    return fingerprint({"monitor": change.monitor_id, "change": change.id})


def latest(change=RiverChange):
    other = aliased(RiverChange)
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
    recorded = exists(select(RiverDelivery.id).where(RiverDelivery.change_id == RiverChange.id,
        RiverDelivery.monitor_id == monitor.id, RiverDelivery.consent_revision == current.revision))
    changes = list(session.scalars(select(RiverChange).where(
        RiverChange.monitor_id == monitor.id, RiverChange.organization_id == monitor.organization_id,
        RiverChange.revision == monitor.revision, RiverChange.decision.is_(None), latest(),
        RiverChange.created_at > _utc(current.created_at), RiverChange.created_at >= now - MAX_AGE,
        RiverChange.created_at <= now, ~recorded).order_by(RiverChange.created_at, RiverChange.sequence).limit(MAX_BATCH)))
    for change in changes:
        session.add(RiverDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
            owner_user_id=monitor.owner_user_id, change_id=change.id, consent_revision=current.revision,
            signal_hash=signal(change), state="suppressed" if change.evidence.get("recovered") else "pending",
            due_at=next_delivery_at(config, now), created_at=now))
    session.flush()
    return len(changes)


def context(session, settings, monitor, revision, now):
    if not settings.river_watch_enabled:
        raise ValueError("River email is unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id).with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or current is None or current.revision != revision
            or _utc(current.created_at) > now or user is None or user.email_verified_at is None or user.email != current.recipient_email):
        raise ValueError("River email consent is no longer applicable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise ValueError("River email is off")
    return config, user


def current_condition(session, monitor, change, *, now):
    """Re-evaluate the current source value, never turn absent/stale evidence into safe."""
    config = RiverConfiguration.model_validate(monitor.configuration)
    rule = change.evidence.get("rule")
    key = fingerprint(rule) if rule else "official-danger"
    if rule and not any(item.model_dump(mode="json") == rule for item in config.rules) or not rule and not config.official_danger:
        return "suppressed"
    condition = (monitor.state or {}).get("conditions", {}).get(key)
    if condition is None or condition.get("latest_change_id") != change.id:
        return "suppressed"
    metric = rule["metric"] if rule else "danger"
    if change.evidence.get("station_id") != config.station_id or change.evidence["sample"]["metric"] != metric:
        return "suppressed"
    cache = session.get(RiverSourceCache, "danger" if metric == "danger" else config.station_id, populate_existing=True)
    if cache is None or cache.error or cache.fetched_at is None or not now - timedelta(minutes=60) <= _utc(cache.fetched_at) <= now:
        return "deferred"
    try:
        coverage = source_preview(session, monitor.configuration, now)["coverage"].get(metric)
    except DomainError:
        return "deferred"
    if not coverage or coverage["status"] != "current" or condition.get("status") != "current":
        return "deferred"
    sample = coverage["sample"]
    if not fresh(sample, now) or _utc(sample["timestamp"]) > now or condition.get("watermark") != sample["timestamp"]:
        return "deferred"
    if rule:
        selected = next(item for item in config.rules if item.model_dump(mode="json") == rule)
        value, _ = _rule_value(selected, sample, [item for item in samples(session, config.station_id,
            start=now - timedelta(hours=49)) if item["metric"] == metric])
        if value is None:
            return "deferred"
        observed = int(value > selected.threshold)
    else:
        value = Decimal(sample["value"])
        if value != value.to_integral_value() or not 1 <= value <= 5:
            return "deferred"
        observed = int(value)
    if observed != change.evidence["current_state"] or observed != condition.get("last_known"):
        return "suppressed"
    return "eligible"


def eligibility(session, monitor, intent, *, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or intent.organization_id != monitor.organization_id or not now - MAX_AGE <= _utc(intent.created_at) <= now):
        return "suppressed", None
    change = session.scalar(select(RiverChange).where(RiverChange.id == intent.change_id,
        RiverChange.monitor_id == monitor.id, RiverChange.organization_id == monitor.organization_id,
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
    duplicates = set(session.scalars(select(RiverDelivery.state).where(
        RiverDelivery.organization_id == monitor.organization_id, RiverDelivery.owner_user_id == monitor.owner_user_id,
        RiverDelivery.signal_hash == intent.signal_hash, RiverDelivery.id != intent.id,
        RiverDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "deferred", None
    return "eligible", {"href": f"/river-watch?monitor={monitor.id}&change={change.id}",
                        "detected_at": _utc(change.created_at).isoformat()}


def pending(monitor, now):
    return (select(RiverDelivery).where(RiverDelivery.monitor_id == monitor.id,
        RiverDelivery.organization_id == monitor.organization_id, RiverDelivery.state == "pending",
        RiverDelivery.due_at <= now, RiverDelivery.consent_revision == monitor.email_revision)
        .order_by(RiverDelivery.due_at, RiverDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(RiverDelivery.sent_at, RiverDelivery.claimed_at)
    return session.scalar(select(RiverDelivery.id).where(RiverDelivery.monitor_id == monitor.id,
        RiverDelivery.organization_id == monitor.organization_id,
        RiverDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def retry_at(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now + timedelta(seconds=60))


def preview(session, settings, user_id, monitor_id, *, now=None):
    from .river_runtime import owned
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
        session.execute(update(RiverDelivery).where(RiverDelivery.state == "sending",
            RiverDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(RiverDelivery).where(RiverDelivery.state == "pending",
            RiverDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active = exists(select(jobs.Job.id).where(jobs.Job.type == "river_email", jobs.Job.target_type == "river_monitor",
            jobs.Job.target_id == RiverDelivery.monitor_id, jobs.Job.organization_id == RiverDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)))
        candidates = list(session.execute(select(RiverDelivery.monitor_id, RiverDelivery.organization_id).where(
            RiverDelivery.state == "pending", RiverDelivery.due_at <= now, ~active)
            .group_by(RiverDelivery.monitor_id, RiverDelivery.organization_id)
            .order_by(func.min(RiverDelivery.due_at), RiverDelivery.monitor_id).limit(100)))
        session.commit()
    if not settings.river_watch_enabled or settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(RiverMonitor).where(RiverMonitor.id == identifier).with_for_update())
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
                session.execute(update(RiverDelivery).where(RiverDelivery.monitor_id == identifier,
                    RiverDelivery.state == "pending", RiverDelivery.due_at <= now)
                    .values(due_at=next_delivery_at(config, now + timedelta(minutes=1))))
                session.commit()
                continue
            active_job = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "river_email",
                jobs.Job.target_type == "river_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active_job is None:
                _, reused = jobs.enqueue(session, job_type="river_email", target_type="river_monitor", target_id=identifier,
                    queue="maintenance", max_attempts=1, payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"river-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("River / Lake Watch: station updates", "Review new changes at your monitored station. Observations are not a regional forecast.", "Open River / Lake Watch", "Turn off email in monitor settings to unsubscribe."),
    "de": ("River / Lake Watch: Stationsänderungen", "Prüfen Sie neue Änderungen an Ihrer überwachten Station. Messungen sind keine regionale Vorhersage.", "River / Lake Watch öffnen", "Zum Abbestellen E-Mail in den Monitoreinstellungen ausschalten."),
    "fr": ("River / Lake Watch : changements à la station", "Consultez les changements à votre station surveillée. Les observations ne sont pas une prévision régionale.", "Ouvrir River / Lake Watch", "Désactivez les e-mails dans les réglages du suivi pour vous désabonner."),
    "it": ("River / Lake Watch: aggiornamenti della stazione", "Esamina le modifiche alla stazione monitorata. Le osservazioni non sono una previsione regionale.", "Apri River / Lake Watch", "Disattiva le e-mail nelle impostazioni del monitoraggio per annullare l’iscrizione."),
    "rm": ("River / Lake Watch: midadas da la staziun", "Controllai las novas midadas da Vossa staziun observada. Observaziuns n’èn betg ina prognosa regiunala.", "Avrir River / Lake Watch", "Deactivai ils e-mails en ils parameters da l’observaziun per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/river-watch?monitor={monitor.id}"
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
        monitor = session.scalar(select(RiverMonitor).where(RiverMonitor.id == monitor_id).with_for_update())
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
        monitor = session.scalar(select(RiverMonitor).where(RiverMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(RiverDelivery).where(RiverDelivery.id.in_(identifiers),
            RiverDelivery.monitor_id == monitor_id, RiverDelivery.state == "sending").with_for_update()))
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
                message_id=f"<river-{fingerprint(sorted(row.id for row in rows))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
