"""Opt-in personal dossier email through native jobs, with current-access fences."""
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import select

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .models import User
from .product_access import require
from .product_models import PrivateDossierFollow, ProductDossier
from .product_operations import fingerprint
from .product_research_updates import completed, update_payload

MAIL_JOB = "dossier_update_email"


def aware(value):
    return (datetime.fromisoformat(value) if isinstance(value, str) else value).replace(tzinfo=UTC)


def next_delivery(mode, now):
    return now + timedelta(days=7 if mode == "weekly" else 1 if mode == "daily" else 0, minutes=1 if mode == "immediate" else 0)


def recipient(session, follow):
    parent = session.get(ProductDossier, follow.dossier_id)
    user = session.get(User, follow.owner_user_id)
    if not parent or not user or not user.active or not user.email_verified_at:
        raise DomainError("Recipient access is unavailable.", 403)
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    require(session, parent, profile, user.id, "read")
    return parent, profile, user


def candidates(session, follow, after, cutoff):
    from .product_investigation_models import Investigation

    rows = completed(follow.dossier_id).subquery()
    records = session.execute(select(Investigation, rows.c.finished_at).join(rows, rows.c.id == Investigation.id)
        .where(rows.c.finished_at > aware(after), rows.c.finished_at <= aware(cutoff))
        .order_by(rows.c.finished_at, rows.c.id))
    updates = [update_payload(session, run, finished, follow, None) for run, finished in records]
    return [u for u in updates if u["materiality"]["category"] != "quiet"]


def enqueue_due(database, settings, *, now=None):
    now = now or utcnow()
    queued = 0
    with database.session(include_all_organizations=True) as session:
        query = select(PrivateDossierFollow).where(PrivateDossierFollow.following.is_(True),
            PrivateDossierFollow.email_settings["mode"].as_string().in_(("immediate", "daily", "weekly")),
            PrivateDossierFollow.email_settings["next_delivery_at"].as_string() <= now.isoformat())
        due = list(session.scalars(query.order_by(PrivateDossierFollow.email_settings["next_delivery_at"].as_string(), PrivateDossierFollow.id).limit(50)))
        identifiers = [follow.id for follow in due]
    for identifier in identifiers:
        with database.session(include_all_organizations=True) as session:
            follow = locked_follow(session, identifier)
            if (not follow or not follow.following or follow.email_settings.get("mode", "off") == "off"
                    or aware(follow.email_settings["next_delivery_at"]) > now):
                continue
            value = dict(follow.email_settings)
            value["next_delivery_at"] = next_delivery(value["mode"], now).isoformat()
            if value.get("pending"):
                follow.email_settings = value
                session.commit()
                continue
            try:
                recipient(session, follow)
            except DomainError:
                value["state"] = "access_unavailable"
                follow.email_settings = value
                session.commit()
                continue
            if settings.auth_email_mode != "smtp":
                value["state"] = "email_unavailable"
                follow.email_settings = value
                session.commit()
                continue
            cutoff = now.isoformat()
            updates = candidates(session, follow, value["after"], cutoff)
            if updates:
                key = fingerprint({"follow": follow.id, "version": value["version"], "after": value["after"], "cutoff": cutoff})
                value.update(pending=key, state="queued")
                jobs.enqueue(session, job_type=MAIL_JOB, target_type="dossier_follow", target_id=follow.id,
                    organization_id=follow.organization_id, queue="maintenance", idempotency_key=MAIL_JOB + ":" + key,
                    payload={"version": value["version"], "key": key, "after": value["after"], "cutoff": cutoff})
                queued += 1
            else:
                value.update(after=cutoff, state="no_new_updates")
            follow.email_settings = value
            session.commit()
    return {"queued": queued}


def deliver(database, settings, identifier, payload, *, mailer=None):
    with database.session() as session:
        follow = locked_follow(session, identifier)
        value = dict(follow.email_settings) if follow else {}
        if (not follow or not follow.following or value.get("mode", "off") == "off"
                or value.get("version") != payload.get("version") or value.get("pending") != payload.get("key")):
            return {"state": "cancelled_or_already_handled"}
        if value.get("attempted") == payload["key"]:
            # An interrupted SMTP attempt is uncertain, not permission to resend.
            value["state"] = "delivery_uncertain"
            follow.email_settings = value
            session.commit()
            return {"state": "delivery_uncertain"}
        try:
            parent, profile, user = recipient(session, follow)
        except DomainError:
            value.update(state="access_unavailable", pending=None)
            follow.email_settings = value
            session.commit()
            return {"state": "access_unavailable"}
        updates = candidates(session, follow, payload["after"], payload["cutoff"])
        if not updates:
            value.update(state="no_current_updates", pending=None, after=payload["cutoff"])
            follow.email_settings = value
            session.commit()
            return {"state": "no_current_updates"}
        value.update(attempted=payload["key"], state="sending")
        follow.email_settings = value
        session.commit()
        # Recheck consent and access immediately before the external write.
        follow = locked_follow(session, identifier)
        if not follow or follow.email_settings.get("version") != payload["version"] or not follow.following:
            return {"state": "cancelled"}
        try:
            parent, profile, user = recipient(session, follow)
            # Evidence may have been withdrawn between enqueue and delivery.
            updates = candidates(session, follow, payload["after"], payload["cutoff"])
            if not updates:
                value.update(state="no_current_updates", pending=None, after=payload["cutoff"])
                follow.email_settings = value
                session.commit()
                return {"state": "no_current_updates"}
            product = "legal" if parent.product in {"legal", "loyer"} else "pharma"
            url = f"https://{product}.helveticlens.ch/?dossier={parent.id}"
            title = profile.config_json.get("name", "Your dossier")
            lines = [title, f"{len(updates)} research update(s) are available.", ""]
            for update in updates[-5:]:
                lines.append(update["question"])
                lines.extend(update["materiality"]["reasons"][:3])
            lines.extend(["", "Open the current evidence, contradictions and gaps:", url,
                "Manage or turn off these dossier emails under Monitoring in the dossier."])
            body = "\n".join(lines)
            mode = (mailer or AuthMailer(settings)).send_message(user.email, "Helvetic Lens — dossier updates", body,
                "<html><body><p>" + escape(body).replace("\n", "<br>") + "</p></body></html>",
                message_id=f"<dossier-update-{payload['key']}@helveticlens.ch>")
        except Exception:
            value["state"] = "delivery_uncertain"
        else:
            value.update(state="sent" if mode == "smtp" else "email_unavailable", pending=None)
            if mode == "smtp":
                value.update(after=payload["cutoff"], last_sent_at=utcnow().isoformat())
        session.refresh(follow)
        if follow.email_settings.get("version") == payload["version"]:
            follow.email_settings = value
            session.commit()
        return {"state": value["state"]}


def locked_follow(session, identifier):
    follow = session.get(PrivateDossierFollow, identifier)
    if not follow:
        return None
    lock_organization(session, follow.organization_id)
    session.get(User, follow.owner_user_id, populate_existing=True, with_for_update=True)
    return session.scalar(select(PrivateDossierFollow).where(PrivateDossierFollow.id == identifier)
        .with_for_update().execution_options(populate_existing=True))
