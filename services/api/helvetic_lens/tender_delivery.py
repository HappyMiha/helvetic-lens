"""Private tender notifications from exact dossier versions and owner consent.

Claim before SMTP, recheck before sending, never automatically repeat a possibly
accepted message. Source content stays in the authenticated evidence reader.
"""

from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor
from .pollen_delivery import _quiet, next_delivery_at
from .simap_sources import aware
from .tender_email_preferences import EmailConfiguration, policy
from .tender_models import TenderDelivery, TenderDossier, TenderDossierVersion, TenderMonitor
from .tender_repository import digest, owned, source_readable

MAX_BATCH = 50
MAX_AGE = timedelta(days=2)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def record_intent(session, monitor, dossier, version, now):
    if version.kind not in {"new_opportunity", "material_update"}:
        return
    if version.kind == "material_update" and not dossier.following:
        return
    current = policy(session, monitor)
    if current is None:
        return
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off" or utc(current.created_at) > now:
        return
    user = session.get(User, monitor.owner_user_id)
    if user.email_verified_at is None or current.recipient_email != user.email:
        return
    session.add(
        TenderDelivery(
            organization_id=monitor.organization_id,
            monitor_id=monitor.id,
            owner_user_id=monitor.owner_user_id,
            evidence_version_id=version.id,
            consent_revision=current.revision,
            signal_hash=digest(
                {"project": dossier.project_id, "lot": dossier.lot_key, "source_hash": version.source_hash,
                 "document_event": version.observation_key or ""}
            ),
            due_at=next_delivery_at(config, now),
            created_at=now,
        )
    )


def context(session, settings, monitor, revision):
    if not settings.tender_watch_enabled or not settings.simap_public_source_enabled:
        raise DomainError("Tender source is unavailable.", 409, "tender_delivery_unavailable")
    _actor(session, monitor.owner_user_id, write=True)
    current = policy(session, monitor)
    user = session.scalar(
        select(User)
        .where(User.id == monitor.owner_user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        monitor.status != "active"
        or current is None
        or current.revision != revision
        or user.email_verified_at is None
        or user.email != current.recipient_email
    ):
        raise DomainError("Email consent is no longer applicable.", 409, "tender_delivery_unavailable")
    config = EmailConfiguration.model_validate(current.configuration)
    if config.delivery.email == "off":
        raise DomainError("Email is turned off.", 409, "tender_delivery_unavailable")
    return config, user


def eligibility(session, monitor, intent, now):
    """Shared by preview and delivery, including duplicates across private monitors."""
    if (
        intent.consent_revision != monitor.email_revision
        or intent.owner_user_id != monitor.owner_user_id
        or utc(intent.created_at) < now - MAX_AGE
    ):
        return "suppressed", None
    version = session.get(TenderDossierVersion, intent.evidence_version_id)
    dossier = session.get(TenderDossier, version.dossier_id) if version else None
    if (
        dossier is None
        or dossier.monitor_id != monitor.id
        or version.sequence != dossier.latest_sequence
        or version.profile_revision != monitor.revision
        or dossier.reviewed_sequence == version.sequence
    ):
        return "suppressed", None
    if version.kind == "new_opportunity":
        if version.match.get("verdict") not in {"match", "needs_review"}:
            return "suppressed", None
        deadline = version.summary.get("deadline") or {}
        if deadline.get("status") == "known" and aware(datetime.fromisoformat(deadline["utc"])) <= now:
            return "suppressed", None
    elif version.kind != "material_update" or not dossier.following:
        return "suppressed", None
    try:
        source_readable(version, now)
    except DomainError:
        return "suppressed", None
    duplicate_states = set(
        session.scalars(
            select(TenderDelivery.state).where(
                TenderDelivery.organization_id == monitor.organization_id,
                TenderDelivery.owner_user_id == monitor.owner_user_id,
                TenderDelivery.signal_hash == intent.signal_hash,
                TenderDelivery.id != intent.id,
                TenderDelivery.state.in_({"sending", "sent", "uncertain"}),
            )
        )
    )
    if duplicate_states & {"sent", "uncertain"}:
        return "suppressed", None
    if "sending" in duplicate_states:
        return "duplicate_wait", None
    return "eligible", {
        "dossier_id": dossier.id,
        "evidence_version_id": version.id,
        "sequence": version.sequence,
        "kind": version.kind,
        "href": f"/tender-watch?monitor={monitor.id}&dossier={dossier.id}&version={version.id}",
    }


def pending(session, monitor, now):
    # Superseded/expired rows are removed from consideration in SQL, so an old
    # outage cannot bury current records behind an unbounded scan.
    current = (
        select(TenderDossierVersion.id)
        .join(TenderDossier, TenderDossier.id == TenderDossierVersion.dossier_id)
        .where(
            TenderDossier.monitor_id == monitor.id,
            TenderDossier.latest_sequence == TenderDossierVersion.sequence,
            TenderDossierVersion.profile_revision == monitor.revision,
        )
    )
    return (
        select(TenderDelivery)
        .where(
            TenderDelivery.monitor_id == monitor.id,
            TenderDelivery.organization_id == monitor.organization_id,
            TenderDelivery.state == "pending",
            TenderDelivery.due_at <= now,
            TenderDelivery.consent_revision == monitor.email_revision,
            TenderDelivery.created_at >= now - MAX_AGE,
            TenderDelivery.evidence_version_id.in_(current),
        )
        .order_by(TenderDelivery.due_at, TenderDelivery.id)
    )


def daily_attempted(session, monitor, config, now):
    if config.delivery.email != "daily_digest":
        return False
    zone = ZoneInfo(config.timezone)
    day = now.astimezone(zone).date()
    beginning = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
    ending = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    stamp = func.coalesce(TenderDelivery.sent_at, TenderDelivery.claimed_at)
    return bool(
        session.scalar(
            select(TenderDelivery.id)
            .where(
                TenderDelivery.monitor_id == monitor.id,
                TenderDelivery.organization_id == monitor.organization_id,
                TenderDelivery.consent_revision == monitor.email_revision,
                TenderDelivery.state.in_({"sending", "sent", "uncertain"}),
                stamp >= beginning,
                stamp < ending,
            )
            .limit(1)
        )
    )


def prune(session, monitor, now):
    current = (
        select(TenderDossierVersion.id)
        .join(TenderDossier, TenderDossier.id == TenderDossierVersion.dossier_id)
        .where(
            TenderDossier.monitor_id == monitor.id,
            TenderDossier.latest_sequence == TenderDossierVersion.sequence,
            TenderDossierVersion.profile_revision == monitor.revision,
        )
    )
    session.execute(
        update(TenderDelivery)
        .where(
            TenderDelivery.monitor_id == monitor.id,
            TenderDelivery.organization_id == monitor.organization_id,
            TenderDelivery.state == "pending",
            (TenderDelivery.consent_revision != monitor.email_revision)
            | (TenderDelivery.created_at < now - MAX_AGE)
            | TenderDelivery.evidence_version_id.not_in(current),
        )
        .values(state="suppressed")
    )


def preview(session, settings, user_id, monitor_id, *, now=None):
    now = aware(now or datetime.now(UTC))
    monitor = owned(session, user_id, monitor_id)
    result = {
        "items": [],
        "more_available": False,
        "quiet_hours": False,
        "source_health": monitor.health,
        "status": "unavailable",
    }
    if getattr(settings, "auth_email_mode", "disabled") != "smtp":
        return result
    try:
        config, _ = context(session, settings, monitor, monitor.email_revision)
    except (DomainError, ValueError):
        return result
    rows = list(session.scalars(pending(session, monitor, now).limit(MAX_BATCH + 1)))
    for row in rows[:MAX_BATCH]:
        state, item = eligibility(session, monitor, row, now)
        if state == "eligible":
            result["items"].append(item)
    result.update(
        status="daily_already_attempted" if daily_attempted(session, monitor, config, now) else "ready",
        more_available=len(rows) > MAX_BATCH,
        quiet_hours=_quiet(config, now),
    )
    return result


def enqueue_due(database, settings, *, now=None):
    if not settings.tender_watch_enabled:
        return {"enqueued": 0}
    now = aware(now or datetime.now(UTC))
    with database.session(include_all_organizations=True) as session:
        session.execute(
            update(TenderDelivery)
            .where(TenderDelivery.state == "sending", TenderDelivery.claimed_at < now - timedelta(minutes=5))
            .values(state="uncertain")
        )
        session.execute(
            update(TenderDelivery)
            .where(TenderDelivery.state == "pending", TenderDelivery.created_at < now - MAX_AGE)
            .values(state="suppressed")
        )
        candidates = list(
            session.execute(
                select(TenderDelivery.monitor_id, TenderDelivery.organization_id)
                .where(TenderDelivery.state == "pending", TenderDelivery.due_at <= now)
                .distinct()
                .limit(100)
            )
        )
        session.commit()
    if getattr(settings, "auth_email_mode", "disabled") != "smtp":
        return {"enqueued": 0}
    count = 0
    for monitor_id, organization_id in candidates:
        with database.organization_context(organization_id), database.session() as session:
            monitor = session.scalar(
                select(TenderMonitor).where(TenderMonitor.id == monitor_id).with_for_update()
            )
            if monitor is None:
                continue
            try:
                config, _ = context(session, settings, monitor, monitor.email_revision)
            except (DomainError, ValueError):
                session.execute(
                    update(TenderDelivery)
                    .where(
                        TenderDelivery.monitor_id == monitor_id,
                        TenderDelivery.organization_id == organization_id,
                        TenderDelivery.state == "pending",
                    )
                    .values(state="suppressed")
                )
                session.commit()
                continue
            prune(session, monitor, now)
            if (
                daily_attempted(session, monitor, config, now)
                or session.scalar(pending(session, monitor, now).limit(1)) is None
            ):
                session.commit()
                continue
            # A pre-send suppression or quiet-hour deferral may be retried, but
            # a claimed/sent/uncertain daily message prevents another that day.
            bucket = str(int(now.timestamp()) // 60)
            _, reused = jobs.enqueue(
                session,
                job_type="tender_email",
                target_type="tender_monitor",
                target_id=monitor_id,
                queue="maintenance",
                max_attempts=1,
                payload={"consent_revision": monitor.email_revision},
                idempotency_key=f"tender-email:{monitor_id}:{monitor.email_revision}:{bucket}",
            )
            session.commit()
            count += not reused
    return {"enqueued": count}


MAIL_COPY = {
    "en": (
        "Tender Watch: review your changes",
        "New opportunity",
        "Material update",
        "Open Tender Watch",
        "Turn off email in the monitor to unsubscribe.",
        "Source coverage may be incomplete. Check the source status and exact publication before deciding.",
    ),
    "de": (
        "Tender Watch: Änderungen prüfen",
        "Neue Gelegenheit",
        "Wesentliche Änderung",
        "Tender Watch öffnen",
        "Zum Abbestellen E-Mail im Monitor ausschalten.",
        "Die Quellenabdeckung kann unvollständig sein. Prüfen Sie Quellenstatus und genaue Publikation vor einer Entscheidung.",
    ),
    "fr": (
        "Tender Watch : changements à examiner",
        "Nouvelle opportunité",
        "Modification importante",
        "Ouvrir Tender Watch",
        "Désactivez les e-mails dans le suivi pour vous désabonner.",
        "La couverture de la source peut être incomplète. Vérifiez son état et la publication exacte avant de décider.",
    ),
    "it": (
        "Tender Watch: cambiamenti da esaminare",
        "Nuova opportunità",
        "Modifica sostanziale",
        "Apri Tender Watch",
        "Disattiva le e-mail nel monitoraggio per annullare l’iscrizione.",
        "La copertura della fonte può essere incompleta. Controlla lo stato e la pubblicazione esatta prima di decidere.",
    ),
    "rm": (
        "Tender Watch: midadas da controllar",
        "Nova occasiun",
        "Midada impurtanta",
        "Avrir Tender Watch",
        "Deactivai ils e-mails en il monitoring per terminar l’abunament.",
        "La cuvrida da la funtauna po esser incumpletta. Controllai il stadi e la publicaziun exacta avant ina decisiun.",
    ),
}


def render(settings, user, monitor, items):
    title, opportunity, changed, action, stop, caveat = MAIL_COPY.get(
        (user.locale or "en").split("-")[0], MAIL_COPY["en"]
    )
    root = settings.public_base_url.rstrip("/")
    link = root + f"/tender-watch?monitor={monitor.id}"
    lines = [monitor.configuration["name"]]
    links = []
    for item in items:
        label = opportunity if item["kind"] == "new_opportunity" else changed
        lines.append(f"{label}: {root}{item['href']}")
        links.append(f'<li><a href="{escape(root + item["href"], quote=True)}">{escape(label)}</a></li>')
    body = "\n\n".join([*lines, caveat, f"{action}: {link}", stop])
    html = (
        f"<p>{escape(monitor.configuration['name'])}</p><ul>{''.join(links)}</ul>"
        + f'<p>{escape(caveat)}</p><p><a href="{escape(link, quote=True)}">{escape(action)}</a></p><p>{escape(stop)}</p>'
    )
    return title, body, html


def deliver(
    database,
    settings,
    *,
    monitor_id,
    consent_revision,
    now=None,
    mailer=None,
    before_send=None,
    checkpoint=lambda: True,
):
    fixed = now is not None
    now = aware(now or datetime.now(UTC))
    if not checkpoint():
        return {"status": "cancelled"}
    if mailer is None and getattr(settings, "auth_email_mode", "disabled") != "smtp":
        return {"status": "mail_not_live"}
    ids = []
    with database.session() as session:
        monitor = session.scalar(
            select(TenderMonitor).where(TenderMonitor.id == monitor_id).with_for_update()
        )
        if monitor is None:
            return {"status": "inactive"}
        try:
            config, _ = context(session, settings, monitor, consent_revision)
        except (DomainError, ValueError):
            return {"status": "unavailable"}
        if daily_attempted(session, monitor, config, now):
            return {"status": "daily_already_attempted"}
        prune(session, monitor, now)
        rows = list(session.scalars(pending(session, monitor, now).limit(MAX_BATCH)))
        for row in rows:
            state, _ = eligibility(session, monitor, row, now)
            if state == "suppressed":
                row.state = "suppressed"
            elif state == "duplicate_wait":
                row.due_at = now + timedelta(minutes=5)
            elif _quiet(config, now):
                immediate = config.model_copy(
                    update={
                        "delivery": config.delivery.model_copy(
                            update={"email": "immediate", "digest_at": None}
                        )
                    }
                )
                row.due_at = next_delivery_at(immediate, now)
            else:
                row.state, row.claimed_at = "sending", now
                ids.append(row.id)
        session.commit()
    if not ids:
        return {"status": "no_eligible_changes"}
    if before_send is not None:
        before_send()  # Test/fault-injection boundary; never an HTTP parameter.
    permitted_job = checkpoint()
    with database.session() as session:
        monitor = session.scalar(
            select(TenderMonitor).where(TenderMonitor.id == monitor_id).with_for_update()
        )
        rows = list(
            session.scalars(
                select(TenderDelivery)
                .where(
                    TenderDelivery.id.in_(ids),
                    TenderDelivery.monitor_id == monitor_id,
                    TenderDelivery.state == "sending",
                )
                .with_for_update()
            )
        )
        now = now if fixed else datetime.now(UTC)
        try:
            if not permitted_job or monitor is None or len(rows) != len(ids):
                raise ValueError("Claim no longer exists")
            config, user = context(session, settings, monitor, consent_revision)
            items, selected_rows = [], []
            for row in rows:
                state, item = eligibility(session, monitor, row, now)
                if state == "eligible":
                    items.append(item)
                    selected_rows.append(row)
                elif state == "duplicate_wait":
                    row.state, row.claimed_at = "pending", None
                    row.due_at = now + timedelta(minutes=5)
                else:
                    row.state = "suppressed"
            rows = selected_rows
            if not rows:
                session.commit()
                return {"status": "suppressed"}
            if _quiet(config, now):
                immediate = config.model_copy(
                    update={
                        "delivery": config.delivery.model_copy(
                            update={"email": "immediate", "digest_at": None}
                        )
                    }
                )
                for row in rows:
                    row.state, row.claimed_at = "pending", None
                    row.due_at = next_delivery_at(immediate, now)
                session.commit()
                return {"status": "quiet_hours"}
        except (DomainError, ValueError):
            for row in rows:
                row.state = "suppressed"
            session.commit()
            return {"status": "suppressed"}
        title, body, html = render(settings, user, monitor, items)
        try:
            mode = (mailer or AuthMailer(settings)).send_message(
                user.email,
                title,
                body,
                html,
                user.locale,
                message_id=f"<tender-{digest(sorted(row.id for row in rows))}@helvetic-lens.local>",
            )
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
