"""Consent-aware private pollen email using the existing durable job and mailer.

SMTP has no transactional exactly-once guarantee. A possibly accepted send is
recorded as uncertain and is never automatically retried as a fresh message.
"""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .models import MonitoringSubject, User
from .monitoring_live_models import (
    MonitoringDelivery,
    MonitoringLiveEntry,
    MonitoringLiveStream,
    MonitoringReview,
    MonitoringRuntime,
)
from .monitoring_runtime import _configuration, _gate, _locked_subject, _require_live
from .pollen_thresholds import PollenSample, _hash


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _quiet(config, moment):
    interval = config.delivery.quiet_hours
    if interval is None:
        return False
    clock = moment.astimezone(ZoneInfo(config.timezone)).strftime("%H:%M")
    return interval.start <= clock < interval.end if interval.start < interval.end else clock >= interval.start or clock < interval.end


def next_delivery_at(config, now):
    """First actual UTC instant; DST gaps advance, repeated digest clocks send once."""
    if now.tzinfo is None:
        raise ValueError("Delivery scheduling requires an aware clock")
    now = now.astimezone(UTC)
    zone = ZoneInfo(config.timezone)
    candidate = now
    if config.delivery.email == "daily_digest":
        local_day = now.astimezone(zone).date()
        for offset in range(3):
            day = local_day + timedelta(days=offset)
            midnight = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
            scheduled = None
            for minutes in range(26 * 60):
                instant = midnight + timedelta(minutes=minutes)
                local = instant.astimezone(zone)
                if local.date() == day and local.strftime("%H:%M") >= config.delivery.digest_at:
                    scheduled = instant
                    break
            if scheduled is not None and scheduled >= now:
                candidate = scheduled
                break
        else:
            raise ValueError("Digest schedule has no bounded delivery instant")
    if _quiet(config, candidate):
        candidate = candidate.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(27 * 60):
            if not _quiet(config, candidate):
                break
            candidate += timedelta(minutes=1)
        else:
            raise ValueError("Quiet hours have no bounded delivery instant")
    return candidate


def enqueue_due(database, settings, *, now=None):
    if settings.deployment_instance != "monitoring-v2" or not settings.monitoring_rollout.enabled:
        return {"enqueued": 0}
    now = now or datetime.now(UTC)
    with database.session(include_all_organizations=True) as session:
        session.execute(update(MonitoringDelivery).where(MonitoringDelivery.state == "sending",
            MonitoringDelivery.claimed_at < now - timedelta(minutes=5)).values(state="uncertain"))
        session.commit()
        rows = list(session.execute(select(MonitoringLiveStream.subject_id, MonitoringDelivery.organization_id, MonitoringDelivery.consent_version)
            .select_from(MonitoringDelivery)
            .join(MonitoringLiveEntry, MonitoringLiveEntry.id == MonitoringDelivery.entry_id)
            .join(MonitoringLiveStream, MonitoringLiveStream.id == MonitoringLiveEntry.stream_id)
            .where(MonitoringDelivery.state == "pending", MonitoringDelivery.due_at <= now)
            .distinct().limit(100)))
    count = 0
    for subject_id, organization_id, consent_version in rows:
        with database.organization_context(organization_id), database.session() as session:
            subject = session.get(MonitoringSubject, subject_id)
            runtime = session.get(MonitoringRuntime, subject_id)
            if subject is None or runtime is None:
                continue
            entries = select(MonitoringLiveEntry.id).join(MonitoringLiveStream,
                MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(MonitoringLiveStream.subject_id == subject_id)
            try:
                subject = _locked_subject(session, subject.owner_user_id, subject_id)
                _require_live(settings, organization_id)
                _gate(settings, _configuration(session, subject), now)
                permitted = subject.status == "active" and runtime.email_consent and not runtime.muted and runtime.version == consent_version
            except DomainError:
                permitted = False
            if not permitted:
                session.execute(update(MonitoringDelivery).where(MonitoringDelivery.entry_id.in_(entries),
                    MonitoringDelivery.consent_version == consent_version, MonitoringDelivery.state == "pending").values(state="suppressed"))
                session.commit()
                continue
            config = _configuration(session, subject)
            bucket = now.astimezone(ZoneInfo(config.timezone)).date().isoformat() if config.delivery.email == "daily_digest" else str(int(now.timestamp()) // 60)
            _, reused = jobs.enqueue(session, job_type="pollen_email", target_type="monitoring_subject", target_id=subject_id,
                queue="maintenance", idempotency_key=f"pollen-email:{subject_id}:{consent_version}:{bucket}",
                payload={"consent_version": consent_version}, max_attempts=1)
            session.commit()
            count += not reused
    return {"enqueued": count}


def _eligible(session, settings, subject, runtime, row, now):
    _require_live(settings, subject.organization_id)
    config = _configuration(session, subject)
    _gate(settings, config, now)
    if (subject.status != "active" or runtime.muted or not runtime.email_consent
            or config.delivery.email == "off" or runtime.version != row.consent_version
            or subject.current_revision != row.configuration_revision):
        return False
    # The owner row is locked by the caller across subjects. A possibly accepted
    # email is never repeated through another monitor with the identical rule and
    # public material transition. Separate users retain separate notification scope.
    already_delivered = session.scalar(select(MonitoringDelivery.id).where(
        MonitoringDelivery.organization_id == subject.organization_id,
        MonitoringDelivery.owner_user_id == subject.owner_user_id, MonitoringDelivery.signal_hash == row.signal_hash,
        MonitoringDelivery.id != row.id, MonitoringDelivery.state.in_({"sending", "sent", "uncertain"})).limit(1))
    if already_delivered:
        return False
    entry = session.get(MonitoringLiveEntry, row.entry_id)
    stream = session.get(MonitoringLiveStream, entry.stream_id)
    if stream.run_id != runtime.run_id or stream.id not in runtime.current_stream_ids or not stream.state_json.get("available"):
        return False
    current = PollenSample.model_validate(stream.state_json["sample"])
    if now >= current.fresh_until or settings.pollen_source_policy.approval(current.series, now) is None:
        return False
    latest = session.scalar(select(MonitoringLiveEntry.id).where(MonitoringLiveEntry.stream_id == stream.id,
        MonitoringLiveEntry.material_id.is_not(None)).order_by(MonitoringLiveEntry.sequence.desc()).limit(1))
    if latest != entry.id:
        return False  # Delayed delivery describes only the current material revision.
    review = session.scalar(select(MonitoringReview).where(MonitoringReview.entry_id == entry.id)
        .order_by(MonitoringReview.version.desc()).limit(1))
    return not review or review.decision in {"continue", "action_required"}


MAIL_COPY = {
    "en": ("Pollen Watch: changes to review", "New pollen changes are ready to review in your private monitor.", "Open monitoring", "To stop these emails, open the monitor and choose Turn off email."),
    "de": ("Pollen Watch: Änderungen prüfen", "Neue Pollenänderungen sind in Ihrem privaten Monitor zur Prüfung bereit.", "Monitoring öffnen", "Um diese E-Mails zu beenden, öffnen Sie den Monitor und wählen Sie E-Mail ausschalten."),
    "fr": ("Pollen Watch : changements à examiner", "De nouveaux changements sont à examiner dans votre suivi privé du pollen.", "Ouvrir le suivi", "Pour arrêter ces e-mails, ouvrez le suivi et choisissez Désactiver les e-mails."),
    "it": ("Pollen Watch: cambiamenti da esaminare", "Nuovi cambiamenti dei pollini sono disponibili nel monitoraggio privato.", "Apri monitoraggio", "Per interrompere queste e-mail, apri il monitoraggio e scegli Disattiva e-mail."),
    "rm": ("Pollen Watch: midadas da controllar", "Novas midadas dal pollen èn prontas per la controlla en tes monitoring privat.", "Avrir il monitoring", "Per terminar quests e-mails, avra il monitoring e tscherna Deactivar e-mails."),
}


def deliver(database, settings, *, subject_id, consent_version, now=None, mailer=None):
    fixed_clock = now is not None
    now = now or datetime.now(UTC)
    # Claim a bounded group durably before touching SMTP. A process crash after
    # this commit leaves 'sending' rows for explicit uncertain-delivery handling.
    with database.session() as session:
        subject = session.get(MonitoringSubject, subject_id)
        if subject is None:
            return {"status": "inactive"}
        try:
            subject = _locked_subject(session, subject.owner_user_id, subject_id)
        except DomainError:
            return {"status": "access_unavailable"}
        runtime = session.get(MonitoringRuntime, subject_id)
        if runtime is None:
            return {"status": "inactive"}
        # Discard superseded intents in SQL before the bounded send group, so a
        # long outage cannot bury current changes behind thousands of old rows.
        latest = select(MonitoringLiveEntry.stream_id, func.max(MonitoringLiveEntry.sequence).label("sequence")).where(
            MonitoringLiveEntry.stream_id.in_(runtime.current_stream_ids), MonitoringLiveEntry.material_id.is_not(None)
        ).group_by(MonitoringLiveEntry.stream_id).subquery()
        current_entries = select(MonitoringLiveEntry.id).join(latest,
            (latest.c.stream_id == MonitoringLiveEntry.stream_id) & (latest.c.sequence == MonitoringLiveEntry.sequence))
        subject_entries = select(MonitoringLiveEntry.id).join(MonitoringLiveStream,
            MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(MonitoringLiveStream.subject_id == subject_id)
        session.execute(update(MonitoringDelivery).where(MonitoringDelivery.entry_id.in_(subject_entries),
            MonitoringDelivery.entry_id.not_in(current_entries), MonitoringDelivery.consent_version == consent_version,
            MonitoringDelivery.state == "pending").values(state="suppressed"))
        rows = list(session.scalars(select(MonitoringDelivery).join(MonitoringLiveEntry,
            MonitoringLiveEntry.id == MonitoringDelivery.entry_id).join(MonitoringLiveStream,
            MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(
            MonitoringLiveStream.subject_id == subject_id, MonitoringDelivery.state == "pending",
            MonitoringDelivery.consent_version == consent_version,
            MonitoringDelivery.due_at <= now).order_by(MonitoringDelivery.due_at, MonitoringDelivery.id).limit(50)))
        ids = []
        config = _configuration(session, subject)
        for row in rows:
            try:
                eligible = _eligible(session, settings, subject, runtime, row, now)
            except DomainError:
                eligible = False
            if not eligible or consent_version != runtime.version:
                row.state = "suppressed"
            elif _quiet(config, now):
                row.due_at = next_delivery_at(config.model_copy(update={"delivery": config.delivery.model_copy(update={"email": "immediate", "digest_at": None})}), now)
            else:
                row.state = "sending"
                row.claimed_at = now
                ids.append(row.id)
        session.commit()
    if not ids:
        return {"status": "no_eligible_changes"}
    with database.session() as session:
        subject = session.get(MonitoringSubject, subject_id)
        if subject is None:
            return {"status": "inactive"}
        rows = []
        try:
            subject = _locked_subject(session, subject.owner_user_id, subject_id)
            rows = list(session.scalars(select(MonitoringDelivery).where(MonitoringDelivery.id.in_(ids)).with_for_update()))
            now = now if fixed_clock else datetime.now(UTC)
            runtime = session.get(MonitoringRuntime, subject_id)
            user = session.scalar(select(User).where(User.id == subject.owner_user_id).with_for_update())
            if user.email_verified_at is None or any(not _eligible(session, settings, subject, runtime, row, now) for row in rows):
                raise DomainError("Delivery is no longer permitted.", 409, "pollen_delivery_suppressed")
        except DomainError:
            if not rows:
                rows = list(session.scalars(select(MonitoringDelivery).where(MonitoringDelivery.id.in_(ids))))
            for row in rows:
                row.state = "suppressed"
            session.commit()
            return {"status": "suppressed"}
        config = _configuration(session, subject)
        if _quiet(config, now):
            for row in rows:
                row.state, row.claimed_at = "pending", None
                row.due_at = next_delivery_at(config.model_copy(update={"delivery": config.delivery.model_copy(
                    update={"email": "immediate", "digest_at": None})}), now)
            session.commit()
            return {"status": "quiet_hours"}
        selected = MAIL_COPY.get((user.locale or "en").split("-")[0], MAIL_COPY["en"])
        subject_line, explanation, action, unsubscribe = selected
        link = settings.public_base_url.rstrip("/") + f"/pollen-watch#draft={subject_id}"
        body = f"{explanation}\n\n{action}: {link}\n\n{unsubscribe}"
        html = f'<p>{escape(explanation)}</p><p><a href="{escape(link, quote=True)}">{escape(action)}</a></p><p>{escape(unsubscribe)}</p>'
        try:
            mode = (mailer or AuthMailer(settings)).send_message(user.email, subject_line, body, html, user.locale,
                message_id=f"<pollen-{_hash(sorted(ids))}@helvetic-lens.local>")
        except Exception:
            for row in rows:
                row.state = "uncertain"
            session.commit()
            return {"status": "uncertain"}
        for row in rows:
            row.state = "sent" if mode == "smtp" else "suppressed"
            row.sent_at = now if mode == "smtp" else None
        session.commit()
        return {"status": "sent" if mode == "smtp" else "mail_not_live", "changes": len(rows)}
