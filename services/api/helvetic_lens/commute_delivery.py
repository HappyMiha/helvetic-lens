"""Consent-bound saved transport notices; claim/recheck before real SMTP.

An uncertain send is never automatically retried. Source evidence stays behind
the authenticated exact-version reader; receiving mail does not review an event.
"""

from datetime import UTC, date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, update

from . import jobs
from .auth_mail import AuthMailer
from .commute_catalog import resolve_configuration
from .commute_contracts import digest
from .commute_email_preferences import EmailConfiguration, cancel_email_work, policy
from .commute_interchanges import require_interchanges
from .commute_models import CommuteDelivery, CommuteDevelopment, CommuteMonitor, CommuteSignal
from .commute_repository import configuration, owned
from .commute_sources import clock, utc
from .commute_today import detail
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at
from .transport_reference import ZURICH

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def signal_hash(evidence):
    return digest({key: evidence.get(key) for key in
        ("source", "static_version", "provider_entity_id", "service_day", "entity_sha256", "feed_observed_at")})


def record_intent(session, monitor, event, signal, evidence, now):
    current = policy(session, monitor)
    if current is None or utc(current.created_at) > now:
        return
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if (config.delivery.email == "off" or user.email_verified_at is None or user.email != current.recipient_email
            or signal.delivery_kind == "digest_candidate" and config.delivery.email != "daily_digest"):
        return
    session.add(CommuteDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
        owner_user_id=monitor.owner_user_id, development_id=event.id, sequence=signal.sequence,
        consent_revision=current.revision, signal_hash=signal_hash(evidence), priority=signal.priority,
        due_at=next_delivery_at(config, now), created_at=now))


def context(session, settings, monitor, revision, now):
    if not settings.commute_watch_enabled or not settings.commute_source_enabled:
        raise DomainError("Transport delivery is unavailable.", 409, "commute_delivery_unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id)
        .with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or monitor.paused_on == now.astimezone(ZURICH).date()
            or current is None or current.revision != revision or utc(current.created_at) > now
            or user.email_verified_at is None or user.email != current.recipient_email):
        raise DomainError("Transport email consent is no longer applicable.", 409, "commute_delivery_unavailable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise DomainError("Email is turned off.", 409, "commute_delivery_unavailable")
    return config, user


def eligibility(session, monitor, intent, config, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or not now - MAX_AGE <= utc(intent.created_at) <= now):
        return "suppressed", None
    try:
        linked = detail(session, monitor.owner_user_id, intent.development_id, now=now,
                        sequence=intent.sequence, monitor_id=monitor.id)
        event = linked["event"]
        signal = session.scalar(select(CommuteSignal).where(CommuteSignal.development_id == intent.development_id,
            CommuteSignal.organization_id == monitor.organization_id, CommuteSignal.sequence == intent.sequence))
        journey = configuration(monitor.configuration)
        if len(journey.leg_reference_ids) > 1:
            legs = resolve_configuration(session, journey, service_day=date.fromisoformat(event["service_day"]),
                static_version=linked["snapshot"]["evidence"]["static_version"])
            require_interchanges(session, journey, legs)
        if (not linked["current_configuration"] or event["sequence"] != intent.sequence
                or event["muted"] or event["reviewed_sequence"] >= intent.sequence
                or signal is None or signal.state != "pending"
                or signal.delivery_kind == "digest_candidate" and config.delivery.email != "daily_digest"
                or signal_hash(linked["snapshot"]["evidence"]) != intent.signal_hash):
            return "suppressed", None
        if config.delivery.email == "immediate" and not any(
                state["availability"] == "present" for state in event["current"]["states"].values()):
            return "suppressed", None
    except (DomainError, ValueError, KeyError, TypeError):
        return "suppressed", None
    duplicates = set(session.scalars(select(CommuteDelivery.state).where(
        CommuteDelivery.organization_id == monitor.organization_id, CommuteDelivery.owner_user_id == monitor.owner_user_id,
        CommuteDelivery.signal_hash == intent.signal_hash, CommuteDelivery.id != intent.id,
        CommuteDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "duplicate_wait", None
    return "eligible", {"event_id": event["id"], "sequence": intent.sequence, "service_day": event["service_day"],
        "href": f"/commute-watch?monitor={monitor.id}&event={event['id']}&sequence={intent.sequence}"}


def pending(monitor, now):
    return (select(CommuteDelivery).join(CommuteDevelopment,
        (CommuteDevelopment.id == CommuteDelivery.development_id)
        & (CommuteDevelopment.organization_id == CommuteDelivery.organization_id)).where(
        CommuteDelivery.monitor_id == monitor.id, CommuteDelivery.organization_id == monitor.organization_id,
        CommuteDelivery.state == "pending", CommuteDelivery.due_at <= now,
        CommuteDelivery.created_at >= now - MAX_AGE, CommuteDelivery.consent_revision == monitor.email_revision,
        CommuteDevelopment.sequence == CommuteDelivery.sequence,
        CommuteDevelopment.configuration_revision == monitor.revision,
        CommuteDevelopment.muted.is_(False), CommuteDevelopment.reviewed_sequence < CommuteDelivery.sequence)
        .order_by(case((CommuteDelivery.priority == "urgent", 0), else_=1), CommuteDelivery.due_at, CommuteDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(CommuteDelivery.sent_at, CommuteDelivery.claimed_at)
    return session.scalar(select(CommuteDelivery.id).where(CommuteDelivery.monitor_id == monitor.id,
        CommuteDelivery.organization_id == monitor.organization_id, CommuteDelivery.consent_revision == monitor.email_revision,
        CommuteDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def prune(session, monitor, now):
    current = select(CommuteDevelopment.id).where(CommuteDevelopment.id == CommuteDelivery.development_id,
        CommuteDevelopment.organization_id == monitor.organization_id, CommuteDevelopment.monitor_id == monitor.id,
        CommuteDevelopment.sequence == CommuteDelivery.sequence, CommuteDevelopment.configuration_revision == monitor.revision,
        CommuteDevelopment.muted.is_(False), CommuteDevelopment.reviewed_sequence < CommuteDelivery.sequence).exists()
    session.execute(update(CommuteDelivery).where(CommuteDelivery.monitor_id == monitor.id,
        CommuteDelivery.organization_id == monitor.organization_id, CommuteDelivery.state == "pending",
        (~current) | (CommuteDelivery.consent_revision != monitor.email_revision)
        | (CommuteDelivery.created_at < now - MAX_AGE)).values(state="suppressed"))


def after_quiet(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now)


def preview(session, settings, user_id, monitor_id, *, now=None):
    now = clock(now)
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
        state, item = eligibility(session, monitor, row, config, now)
        if state == "eligible":
            result["items"].append(item)
    return {**result, "more_available": len(rows) > MAX_BATCH, "quiet_hours": _quiet(config, now),
            "status": "daily_already_attempted" if daily_attempted(session, monitor, config, now) else "ready"}


def enqueue_due(database, settings, *, now=None):
    now = clock(now)
    if not settings.commute_watch_enabled:
        return {"enqueued": 0}
    with database.session(include_all_organizations=True) as session:
        session.execute(update(CommuteDelivery).where(CommuteDelivery.state == "sending",
            CommuteDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(CommuteDelivery).where(CommuteDelivery.state == "pending",
            CommuteDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active_job = select(jobs.Job.id).where(jobs.Job.type == "commute_email",
            jobs.Job.target_type == "commute_monitor", jobs.Job.target_id == CommuteDelivery.monitor_id,
            jobs.Job.organization_id == CommuteDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).exists()
        candidates = list(session.execute(select(CommuteDelivery.monitor_id, CommuteDelivery.organization_id).where(
            CommuteDelivery.state == "pending", CommuteDelivery.due_at <= now, ~active_job)
            .group_by(CommuteDelivery.monitor_id, CommuteDelivery.organization_id)
            .order_by(func.min(CommuteDelivery.due_at), CommuteDelivery.monitor_id).limit(100)))
        session.commit()
    if settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == identifier).with_for_update())
            if monitor is None:
                continue
            try:
                config, _ = context(session, settings, monitor, monitor.email_revision, now)
            except (DomainError, ValueError):
                cancel_email_work(session, monitor)
                session.commit()
                continue
            prune(session, monitor, now)
            first = session.scalar(pending(monitor, now).limit(1))
            if first is not None and daily_attempted(session, monitor, config, now):
                # Bounded digest overflow waits until the next local schedule;
                # it must not fill every scheduler page for the rest of today.
                session.execute(update(CommuteDelivery).where(CommuteDelivery.monitor_id == identifier,
                    CommuteDelivery.organization_id == organization, CommuteDelivery.state == "pending",
                    CommuteDelivery.due_at <= now).values(due_at=next_delivery_at(config, now + timedelta(minutes=1)))
                    .execution_options(synchronize_session=False))
                session.commit()
                continue
            active = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "commute_email",
                jobs.Job.target_type == "commute_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active is None and not daily_attempted(session, monitor, config, now):
                _, reused = jobs.enqueue(session, job_type="commute_email", target_type="commute_monitor",
                    target_id=identifier, queue="maintenance", max_attempts=1, priority=9 if first.priority == "urgent" else 5,
                    payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"commute-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("Commute Watch: saved journey updates", "Review saved transport updates", "Open Commute Watch", "Turn off email in the journey settings to unsubscribe."),
    "de": ("Commute Watch: gespeicherte Fahrtänderungen", "Gespeicherte Verkehrsänderungen prüfen", "Commute Watch öffnen", "Zum Abbestellen E-Mail in den Fahrteinstellungen ausschalten."),
    "fr": ("Commute Watch : changements de trajet enregistrés", "Consulter les changements de transport enregistrés", "Ouvrir Commute Watch", "Désactivez les e-mails dans les paramètres du trajet pour vous désabonner."),
    "it": ("Commute Watch: aggiornamenti del viaggio salvati", "Esamina gli aggiornamenti dei trasporti salvati", "Apri Commute Watch", "Disattiva le e-mail nelle impostazioni del viaggio per annullare l’iscrizione."),
    "rm": ("Commute Watch: midadas dal viadi memorisadas", "Controllar las midadas dal traffic memorisadas", "Avrir Commute Watch", "Deactivai ils e-mails en las configuraziuns dal viadi per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/commute-watch?monitor={monitor.id}"
    lines = [f"{item['service_day']}: {root}{item['href']}" for item in items]
    links = [f'<li><a href="{escape(root + item["href"], quote=True)}">{escape(item["service_day"])}</a></li>' for item in items]
    body = "\n\n".join([monitor.configuration["name"], intro, *lines, f"{action}: {link}", stop])
    html = f"<p>{escape(monitor.configuration['name'])}</p><p>{escape(intro)}</p><ul>{''.join(links)}</ul>"
    html += f'<p><a href="{escape(link, quote=True)}">{escape(action)}</a></p><p>{escape(stop)}</p>'
    return title, body, html


def deliver(database, settings, *, monitor_id, consent_revision, now=None, mailer=None, before_send=None, checkpoint=lambda: True):
    fixed = now is not None
    now = clock(now)
    if not checkpoint():
        return {"status": "cancelled"}
    if mailer is None and settings.auth_email_mode != "smtp":
        return {"status": "mail_not_live"}
    ids = []
    with database.session() as session:
        monitor = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == monitor_id).with_for_update())
        if monitor is None:
            return {"status": "inactive"}
        try:
            config, _ = context(session, settings, monitor, consent_revision, now)
        except (DomainError, ValueError):
            return {"status": "unavailable"}
        if daily_attempted(session, monitor, config, now):
            return {"status": "daily_already_attempted"}
        prune(session, monitor, now)
        for row in session.scalars(pending(monitor, now).limit(MAX_BATCH)):
            state, _ = eligibility(session, monitor, row, config, now)
            if state == "suppressed":
                row.state = "suppressed"
            elif state == "duplicate_wait":
                row.due_at = now + timedelta(minutes=5)
            elif _quiet(config, now):
                row.due_at = after_quiet(config, now)
            else:
                row.state, row.claimed_at = "sending", now
                ids.append(row.id)
        session.commit()
    if not ids:
        return {"status": "no_eligible_changes"}
    if before_send is not None:
        before_send()
    permitted_job = checkpoint()
    with database.session() as session:
        monitor = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(CommuteDelivery).where(CommuteDelivery.id.in_(ids),
            CommuteDelivery.monitor_id == monitor_id, CommuteDelivery.state == "sending").with_for_update()))
        now = now if fixed else clock()
        try:
            if not permitted_job or monitor is None or len(rows) != len(ids):
                raise ValueError("Claim is no longer available")
            config, user = context(session, settings, monitor, consent_revision, now)
            selected, items = [], []
            for row in rows:
                state, item = eligibility(session, monitor, row, config, now)
                if state == "eligible":
                    selected.append(row)
                    items.append(item)
                elif state == "duplicate_wait":
                    row.state, row.claimed_at, row.due_at = "pending", None, now + timedelta(minutes=5)
                else:
                    row.state = "suppressed"
            rows = selected
            if not rows:
                session.commit()
                return {"status": "suppressed"}
            if _quiet(config, now):
                for row in rows:
                    row.state, row.claimed_at, row.due_at = "pending", None, after_quiet(config, now)
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
                message_id=f"<commute-{digest(sorted(row.id for row in rows))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
