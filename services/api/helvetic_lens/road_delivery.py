"""Consent-bound saved road notices; claim/recheck before real SMTP.

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
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at
from .road_catalog import CatalogReadBudget, _rights, resolve_reference
from .road_email_preferences import EmailConfiguration, cancel_email_work, policy
from .road_events import _proof, event_view
from .road_models import (
    RoadCorridorMap,
    RoadDelivery,
    RoadDevelopment,
    RoadEventVersion,
    RoadMonitor,
    RoadSourceChange,
)
from .road_repository import owned
from .road_sources import _clock as clock
from .road_sources import _encoded, _hash, require_permission
from .road_sources import _utc as utc
from .road_today import urgent

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def signal_hash(session, event, snapshot):
    # Provider situation + exact material source identity deduplicates overlapping
    # private routes; it does not include private labels or raw geometry.
    change = session.scalar(select(RoadSourceChange).where(RoadSourceChange.permission_id == event.permission_id,
        RoadSourceChange.source_id == event.source_id, RoadSourceChange.generation <= snapshot.proof["source_generation"])
        .order_by(RoadSourceChange.generation.desc()).limit(1))
    if change is None:
        raise DomainError("Road notification identity is unavailable.", 409, "road_notification_identity_unavailable")
    return _hash(_encoded({"permission": event.permission_id, "source": event.source_id,
        "semantic": snapshot.proof["source_semantic_hash"],
        "material_source_change": change.id,
        "states": sorted({item["state"] for item in _read_states(snapshot)})}))


def _read_states(snapshot):
    from .road_events import _read
    return _read(snapshot.payload, snapshot.payload_hash)["corridors"].values()


def notification_evidence(session, event, snapshot, *, now, current=False):
    payload = _proof(session, event, snapshot, now=now)
    require_permission(session, event.permission_id, now=now,
        fields=snapshot.proof["fields"], notification=True)
    budget = CatalogReadBudget()
    for identifier in snapshot.proof["mapping_ids"]:
        mapped = session.get(RoadCorridorMap, identifier)
        if mapped is None:
            raise DomainError("Road notification evidence is unavailable.", 409, "road_notification_unavailable")
        topology, _ = _rights(session, mapped.topology_id, now=now, matching=True, display=True, notification=True)
        if current:
            latest = resolve_reference(session, mapped.reference_id,
                table_key=(topology.country, topology.table, topology.version), now=now,
                display=True, notification=True, read_budget=budget)
            if latest.mapping_id != mapped.id:
                raise DomainError("Road mapping changed before notification.", 409, "road_notification_mapping_changed")
    return payload


def record_intent(session, monitor, event, snapshot, now):
    current = policy(session, monitor)
    if current is None or utc(current.created_at) > now:
        return
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if (config.delivery.email == "off" or user.email_verified_at is None
            or user.email != current.recipient_email or monitor.status != "active"):
        return
    try:
        payload = notification_evidence(session, event, snapshot, now=now, current=True)
        view = event_view(session, event, now=now)
        identity = signal_hash(session, event, snapshot)
        if view["availability"] != "available" or payload["state"] == "unavailable":
            return
    except DomainError:
        return
    session.add(RoadDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
        owner_user_id=monitor.owner_user_id, development_id=event.id, sequence=snapshot.sequence,
        consent_revision=current.revision, signal_hash=identity,
        priority="urgent" if urgent(view, now=now) else "normal",
        due_at=next_delivery_at(config, now), created_at=now))


def context(session, settings, monitor, revision, now):
    if not settings.road_watch_enabled or not settings.road_source_enabled:
        raise DomainError("Road delivery is unavailable.", 409, "road_delivery_unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id)
        .with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active"
            or current is None or current.revision != revision or utc(current.created_at) > now
            or user.email_verified_at is None or user.email != current.recipient_email):
        raise DomainError("Road email consent is no longer applicable.", 409, "road_delivery_unavailable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise DomainError("Email is turned off.", 409, "road_delivery_unavailable")
    return config, user


def eligibility(session, settings, monitor, intent, config, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or not now - MAX_AGE <= utc(intent.created_at) <= now):
        return "suppressed", None
    try:
        event = session.scalar(select(RoadDevelopment).where(RoadDevelopment.id == intent.development_id,
            RoadDevelopment.monitor_id == monitor.id, RoadDevelopment.organization_id == monitor.organization_id))
        snapshot = session.scalar(select(RoadEventVersion).where(RoadEventVersion.development_id == intent.development_id,
            RoadEventVersion.organization_id == monitor.organization_id, RoadEventVersion.sequence == intent.sequence))
        if (event is None or snapshot is None or event.configuration_revision != monitor.revision
                or event.sequence != intent.sequence or event.muted or event.reviewed_sequence >= intent.sequence
                or event.permission_id != settings.road_source_permission_id
                or signal_hash(session, event, snapshot) != intent.signal_hash):
            return "suppressed", None
        notification_evidence(session, event, snapshot, now=now)
        notification_evidence(session, event, event, now=now, current=True)
        current = event_view(session, event, now=now)
        if current["availability"] != "available" or current["payload"]["state"] == "unavailable":
            return "suppressed", None
    except (DomainError, ValueError, KeyError, TypeError):
        return "suppressed", None
    duplicates = set(session.scalars(select(RoadDelivery.state).where(
        RoadDelivery.organization_id == monitor.organization_id, RoadDelivery.owner_user_id == monitor.owner_user_id,
        RoadDelivery.signal_hash == intent.signal_hash, RoadDelivery.id != intent.id,
        RoadDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "duplicate_wait", None
    return "eligible", {"event_id": event.id, "sequence": intent.sequence,
        "detected_at": utc(snapshot.created_at).isoformat(),
        "href": f"/road-watch?monitor={monitor.id}&event={event.id}&sequence={intent.sequence}"}


def pending(monitor, now):
    return (select(RoadDelivery).join(RoadDevelopment,
        (RoadDevelopment.id == RoadDelivery.development_id)
        & (RoadDevelopment.organization_id == RoadDelivery.organization_id)).where(
        RoadDelivery.monitor_id == monitor.id, RoadDelivery.organization_id == monitor.organization_id,
        RoadDelivery.state == "pending", RoadDelivery.due_at <= now,
        RoadDelivery.created_at >= now - MAX_AGE, RoadDelivery.consent_revision == monitor.email_revision,
        RoadDevelopment.sequence == RoadDelivery.sequence,
        RoadDevelopment.configuration_revision == monitor.revision,
        RoadDevelopment.muted.is_(False), RoadDevelopment.reviewed_sequence < RoadDelivery.sequence)
        .order_by(case((RoadDelivery.priority == "urgent", 0), else_=1), RoadDelivery.due_at, RoadDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(RoadDelivery.sent_at, RoadDelivery.claimed_at)
    return session.scalar(select(RoadDelivery.id).where(RoadDelivery.monitor_id == monitor.id,
        RoadDelivery.organization_id == monitor.organization_id, RoadDelivery.consent_revision == monitor.email_revision,
        RoadDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def prune(session, monitor, now):
    current = select(RoadDevelopment.id).where(RoadDevelopment.id == RoadDelivery.development_id,
        RoadDevelopment.organization_id == monitor.organization_id, RoadDevelopment.monitor_id == monitor.id,
        RoadDevelopment.sequence == RoadDelivery.sequence, RoadDevelopment.configuration_revision == monitor.revision,
        RoadDevelopment.muted.is_(False), RoadDevelopment.reviewed_sequence < RoadDelivery.sequence).exists()
    session.execute(update(RoadDelivery).where(RoadDelivery.monitor_id == monitor.id,
        RoadDelivery.organization_id == monitor.organization_id, RoadDelivery.state == "pending",
        (~current) | (RoadDelivery.consent_revision != monitor.email_revision)
        | (RoadDelivery.created_at < now - MAX_AGE)).values(state="suppressed"))


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
        state, item = eligibility(session, settings, monitor, row, config, now)
        if state == "eligible":
            result["items"].append(item)
    return {**result, "more_available": len(rows) > MAX_BATCH, "quiet_hours": _quiet(config, now),
            "status": "daily_already_attempted" if daily_attempted(session, monitor, config, now) else "ready"}


def enqueue_due(database, settings, *, now=None):
    now = clock(now)
    if not settings.road_watch_enabled:
        return {"enqueued": 0}
    with database.session(include_all_organizations=True) as session:
        session.execute(update(RoadDelivery).where(RoadDelivery.state == "sending",
            RoadDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(RoadDelivery).where(RoadDelivery.state == "pending",
            RoadDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active_job = select(jobs.Job.id).where(jobs.Job.type == "road_email",
            jobs.Job.target_type == "road_monitor", jobs.Job.target_id == RoadDelivery.monitor_id,
            jobs.Job.organization_id == RoadDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).exists()
        candidates = list(session.execute(select(RoadDelivery.monitor_id, RoadDelivery.organization_id).where(
            RoadDelivery.state == "pending", RoadDelivery.due_at <= now, ~active_job)
            .group_by(RoadDelivery.monitor_id, RoadDelivery.organization_id)
            .order_by(func.min(RoadDelivery.due_at), RoadDelivery.monitor_id).limit(100)))
        session.commit()
    if settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(RoadMonitor).where(RoadMonitor.id == identifier).with_for_update())
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
                session.execute(update(RoadDelivery).where(RoadDelivery.monitor_id == identifier,
                    RoadDelivery.organization_id == organization, RoadDelivery.state == "pending",
                    RoadDelivery.due_at <= now).values(due_at=next_delivery_at(config, now + timedelta(minutes=1)))
                    .execution_options(synchronize_session=False))
                session.commit()
                continue
            active = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "road_email",
                jobs.Job.target_type == "road_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active is None and not daily_attempted(session, monitor, config, now):
                _, reused = jobs.enqueue(session, job_type="road_email", target_type="road_monitor",
                    target_id=identifier, queue="maintenance", max_attempts=1, priority=9 if first.priority == "urgent" else 5,
                    payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"road-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("Road Watch: saved road changes", "Review saved road changes", "Open Road Watch", "Turn off email in the route settings to unsubscribe."),
    "de": ("Road Watch: gespeicherte Strassenänderungen", "Gespeicherte Strassenänderungen prüfen", "Road Watch öffnen", "Zum Abbestellen E-Mail in den Routeneinstellungen ausschalten."),
    "fr": ("Road Watch : changements routiers enregistrés", "Consulter les changements routiers enregistrés", "Ouvrir Road Watch", "Désactivez les e-mails dans les paramètres de l’itinéraire pour vous désabonner."),
    "it": ("Road Watch: cambiamenti stradali salvati", "Esamina i cambiamenti stradali salvati", "Apri Road Watch", "Disattiva le e-mail nelle impostazioni del percorso per annullare l’iscrizione."),
    "rm": ("Road Watch: midadas da vias memorisadas", "Controllar las midadas da vias memorisadas", "Avrir Road Watch", "Deactivai ils e-mails en las configuraziuns da la ruta per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/road-watch?monitor={monitor.id}"
    lines = [f"{item['detected_at']}: {root}{item['href']}" for item in items]
    links = [f'<li><a href="{escape(root + item["href"], quote=True)}">{escape(item["detected_at"])}</a></li>' for item in items]
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
        monitor = session.scalar(select(RoadMonitor).where(RoadMonitor.id == monitor_id).with_for_update())
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
            state, _ = eligibility(session, settings, monitor, row, config, now)
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
        monitor = session.scalar(select(RoadMonitor).where(RoadMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(RoadDelivery).where(RoadDelivery.id.in_(ids),
            RoadDelivery.monitor_id == monitor_id, RoadDelivery.state == "sending").with_for_update()))
        now = now if fixed else clock()
        try:
            if not permitted_job or monitor is None or len(rows) != len(ids):
                raise ValueError("Claim is no longer available")
            config, user = context(session, settings, monitor, consent_revision, now)
            selected, items = [], []
            for row in rows:
                state, item = eligibility(session, settings, monitor, row, config, now)
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
                message_id=f"<road-{_hash(_encoded(sorted(row.id for row in rows)))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
