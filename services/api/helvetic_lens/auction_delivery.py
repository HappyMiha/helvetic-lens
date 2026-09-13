"""Consent-bound auction notices. Unknown SMTP outcomes are never retried."""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.orm import aliased

from . import jobs
from .auction_contracts import AuctionProfile, clock, fingerprint
from .auction_email_preferences import EmailConfiguration, cancel_email_work, policy
from .auction_models import AuctionMonitor
from .auction_reminders import eligible as reminder_eligible
from .auction_rules import assessment
from .auction_sources import read_revision, require_permission
from .auction_workflow import _current, _utc
from .auction_workflow_models import (
    AuctionDecision,
    AuctionDelivery,
    AuctionItem,
    AuctionItemEvent,
    AuctionReminder,
)
from .auth_mail import AuthMailer
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)
TRANSIENT = {"auction_source_stale", "auction_item_refresh_required"}


def _now(value=None):
    return clock(value or datetime.now(UTC))


def signal(item, *, event=None, reminder=None):
    return fingerprint({"item": item.id, "event": event.id} if event else
        {"item": item.id, "deadline_generation": reminder.deadline_generation, "hours": reminder.hours})


def prepare_monitor(session, monitor, *, now):
    """Retain bounded private intents during normal source/reminder processing.

    Preparation does not imply notification rights or send permission. All source
    evidence is checked at claim and again at the final send boundary.
    """
    now = _now(now)
    current = policy(session, monitor)
    if current is None or monitor.status != "active" or _utc(current.created_at) > now:
        return 0
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if config.delivery.email == "off" or user is None or user.email_verified_at is None or current.recipient_email != user.email:
        return 0
    latest = select(func.max(AuctionItemEvent.sequence)).where(
        AuctionItemEvent.item_id == AuctionItem.id, AuctionItemEvent.organization_id == monitor.organization_id,
        AuctionItemEvent.profile_revision == monitor.revision, AuctionItemEvent.notify.is_(True)).correlate(AuctionItem).scalar_subquery()
    recorded = exists(select(AuctionDelivery.id).where(AuctionDelivery.event_id == AuctionItemEvent.id,
        AuctionDelivery.monitor_id == monitor.id, AuctionDelivery.consent_revision == current.revision))
    events = list(session.execute(select(AuctionItem, AuctionItemEvent).join(AuctionItemEvent,
        and_(AuctionItemEvent.item_id == AuctionItem.id, AuctionItemEvent.organization_id == monitor.organization_id,
             AuctionItemEvent.sequence == latest)).where(AuctionItem.monitor_id == monitor.id,
        AuctionItem.profile_revision == monitor.revision, AuctionItemEvent.sequence > AuctionItem.reviewed_sequence,
        AuctionItemEvent.created_at >= max(now - MAX_AGE, _utc(current.created_at)), AuctionItemEvent.created_at <= now,
        ~recorded).order_by(AuctionItemEvent.created_at, AuctionItemEvent.id).limit(MAX_BATCH)))
    prior = aliased(AuctionReminder)
    recorded_reminder = exists(select(AuctionDelivery.id).join(prior, prior.id == AuctionDelivery.reminder_id).where(
        prior.item_id == AuctionReminder.item_id, prior.deadline_generation == AuctionReminder.deadline_generation,
        prior.hours == AuctionReminder.hours, AuctionDelivery.monitor_id == monitor.id,
        AuctionDelivery.consent_revision == current.revision))
    reminders = list(session.execute(select(AuctionItem, AuctionReminder).join(AuctionReminder,
        and_(AuctionReminder.item_id == AuctionItem.id, AuctionReminder.organization_id == monitor.organization_id)).where(
        AuctionItem.monitor_id == monitor.id, AuctionItem.following.is_(True),
        AuctionReminder.profile_revision == monitor.revision, AuctionReminder.deadline_generation == AuctionItem.deadline_generation,
        AuctionReminder.state == "ready", AuctionReminder.ends_at > now, ~recorded_reminder)
        .order_by(AuctionReminder.ends_at, AuctionReminder.id).limit(MAX_BATCH)))
    for item, event in events:
        session.add(AuctionDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
            owner_user_id=monitor.owner_user_id, item_id=item.id, event_id=event.id,
            consent_revision=current.revision, signal_hash=signal(item, event=event),
            due_at=next_delivery_at(config, now), created_at=now))
    added = len(events)
    for item, reminder in reminders:
        identity = signal(item, reminder=reminder)
        if session.scalar(select(AuctionDelivery.id).where(AuctionDelivery.monitor_id == monitor.id,
            AuctionDelivery.consent_revision == current.revision, AuctionDelivery.signal_hash == identity).limit(1)):
            continue
        session.add(AuctionDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
            owner_user_id=monitor.owner_user_id, item_id=item.id, reminder_id=reminder.id,
            consent_revision=current.revision, signal_hash=identity, due_at=next_delivery_at(config, now), created_at=now))
        added += 1
    session.flush()
    return added


def context(session, settings, monitor, revision, now):
    if not settings.auction_watch_enabled:
        raise ValueError("Auction email is unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id).with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or current is None or current.revision != revision
            or _utc(current.created_at) > now or user is None or user.email_verified_at is None or user.email != current.recipient_email):
        raise ValueError("Auction email consent is no longer applicable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise ValueError("Auction email is off")
    return config, user


def eligibility(session, monitor, intent, *, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or intent.organization_id != monitor.organization_id or not now - MAX_AGE <= _utc(intent.created_at) <= now):
        return "suppressed", None
    item = session.scalar(select(AuctionItem).where(AuctionItem.id == intent.item_id,
        AuctionItem.monitor_id == monitor.id, AuctionItem.organization_id == monitor.organization_id))
    if item is None or item.profile_revision != monitor.revision:
        return "suppressed", None
    try:
        require_permission(session, item.permission_id, now=now, purpose="matching")
        require_permission(session, item.permission_id, now=now, purpose="display")
        facts, _, _ = _current(session, monitor, item, now=now, purpose="notification")
        if intent.event_id:
            event = session.scalar(select(AuctionItemEvent).where(AuctionItemEvent.id == intent.event_id,
                AuctionItemEvent.item_id == item.id, AuctionItemEvent.organization_id == monitor.organization_id))
            latest = session.scalar(select(func.max(AuctionItemEvent.sequence)).where(AuctionItemEvent.item_id == item.id,
                AuctionItemEvent.profile_revision == monitor.revision, AuctionItemEvent.notify.is_(True)))
            if (event is None or event.sequence != latest or event.sequence <= item.reviewed_sequence
                    or event.profile_revision != monitor.revision or not event.notify
                    or not now - MAX_AGE <= _utc(event.created_at) <= now or signal(item, event=event) != intent.signal_hash):
                return "suppressed", None
            if not item.following:
                stopped = session.scalar(select(AuctionDecision.id).where(AuctionDecision.item_id == item.id,
                    AuctionDecision.organization_id == monitor.organization_id, AuctionDecision.following.is_(False)).limit(1))
                if event.kind != "new_match" or stopped or assessment(AuctionProfile.model_validate(monitor.configuration), facts)["status"] != "match":
                    return "suppressed", None
            observed = read_revision(session, item.permission_id, event.source_revision_id, now=now, purpose="notification")
            if observed.identity() != facts.identity():
                return "suppressed", None
            value = {"kind": "material", "href": f"/auction-watch?monitor={monitor.id}&event={event.id}",
                     "detected_at": _utc(event.created_at).isoformat()}
        else:
            reminder = session.get(AuctionReminder, intent.reminder_id)
            if reminder is None or reminder.state != "ready" or signal(item, reminder=reminder) != intent.signal_hash:
                return "suppressed", None
            ready, reason = reminder_eligible(session, monitor, item, reminder, now=now)
            if not ready:
                return ("deferred" if reason in {"auction_not_started", "source_not_current", "outside_window"} else "suppressed"), None
            value = {"kind": "ending_soon", "href": f"/auction-watch?monitor={monitor.id}&reminder={reminder.id}",
                     "detected_at": _utc(reminder.activated_at).isoformat()}
    except DomainError as error:
        return ("deferred" if error.code in TRANSIENT else "suppressed"), None
    duplicates = set(session.scalars(select(AuctionDelivery.state).where(AuctionDelivery.organization_id == monitor.organization_id,
        AuctionDelivery.owner_user_id == monitor.owner_user_id, AuctionDelivery.signal_hash == intent.signal_hash,
        AuctionDelivery.id != intent.id, AuctionDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "deferred", None
    return "eligible", value


def pending(monitor, now):
    return (select(AuctionDelivery).where(AuctionDelivery.monitor_id == monitor.id,
        AuctionDelivery.organization_id == monitor.organization_id, AuctionDelivery.state == "pending",
        AuctionDelivery.due_at <= now, AuctionDelivery.consent_revision == monitor.email_revision)
        .order_by(AuctionDelivery.due_at, AuctionDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(AuctionDelivery.sent_at, AuctionDelivery.claimed_at)
    return session.scalar(select(AuctionDelivery.id).where(AuctionDelivery.monitor_id == monitor.id,
        AuctionDelivery.organization_id == monitor.organization_id,
        AuctionDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def retry_at(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now + timedelta(seconds=60))


def preview(session, settings, user_id, monitor_id, *, now=None):
    from .auction_repository import owned
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
        session.execute(update(AuctionDelivery).where(AuctionDelivery.state == "sending",
            AuctionDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(AuctionDelivery).where(AuctionDelivery.state == "pending",
            AuctionDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active = exists(select(jobs.Job.id).where(jobs.Job.type == "auction_email", jobs.Job.target_type == "auction_monitor",
            jobs.Job.target_id == AuctionDelivery.monitor_id, jobs.Job.organization_id == AuctionDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)))
        candidates = list(session.execute(select(AuctionDelivery.monitor_id, AuctionDelivery.organization_id).where(
            AuctionDelivery.state == "pending", AuctionDelivery.due_at <= now, ~active)
            .group_by(AuctionDelivery.monitor_id, AuctionDelivery.organization_id)
            .order_by(func.min(AuctionDelivery.due_at), AuctionDelivery.monitor_id).limit(100)))
        session.commit()
    if not settings.auction_watch_enabled or settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == identifier).with_for_update())
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
                session.execute(update(AuctionDelivery).where(AuctionDelivery.monitor_id == identifier,
                    AuctionDelivery.state == "pending", AuctionDelivery.due_at <= now)
                    .values(due_at=next_delivery_at(config, now + timedelta(minutes=1))))
                session.commit()
                continue
            active_job = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "auction_email",
                jobs.Job.target_type == "auction_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active_job is None:
                _, reused = jobs.enqueue(session, job_type="auction_email", target_type="auction_monitor", target_id=identifier,
                    queue="maintenance", max_attempts=1, payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"auction-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("Auction Watch: saved updates and reminders", "Review your private auction updates and ending-soon reminders.", "Open Auction Watch", "Turn off email in the profile settings to unsubscribe."),
    "de": ("Auction Watch: Änderungen und Erinnerungen", "Prüfen Sie Ihre privaten Auktionsänderungen und Erinnerungen an das Auktionsende.", "Auction Watch öffnen", "Zum Abbestellen E-Mail in den Profileinstellungen ausschalten."),
    "fr": ("Auction Watch : changements et rappels", "Consultez vos changements d’enchères privés et les rappels de fin prochaine.", "Ouvrir Auction Watch", "Désactivez les e-mails dans les réglages du profil pour vous désabonner."),
    "it": ("Auction Watch: modifiche e promemoria", "Esamina le modifiche private delle aste e i promemoria di prossima conclusione.", "Apri Auction Watch", "Disattiva le e-mail nelle impostazioni del profilo per annullare l’iscrizione."),
    "rm": ("Auction Watch: midadas e regurdanzas", "Controllai Vossas midadas privatas d’inchants e las regurdanzas a la fin imminenta.", "Avrir Auction Watch", "Deactivai ils e-mails en ils parameters dal profil per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/auction-watch?monitor={monitor.id}"
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
        monitor = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == monitor_id).with_for_update())
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
        monitor = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(AuctionDelivery).where(AuctionDelivery.id.in_(identifiers),
            AuctionDelivery.monitor_id == monitor_id, AuctionDelivery.state == "sending").with_for_update()))
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
                message_id=f"<auction-{fingerprint(sorted(row.id for row in rows))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
