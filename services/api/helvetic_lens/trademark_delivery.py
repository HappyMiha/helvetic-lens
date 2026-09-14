"""Verified-owner private IP notifications, with exact event links and no legal claims."""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, func, select, update

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at
from .trademark_contracts import fingerprint
from .trademark_email_models import TrademarkDelivery
from .trademark_email_preferences import EmailConfiguration, cancel_email_work, policy
from .trademark_models import TrademarkMonitor
from .trademark_sources import _clock, _utc, read_revision, require_permission
from .trademark_workflow import current as current_candidate
from .trademark_workflow_models import TrademarkCandidate, TrademarkCandidateEvent

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)
TRANSIENT = {"trademark_evidence_stale", "trademark_candidate_refresh_required"}


def _now(value=None):
    return _clock(value or datetime.now(UTC))


def signal(candidate, event):
    return fingerprint({"candidate": candidate.id, "event": event.id})


def source_change(event):
    return bool({"new_candidate", "register_changed"} & set(event.change_codes))


def prepare_monitor(session, monitor, *, now):
    """Called under the private monitor lock; no history before consent is queued."""
    now = _now(now)
    current = policy(session, monitor)
    if current is None or monitor.status != "active" or _utc(current.created_at) > now:
        return 0
    config = EmailConfiguration.model_validate(current.configuration)
    user = session.get(User, monitor.owner_user_id)
    if config.delivery.email == "off" or user is None or user.email_verified_at is None or current.recipient_email != user.email:
        return 0
    recorded = exists(select(TrademarkDelivery.id).where(
        TrademarkDelivery.event_id == TrademarkCandidateEvent.id,
        TrademarkDelivery.monitor_id == monitor.id, TrademarkDelivery.consent_revision == current.revision))
    rows = list(session.execute(select(TrademarkCandidate, TrademarkCandidateEvent).join(TrademarkCandidateEvent,
        and_(TrademarkCandidateEvent.candidate_id == TrademarkCandidate.id,
             TrademarkCandidateEvent.organization_id == monitor.organization_id,
             TrademarkCandidateEvent.sequence == TrademarkCandidate.sequence)).where(
        TrademarkCandidate.monitor_id == monitor.id, TrademarkCandidate.organization_id == monitor.organization_id,
        TrademarkCandidate.profile_revision == monitor.revision,
        TrademarkCandidateEvent.profile_revision == monitor.revision,
        TrademarkCandidate.sequence > TrademarkCandidate.reviewed_sequence,
        TrademarkCandidateEvent.created_at > _utc(current.created_at),
        TrademarkCandidateEvent.created_at >= now - MAX_AGE, TrademarkCandidateEvent.created_at <= now, ~recorded)
        .order_by(TrademarkCandidateEvent.created_at, TrademarkCandidateEvent.id).limit(MAX_BATCH)))
    for candidate, event in rows:
        # Record non-source changes as suppressed, so they cannot starve later
        # source events in bounded scans. Nothing licensed is copied here.
        session.add(TrademarkDelivery(monitor_id=monitor.id, organization_id=monitor.organization_id,
            owner_user_id=monitor.owner_user_id, candidate_id=candidate.id, event_id=event.id,
            consent_revision=current.revision, signal_hash=signal(candidate, event),
            state="pending" if source_change(event) else "suppressed",
            due_at=next_delivery_at(config, now), created_at=now))
    session.flush()
    return len(rows)


def context(session, settings, monitor, revision, now):
    if not settings.trademark_watch_enabled:
        raise ValueError("IP email is unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(select(User).where(User.id == monitor.owner_user_id).with_for_update().execution_options(populate_existing=True))
    if (monitor.status != "active" or current is None or current.revision != revision
            or _utc(current.created_at) > now or user is None or user.email_verified_at is None or user.email != current.recipient_email):
        raise ValueError("IP email consent is no longer applicable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise ValueError("IP email is off")
    return config, user


def eligibility(session, monitor, intent, *, now):
    if (intent.consent_revision != monitor.email_revision or intent.owner_user_id != monitor.owner_user_id
            or intent.organization_id != monitor.organization_id or not now - MAX_AGE <= _utc(intent.created_at) <= now):
        return "suppressed", None
    candidate = session.scalar(select(TrademarkCandidate).where(
        TrademarkCandidate.id == intent.candidate_id, TrademarkCandidate.monitor_id == monitor.id,
        TrademarkCandidate.organization_id == monitor.organization_id).execution_options(populate_existing=True))
    event = session.get(TrademarkCandidateEvent, intent.event_id)
    current_policy = policy(session, monitor)
    if (candidate is None or event is None or current_policy is None
            or candidate.profile_revision != monitor.revision or event.candidate_id != candidate.id
            or event.organization_id != monitor.organization_id or event.profile_revision != monitor.revision
            or event.sequence != candidate.sequence or event.sequence <= candidate.reviewed_sequence
            or not source_change(event) or signal(candidate, event) != intent.signal_hash
            or not _utc(current_policy.created_at) < _utc(event.created_at) <= now
            or _utc(event.created_at) < now - MAX_AGE):
        return "suppressed", None
    try:
        # current() validates source generation, fresh head, matching/calibration
        # and the applicable deadline binding. Email carries no source facts.
        facts, assessment, _, _ = current_candidate(session, monitor, candidate, now=now, purpose="notification")
        require_permission(session, candidate.permission_id, now=now, purpose="display")
        if assessment["state"] == "unavailable":
            return "deferred", None
        if assessment["state"] != "candidate" and candidate.decision not in {"relevant", "monitor", "counsel"}:
            return "suppressed", None
        observed = read_revision(session, candidate.permission_id, event.source_revision_id, now=now, purpose="notification")
        if (observed.origin, observed.official_id) != (facts.origin, facts.official_id):
            return "suppressed", None
    except DomainError as error:
        return ("deferred" if error.code in TRANSIENT else "suppressed"), None
    duplicates = set(session.scalars(select(TrademarkDelivery.state).where(
        TrademarkDelivery.organization_id == monitor.organization_id, TrademarkDelivery.owner_user_id == monitor.owner_user_id,
        TrademarkDelivery.signal_hash == intent.signal_hash, TrademarkDelivery.id != intent.id,
        TrademarkDelivery.state.in_({"sending", "sent", "uncertain"}))))
    if duplicates & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicates:
        return "deferred", None
    return "eligible", {"href": f"/trademark-watch?monitor={monitor.id}&candidate={candidate.id}&event={event.id}",
                        "detected_at": _utc(event.created_at).isoformat()}


def pending(monitor, now):
    return (select(TrademarkDelivery).where(TrademarkDelivery.monitor_id == monitor.id,
        TrademarkDelivery.organization_id == monitor.organization_id, TrademarkDelivery.state == "pending",
        TrademarkDelivery.due_at <= now, TrademarkDelivery.consent_revision == monitor.email_revision)
        .order_by(TrademarkDelivery.due_at, TrademarkDelivery.id))


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    stamp = func.coalesce(TrademarkDelivery.sent_at, TrademarkDelivery.claimed_at)
    return session.scalar(select(TrademarkDelivery.id).where(TrademarkDelivery.monitor_id == monitor.id,
        TrademarkDelivery.organization_id == monitor.organization_id,
        TrademarkDelivery.state.in_({"sending", "sent", "uncertain"}), stamp >= start, stamp < end).limit(1)) is not None


def retry_at(config, now):
    immediate = config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})})
    return next_delivery_at(immediate, now + timedelta(seconds=60))


def preview(session, settings, user_id, monitor_id, *, now=None):
    from .trademark_repository import owned
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
        session.execute(update(TrademarkDelivery).where(TrademarkDelivery.state == "sending",
            TrademarkDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.execute(update(TrademarkDelivery).where(TrademarkDelivery.state == "pending",
            TrademarkDelivery.created_at < now - MAX_AGE).values(state="suppressed"))
        active = exists(select(jobs.Job.id).where(jobs.Job.type == "trademark_email", jobs.Job.target_type == "trademark_monitor",
            jobs.Job.target_id == TrademarkDelivery.monitor_id, jobs.Job.organization_id == TrademarkDelivery.organization_id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)))
        candidates = list(session.execute(select(TrademarkDelivery.monitor_id, TrademarkDelivery.organization_id).where(
            TrademarkDelivery.state == "pending", TrademarkDelivery.due_at <= now, ~active)
            .group_by(TrademarkDelivery.monitor_id, TrademarkDelivery.organization_id)
            .order_by(func.min(TrademarkDelivery.due_at), TrademarkDelivery.monitor_id).limit(100)))
        session.commit()
    if not settings.trademark_watch_enabled or settings.auth_email_mode != "smtp":
        return {"enqueued": 0}
    count = 0
    for identifier, organization in candidates:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == identifier).with_for_update())
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
                session.execute(update(TrademarkDelivery).where(TrademarkDelivery.monitor_id == identifier,
                    TrademarkDelivery.state == "pending", TrademarkDelivery.due_at <= now)
                    .values(due_at=next_delivery_at(config, now + timedelta(minutes=1))))
                session.commit()
                continue
            active_job = session.scalar(select(jobs.Job.id).where(jobs.Job.type == "trademark_email",
                jobs.Job.target_type == "trademark_monitor", jobs.Job.target_id == identifier,
                jobs.Job.state.not_in(jobs.TERMINAL_STATES), jobs.Job.cancel_requested.is_(False)).limit(1))
            if first is not None and active_job is None:
                _, reused = jobs.enqueue(session, job_type="trademark_email", target_type="trademark_monitor", target_id=identifier,
                    queue="maintenance", max_attempts=1, payload={"consent_revision": monitor.email_revision},
                    idempotency_key=f"trademark-email:{identifier}:{monitor.email_revision}:{int(now.timestamp()) // 60}")
                count += not reused
            session.commit()
    return {"enqueued": count}


MAIL_COPY = {
    "en": ("IP Watch: candidates and register updates", "Review your private candidates and register changes. A candidate is not a confirmed infringement.", "Open IP Watch", "Turn off email in portfolio settings to unsubscribe."),
    "de": ("IP Watch: Kandidaten und Registeränderungen", "Prüfen Sie Ihre privaten Kandidaten und Registeränderungen. Ein Kandidat ist keine bestätigte Rechtsverletzung.", "IP Watch öffnen", "Zum Abbestellen E-Mail in den Portfolioeinstellungen ausschalten."),
    "fr": ("IP Watch : candidats et changements du registre", "Consultez vos candidats privés et les changements du registre. Un candidat ne constitue pas une contrefaçon confirmée.", "Ouvrir IP Watch", "Désactivez les e-mails dans les réglages du portefeuille pour vous désabonner."),
    "it": ("IP Watch: candidati e modifiche del registro", "Esamina i candidati privati e le modifiche del registro. Un candidato non costituisce una violazione accertata.", "Apri IP Watch", "Disattiva le e-mail nelle impostazioni del portafoglio per annullare l’iscrizione."),
    "rm": ("IP Watch: candidats e midadas dal register", "Controllai Voss candidats privats e las midadas dal register. In candidat n’è betg ina violaziun confermada.", "Avrir IP Watch", "Deactivai ils e-mails en ils parameters dal portfolio per terminar l’abunament."),
}


def render(settings, user, monitor, items):
    title, intro, action, stop = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
    root = settings.public_base_url.rstrip("/")
    link = root + f"/trademark-watch?monitor={monitor.id}"
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
        monitor = session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == monitor_id).with_for_update())
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
        monitor = session.scalar(select(TrademarkMonitor).where(TrademarkMonitor.id == monitor_id).with_for_update())
        rows = list(session.scalars(select(TrademarkDelivery).where(TrademarkDelivery.id.in_(identifiers),
            TrademarkDelivery.monitor_id == monitor_id, TrademarkDelivery.state == "sending").with_for_update()))
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
                message_id=f"<trademark-{fingerprint(sorted(row.id for row in rows))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state, row.sent_at = ("sent", now) if mode == "smtp" else ("suppressed", None)
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
