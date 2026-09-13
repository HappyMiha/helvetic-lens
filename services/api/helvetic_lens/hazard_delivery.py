"""Consent-bound saved hazard notices; claim/recheck before real SMTP.

An uncertain send is never automatically retried. Source evidence stays behind
the authenticated exact-version reader; receiving mail does not review an event.
"""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, update

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .hazard_boundary_store import BoundaryStore
from .hazard_email_preferences import EmailConfiguration, cancel_email_work, policy
from .hazard_events import _event, read_event
from .hazard_models import (
    HazardDelivery,
    HazardDevelopment,
    HazardMonitor,
)
from .hazard_readiness import ready
from .hazard_repository import configuration, owned
from .hazard_sources import _clock, _encoded, _hash, require_permission
from .hazard_sources import _utc as utc
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def clock(value=None):
    return _clock(value)


def signal_hash(event, snapshot):
    # Material provider identity deduplicates one warning across saved places;
    # translations and private labels do not create another email.
    return _hash(_encoded({"permission": event.permission_id, "source": event.source_development_key,
        "material": snapshot.proof["source_material_sequence"]}))


def record_intent(session, monitor, event, snapshot, *, store, now):
    current = policy(session, monitor)
    if current is None or utc(current.created_at) > now:
        return
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if (config.delivery.email == "off" or user.email_verified_at is None
            or user.email != current.recipient_email or monitor.status != "active"):
        return
    try:
        require_permission(session, event.permission_id, now=now, purpose="notification")
        view = read_event(session, monitor.owner_user_id, monitor.id, event.id, store=store, now=now)
        if view["state"] == "unavailable" or not view["needs_review"] or view["muted"]:
            return
        identity = signal_hash(event, snapshot)
    except DomainError:
        return
    exists = session.scalar(select(HazardDelivery.id).where(HazardDelivery.development_id == event.id,
        HazardDelivery.material_sequence == snapshot.material_sequence,
        HazardDelivery.consent_revision == current.revision).limit(1))
    if exists is not None:
        return
    session.add(HazardDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
        owner_user_id=monitor.owner_user_id, development_id=event.id, revision=snapshot.revision,
        material_sequence=snapshot.material_sequence, consent_revision=current.revision, signal_hash=identity,
        priority="urgent" if view["decision"].get("importance") == "alarm" else "normal",
        due_at=next_delivery_at(config, now), created_at=now))


def context(session, settings, monitor, revision, now, store):
    if not settings.hazard_watch_enabled or not settings.hazard_source_enabled:
        raise DomainError("Hazard delivery is unavailable.", 409, "hazard_delivery_unavailable")
    saved_configuration = configuration(monitor.configuration)
    ready(session, settings, saved_configuration, store=store, now=now)
    monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor.id)
        .with_for_update().execution_options(populate_existing=True))
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id)
        .with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or configuration(monitor.configuration).fingerprint() != saved_configuration.fingerprint()
            or current is None or current.revision != revision or utc(current.created_at) > now
            or user.email_verified_at is None or user.email != current.recipient_email):
        raise DomainError("Hazard email consent is no longer applicable.", 409, "hazard_delivery_unavailable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise DomainError("Email is turned off.", 409, "hazard_delivery_unavailable")
    return config, user


def eligibility(session, settings, monitor, intent, config, now, store):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or not now - MAX_AGE <= utc(intent.created_at) <= now):
        return "suppressed", None
    try:
        event = session.scalar(select(HazardDevelopment).where(HazardDevelopment.id == intent.development_id,
            HazardDevelopment.monitor_id == monitor.id, HazardDevelopment.organization_id == monitor.organization_id))
        if (event is None or event.configuration_revision != monitor.revision
                or event.material_sequence != intent.material_sequence
                or event.permission_id != settings.hazard_source_permission_id):
            return "suppressed", None
        require_permission(session, event.permission_id, now=now, purpose="notification")
        current = read_event(session, monitor.owner_user_id, monitor.id, event.id, store=store, now=now)
        snapshot = _event(session, event)
        if (current["state"] == "unavailable" or not current["needs_review"] or current["muted"]
                or signal_hash(event, snapshot) != intent.signal_hash):
            return "suppressed", None
    except (DomainError, ValueError, KeyError, TypeError):
        return "suppressed", None
    duplicates = set(session.scalars(select(HazardDelivery.state).where(
        HazardDelivery.organization_id == monitor.organization_id, HazardDelivery.owner_user_id == monitor.owner_user_id,
        HazardDelivery.signal_hash == intent.signal_hash, HazardDelivery.id != intent.id,
        HazardDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "duplicate_wait", None
    return "eligible", {"event_id": event.id, "revision": snapshot.revision,
        "detected_at": utc(intent.created_at).isoformat(),
        "href": f"/hazard-watch?monitor={monitor.id}&event={event.id}&revision={snapshot.revision}"}


def pending(monitor, now):
    return (select(HazardDelivery).join(HazardDevelopment,
        (HazardDevelopment.id == HazardDelivery.development_id)
        & (HazardDevelopment.organization_id == HazardDelivery.organization_id)).where(
        HazardDelivery.monitor_id == monitor.id, HazardDelivery.organization_id == monitor.organization_id,
        HazardDelivery.state == "pending", HazardDelivery.due_at <= now,
        HazardDelivery.created_at >= now - MAX_AGE, HazardDelivery.consent_revision == monitor.email_revision,
        HazardDevelopment.material_sequence == HazardDelivery.material_sequence,
        HazardDevelopment.configuration_revision == monitor.revision,
        HazardDevelopment.reviewed_sequence < HazardDelivery.material_sequence,
        HazardDevelopment.dismissed_sequence < HazardDelivery.material_sequence)
        .order_by(case((HazardDelivery.priority == "urgent", 0), else_=1), HazardDelivery.due_at, HazardDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(HazardDelivery.sent_at, HazardDelivery.claimed_at)
    return session.scalar(select(HazardDelivery.id).where(HazardDelivery.monitor_id == monitor.id,
        HazardDelivery.organization_id == monitor.organization_id, HazardDelivery.consent_revision == monitor.email_revision,
        HazardDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def prune(session, monitor, now):
    current = select(HazardDevelopment.id).where(HazardDevelopment.id == HazardDelivery.development_id,
        HazardDevelopment.organization_id == monitor.organization_id, HazardDevelopment.monitor_id == monitor.id,
        HazardDevelopment.material_sequence == HazardDelivery.material_sequence, HazardDevelopment.configuration_revision == monitor.revision,
        HazardDevelopment.reviewed_sequence < HazardDelivery.material_sequence,
        HazardDevelopment.dismissed_sequence < HazardDelivery.material_sequence).exists()
    session.execute(update(HazardDelivery).where(HazardDelivery.monitor_id == monitor.id,
        HazardDelivery.organization_id == monitor.organization_id, HazardDelivery.state == "pending",
        (~current) | (HazardDelivery.consent_revision != monitor.email_revision)
        | (HazardDelivery.created_at < now - MAX_AGE)).values(state="suppressed"))


def after_quiet(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now)


def preview(session, settings, user_id, monitor_id, *, now=None, store=None):
    store = store or BoundaryStore(settings.storage_path)
    now = clock(now)
    monitor = owned(session, user_id, monitor_id)
    result = {"items": [], "more_available": False, "quiet_hours": False, "status": "unavailable"}
    if settings.auth_email_mode != "smtp":
        return result
    try:
        config, _ = context(session, settings, monitor, monitor.email_revision, now, store)
    except (DomainError, ValueError):
        return result
    rows = list(session.scalars(pending(monitor, now).limit(MAX_BATCH + 1)))
    for row in rows[:MAX_BATCH]:
        state, item = eligibility(session, settings, monitor, row, config, now, store)
        if state == "eligible":
            result["items"].append(item)
    return {**result, "more_available": len(rows) > MAX_BATCH, "quiet_hours": _quiet(config, now),
            "status": "daily_already_attempted" if daily_attempted(session, monitor, config, now) else "ready"}


def enqueue_due(database, settings, *, now=None, store=None):
    store = store or BoundaryStore(settings.storage_path)
    now = clock(now)
    if not settings.hazard_watch_enabled:
        return {"enqueued": 0}
    with database.session(include_all_organizations=True) as session:
        session.execute(update(HazardDelivery).where(HazardDelivery.state == "sending",
            HazardDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(HazardDelivery).where(HazardDelivery.state == "pending",
            HazardDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active_job = select(jobs.Job.id).where(jobs.Job.type == "hazard_email",
            jobs.Job.target_type == "hazard_monitor", jobs.Job.target_id == HazardDelivery.monitor_id,
            jobs.Job.organization_id == HazardDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).exists()
        candidates = list(session.execute(select(HazardDelivery.monitor_id, HazardDelivery.organization_id).where(
            HazardDelivery.state == "pending", HazardDelivery.due_at <= now, ~active_job)
            .group_by(HazardDelivery.monitor_id, HazardDelivery.organization_id)
            .order_by(func.min(HazardDelivery.due_at), HazardDelivery.monitor_id).limit(100)))
        session.commit()
    if settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == identifier))
            if monitor is None:
                continue
            try:
                config, _ = context(session, settings, monitor, monitor.email_revision, now, store)
            except (DomainError, ValueError):
                cancel_email_work(session, monitor)
                session.commit()
                continue
            prune(session, monitor, now)
            first = session.scalar(pending(monitor, now).limit(1))
            if first is not None and daily_attempted(session, monitor, config, now):
                # Bounded digest overflow waits until the next local schedule;
                # it must not fill every scheduler page for the rest of today.
                session.execute(update(HazardDelivery).where(HazardDelivery.monitor_id == identifier,
                    HazardDelivery.organization_id == organization, HazardDelivery.state == "pending",
                    HazardDelivery.due_at <= now).values(due_at=next_delivery_at(config, now + timedelta(minutes=1)))
                    .execution_options(synchronize_session=False))
                session.commit()
                continue
            active = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "hazard_email",
                jobs.Job.target_type == "hazard_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active is None and not daily_attempted(session, monitor, config, now):
                _, reused = jobs.enqueue(session, job_type="hazard_email", target_type="hazard_monitor",
                    target_id=identifier, queue="maintenance", max_attempts=1, priority=9 if first.priority == "urgent" else 5,
                    payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"hazard-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("Hazard Watch: warning changes", "Open the original official instructions before acting.", "Open Hazard Watch", "Turn off email in the saved place settings to unsubscribe."),
    "de": ("Hazard Watch: Änderungen an Warnungen", "Lesen Sie vor dem Handeln die offiziellen Originalanweisungen.", "Hazard Watch öffnen", "Zum Abbestellen E-Mail in den Einstellungen des gespeicherten Orts ausschalten."),
    "fr": ("Hazard Watch : changements d’alertes", "Lisez les consignes officielles originales avant d’agir.", "Ouvrir Hazard Watch", "Désactivez les e-mails dans les paramètres du lieu enregistré pour vous désabonner."),
    "it": ("Hazard Watch: modifiche agli avvisi", "Leggi le istruzioni ufficiali originali prima di agire.", "Apri Hazard Watch", "Disattiva le e-mail nelle impostazioni del luogo salvato per annullare l’iscrizione."),
    "rm": ("Hazard Watch: midadas d’avertiments", "Legiai las instrucziuns uffizialas originalas avant d’agir.", "Avrir Hazard Watch", "Deactivai ils e-mails en las configuraziuns dal lieu memorisà per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/hazard-watch?monitor={monitor.id}"
    lines = [f"{item['detected_at']}: {root}{item['href']}" for item in items]
    links = [f'<li><a href="{escape(root + item["href"], quote=True)}">{escape(item["detected_at"])}</a></li>' for item in items]
    body = "\n\n".join([monitor.configuration["name"], intro, *lines, f"{action}: {link}", stop])
    html = f"<p>{escape(monitor.configuration['name'])}</p><p>{escape(intro)}</p><ul>{''.join(links)}</ul>"
    html += f'<p><a href="{escape(link, quote=True)}">{escape(action)}</a></p><p>{escape(stop)}</p>'
    return title, body, html


def deliver(database, settings, *, monitor_id, consent_revision, now=None, mailer=None, before_send=None, checkpoint=lambda: True, store=None):
    store = store or BoundaryStore(settings.storage_path)
    fixed = now is not None
    now = clock(now)
    if not checkpoint():
        return {"status": "cancelled"}
    if mailer is None and settings.auth_email_mode != "smtp":
        return {"status": "mail_not_live"}
    ids = []
    with database.session() as session:
        monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor_id))
        if monitor is None:
            return {"status": "inactive"}
        try:
            config, _ = context(session, settings, monitor, consent_revision, now, store)
        except (DomainError, ValueError):
            return {"status": "unavailable"}
        if daily_attempted(session, monitor, config, now):
            return {"status": "daily_already_attempted"}
        prune(session, monitor, now)
        for row in session.scalars(pending(monitor, now).limit(MAX_BATCH)):
            state, _ = eligibility(session, settings, monitor, row, config, now, store)
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
        monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor_id))
        rows = list(session.scalars(select(HazardDelivery).where(HazardDelivery.id.in_(ids),
            HazardDelivery.monitor_id == monitor_id, HazardDelivery.state == "sending").with_for_update()))
        now = now if fixed else clock()
        try:
            if not permitted_job or monitor is None or len(rows) != len(ids):
                raise ValueError("Claim is no longer available")
            config, user = context(session, settings, monitor, consent_revision, now, store)
            selected, items = [], []
            for row in rows:
                state, item = eligibility(session, settings, monitor, row, config, now, store)
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
                message_id=f"<hazard-{_hash(_encoded(sorted(row.id for row in rows)))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
