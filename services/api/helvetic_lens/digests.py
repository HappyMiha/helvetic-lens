"""Opt-in digests built only from the persisted organization impact inbox."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError, Settings
from .db import Database, utcnow
from .impact_inbox import ImpactInboxFilters, ImpactInboxReader
from .locales import normalize_locale
from .models import DigestDelivery, DigestPreference, Job, OrganizationMembership, User

SEVERITIES = {"high", "medium", "low", "none", "unknown"}
FREQUENCIES = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}

_MESSAGES = {
    "de-CH": {
        "event_limit": "Diese Zusammenfassung ist auf 50 Ereignisse begrenzt. Öffnen Sie das Auswirkungs-Postfach für die vollständige gespeicherte Liste oder grenzen Sie die Quellen und Schweregrade ein.",
        "more_laws": "{shown} von {total} passenden überwachten Gesetzen werden angezeigt.",
        "subject": "Helvetic Lens: {count} Änderungen zur Prüfung",
        "heading": "Ihr regulatorischer Überblick",
        "empty": "Für diesen Zeitraum gibt es keine passenden neuen Hinweise.",
        "open": "Impact-Inbox öffnen",
        "unsubscribe": "E-Mail-Digest abbestellen",
        "evidence": "Beleg öffnen",
        "severity": {"high": "hoch", "medium": "mittel", "low": "niedrig", "none": "keine", "unknown": "unklar"},
    },
    "fr-CH": {
        "event_limit": "Cette synthèse est limitée à 50 événements. Ouvrez la boîte des impacts pour consulter la liste enregistrée complète, ou affinez les sources et les niveaux de gravité.",
        "more_laws": "{shown} lois surveillées correspondantes affichées sur {total}.",
        "subject": "Helvetic Lens : {count} changements à examiner",
        "heading": "Votre synthèse réglementaire",
        "empty": "Aucun nouvel élément correspondant pour cette période.",
        "open": "Ouvrir la boîte d’impact",
        "unsubscribe": "Se désabonner du résumé e-mail",
        "evidence": "Ouvrir la preuve",
        "severity": {"high": "élevée", "medium": "moyenne", "low": "faible", "none": "aucune", "unknown": "incertaine"},
    },
    "it-CH": {
        "event_limit": "Questo riepilogo è limitato a 50 eventi. Apri la posta degli impatti per l’elenco completo salvato, oppure restringi le fonti e i livelli di gravità.",
        "more_laws": "{shown} leggi monitorate corrispondenti mostrate su {total}.",
        "subject": "Helvetic Lens: {count} modifiche da esaminare",
        "heading": "Il tuo riepilogo normativo",
        "empty": "Nessun nuovo elemento corrispondente per questo periodo.",
        "open": "Apri la casella impatti",
        "unsubscribe": "Annulla il riepilogo e-mail",
        "evidence": "Apri la prova",
        "severity": {"high": "alta", "medium": "media", "low": "bassa", "none": "nessuna", "unknown": "incerta"},
    },
    "rm-CH": {
        "event_limit": "Questa resumaziun è limitada a 50 eveniments. Avra la posta dals effects per la glista cumpletta memorisada u restrenscha las funtaunas e las gradaziuns da gravitad.",
        "more_laws": "{shown} da {total} leschas survegliadas correspundentas vegnan mussadas.",
        "subject": "Helvetic Lens: {count} midadas da controllar",
        "heading": "Tia survista regulativa",
        "empty": "I na dat nagins novs avis adattads per questa perioda.",
        "open": "Avrir la posta d’impacts",
        "unsubscribe": "Deabunar il resumaziun per e-mail",
        "evidence": "Avrir la cumprova",
        "severity": {"high": "auta", "medium": "mesauna", "low": "bassa", "none": "nagina", "unknown": "intschertezza"},
    },
    "en-CH": {
        "event_limit": "This digest is limited to 50 events. Open the impact inbox for the full saved list, or narrow your source and severity filters.",
        "more_laws": "Showing {shown} of {total} matching watched laws.",
        "subject": "Helvetic Lens: {count} changes to review",
        "heading": "Your regulatory digest",
        "empty": "There are no matching new items for this period.",
        "open": "Open impact inbox",
        "unsubscribe": "Unsubscribe from email digests",
        "evidence": "Open evidence",
        "severity": {"high": "high", "medium": "medium", "low": "low", "none": "none", "unknown": "unclear"},
    },
}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def next_delivery(now: datetime, frequency: str) -> datetime:
    return _aware(now) + FREQUENCIES[frequency]


def _application_url(settings: Settings, value: str | None) -> str | None:
    """Turn an internal application path into a public URL without forwarding arbitrary links."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return settings.public_base_url.rstrip("/") + value


def preference_token(settings: Settings, preference_id: str) -> str:
    key = settings.credential_encryption_key.get_secret_value()
    if not key:
        key = "helvetic-lens-development-digest-key"
    signature = hmac.new(key.encode(), preference_id.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{preference_id}.{encoded}"


def preference_id_from_token(settings: Settings, token: str) -> str:
    preference_id, separator, _signature = token.partition(".")
    if not separator or not hmac.compare_digest(preference_token(settings, preference_id), token):
        raise DomainError("This unsubscribe link is invalid.", 422, "digest_token_invalid")
    return preference_id


def serialize_preference(preference: DigestPreference | None) -> dict:
    if not preference:
        return {
            "enabled": False,
            "frequency": "weekly",
            "severities": [],
            "sources": [],
            "next_delivery_at": None,
            "last_sent_at": None,
        }
    return {
        "id": preference.id,
        "enabled": preference.enabled,
        "frequency": preference.frequency,
        "severities": preference.severities or [],
        "sources": preference.sources or [],
        "next_delivery_at": _iso(preference.next_delivery_at),
        "last_sent_at": _iso(preference.last_sent_at),
    }


def serialize_delivery(delivery: DigestDelivery) -> dict:
    return {
        "id": delivery.id,
        "frequency": delivery.frequency,
        "period_start": _iso(delivery.period_start),
        "period_end": _iso(delivery.period_end),
        "status": delivery.status,
        "item_count": delivery.item_count,
        "summary": delivery.summary or {},
        "error": delivery.error,
        "sent_at": _iso(delivery.sent_at),
        "created_at": _iso(delivery.created_at),
    }


def inbox_filters(preference: DigestPreference, period_start: datetime, period_end: datetime) -> ImpactInboxFilters:
    return ImpactInboxFilters(
        detected_from=_aware(period_start), detected_before=_aware(period_end),
        sources=tuple(preference.sources or []), excluded_states=("dismissed", "muted"),
    )


def preview_page(session: Session, reader: ImpactInboxReader, preference: DigestPreference, *, cursor: str = "") -> dict:
    """Inspect at most 50 event keys, even when no severity matches this page.

    Cursors pin a period/admission ceiling and bind the actual reader/preferences.
    They are navigation positions, not authorization or immutable result snapshots.
    """
    scope = hashlib.sha256(json.dumps([
        reader.organization_id, reader.principal, _preference_fingerprint(preference),
    ]).encode()).hexdigest()
    end, after = utcnow(), None
    if cursor:
        try:
            if len(cursor) > 2048:
                raise ValueError("oversized")
            data = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
            if not isinstance(data, dict) or data.get("version") != 1 or data.get("scope") != scope:
                raise ValueError("scope")
            end = datetime.fromisoformat(data["period_end"])
            if end.tzinfo is None:
                raise ValueError("timezone")
            end - FREQUENCIES[preference.frequency]  # Reject dates that cannot form a complete period.
            after = data["after"]
            if after is not None:
                if not isinstance(after, dict) or not isinstance(after.get("id"), str) or not 1 <= len(after["id"]) <= 36:
                    raise ValueError("position")
                stamp = datetime.fromisoformat(after["detected_at"])
                if stamp.tzinfo is None or not end - FREQUENCIES[preference.frequency] <= stamp < end:
                    raise ValueError("period")
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise DomainError("This digest preview has expired or its settings changed. Restart the preview.",
                              422, "invalid_digest_cursor") from error
    start = end - FREQUENCIES[preference.frequency]
    def token(position):
        return base64.urlsafe_b64encode(json.dumps({
            "version": 1, "scope": scope, "period_end": _iso(end), "after": position,
        }, separators=(",", ":")).encode()).decode().rstrip("=")
    page = reader.event_page(session, replace(inbox_filters(preference, start, end), admitted_before=end), cursor=after)
    return {
        **filtered_summary(page, preference, start, end),
        "counts_scope": "page", "scanned_event_count": page["scanned"],
        "period_start": _iso(start), "period_end": _iso(end),
        "has_more": page["has_more"], "current_cursor": token(after),
        "next_cursor": token(page["cursor"]) if page["has_more"] else None,
    }


def filtered_summary(page: dict, preference: DigestPreference, period_start: datetime, period_end: datetime) -> dict:
    return summarize_groups(page.get("items", []), preference, period_start, period_end)


def summarize_groups(groups: Iterable[dict], preference: DigestPreference, period_start: datetime, period_end: datetime) -> dict:
    selected = []
    truncated = False
    severities = set(preference.severities or [])
    sources = set(preference.sources or [])
    for group in groups:
        detected = datetime.fromisoformat(group["detected_at"].replace("Z", "+00:00"))
        if not _aware(period_start) <= detected < _aware(period_end) or group.get("read_state") in {"dismissed", "muted"}:
            continue
        if sources and group.get("source") not in sources and group.get("authority") not in sources:
            continue
        items = [item for item in group.get("items", []) if not severities or item["severity"] in severities]
        if not items:
            continue
        if len(selected) == 50:
            truncated = True
            break
        selected.append(
            {
                "event_id": group["event_id"],
                "title": group["title"][:300],
                "source": group.get("source", "")[:120],
                "severity": min(
                    (item["severity"] for item in items),
                    key=lambda value: {"high": 0, "medium": 1, "low": 2}.get(value, 3),
                ),
                "detected_at": group["detected_at"],
                "source_url": group.get("source_url"),
                "impact_count": len(items),
                "impacts_truncated": len(items) > 5,
                "impacts": [
                    {
                        "law_id": item["law_id"],
                        "law_title": item["law_title"][:300],
                        "potential_effect": item["potential_effect"][:800],
                        "next_step": item["suggested_next_step"][:300],
                        "comparison": item["links"].get("comparison"),
                        "evidence": item["links"].get("relation_evidence"),
                    }
                    for item in items[:5]
                ],
            }
        )
    return {"events": selected, "truncated": truncated}


def render_message(settings: Settings, delivery: DigestDelivery, user: User) -> tuple[str, str, str]:
    locale = normalize_locale(user.locale, settings.default_locale)
    message = _MESSAGES[locale]
    events = (delivery.summary or {}).get("events", [])
    inbox_url = settings.public_base_url + "/impact"
    unsubscribe_url = (
        settings.public_base_url
        + "/unsubscribe?token="
        + preference_token(settings, delivery.preference_id)
    )
    subject = message["subject"].format(count=len(events))
    lines = [message["heading"]]
    cards = []
    limit_notice = message["event_limit"] if (delivery.summary or {}).get("truncated") else ""
    if limit_notice:
        lines.append("\n" + limit_notice)
    for event in events:
        severity = message["severity"].get(event["severity"], event["severity"])
        lines.append(f"\n{event['title']} [{severity}] — {event['source']}")
        impacts = []
        for impact in event["impacts"]:
            evidence_url = _application_url(settings, impact.get("evidence"))
            comparison_url = _application_url(settings, impact.get("comparison"))
            review_url = evidence_url or comparison_url
            lines.append(
                f"• {impact['law_title']}: {impact['next_step']}"
                + (f"\n  Evidence: {review_url}" if review_url else "")
            )
            evidence_link = (
                f'<br><a href="{escape(review_url, quote=True)}">{escape(message["evidence"])}</a>'
                if review_url
                else ""
            )
            impacts.append(
                f"<li><strong>{escape(impact['law_title'])}</strong><br>"
                f"{escape(impact['potential_effect'])}<br>"
                f"<em>{escape(impact['next_step'])}</em>{evidence_link}</li>"
            )
        law_notice = ""
        if event.get("impacts_truncated") and isinstance(event.get("impact_count"), int):
            law_notice = message["more_laws"].format(shown=len(event["impacts"]), total=event["impact_count"])
            lines.append(law_notice)
        cards.append(
            f"<section><h2>{escape(event['title'])}</h2>"
            f"<p>{escape(event['source'])} · {escape(severity)}</p>"
            f"<ul>{''.join(impacts)}</ul>"
            + (f"<p>{escape(law_notice)}</p>" if law_notice else "")
            + "</section>"
        )
    if not events:
        lines.append("\n" + message["empty"])
    lines.extend([f"\n{message['open']}: {inbox_url}", f"{message['unsubscribe']}: {unsubscribe_url}"])
    html = (
        f'<html lang="{locale}"><body><h1>{escape(message["heading"])}</h1>'
        + (f"<p>{escape(limit_notice)}</p>" if limit_notice else "")
        + ("".join(cards) or f'<p>{escape(message["empty"])}</p>')
        + f'<p><a href="{inbox_url}">{escape(message["open"])}</a></p>'
        + f'<p><a href="{unsubscribe_url}">{escape(message["unsubscribe"])}</a></p>'
        + "</body></html>"
    )
    return subject, "\n".join(lines), html


def enqueue_due(database: Database, settings: Settings, limit: int = 100) -> dict:
    now = utcnow()
    queued = 0
    with database.session(include_all_organizations=True) as session:
        preferences = list(
            session.scalars(
                select(DigestPreference)
                .where(
                    DigestPreference.enabled.is_(True),
                    DigestPreference.next_delivery_at <= now,
                )
                .order_by(DigestPreference.next_delivery_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for preference in preferences:
            period_end = _aware(preference.next_delivery_at or now)
            period_start = _aware(preference.last_sent_at or (period_end - FREQUENCIES[preference.frequency]))
            delivery = session.scalar(
                select(DigestDelivery).where(
                    DigestDelivery.preference_id == preference.id,
                    DigestDelivery.period_end == period_end,
                )
            )
            if not delivery:
                delivery = DigestDelivery(
                    organization_id=preference.organization_id,
                    user_id=preference.user_id,
                    preference_id=preference.id,
                    frequency=preference.frequency,
                    period_start=period_start,
                    period_end=period_end,
                )
                session.add(delivery)
                session.flush()
            _job, reused = jobs.enqueue(
                session,
                job_type="digest_delivery",
                target_type="digest_delivery",
                target_id=delivery.id,
                queue="maintenance",
                idempotency_key=f"digest:{preference.id}:{period_end.isoformat()}",
                payload={"delivery_id": delivery.id},
                priority=2,
                max_attempts=settings.job_max_attempts,
                organization_id=preference.organization_id,
                steps=[("Build saved impact summary", {}), ("Deliver opted-in email", {})],
            )
            queued += int(not reused)
            preference.next_delivery_at = next_delivery(period_end, preference.frequency)
            preference.updated_at = now
        session.commit()
    return {"due": len(preferences), "queued": queued}


PREPARATION_VERSION = "digest-preparation-v1"


def _preference_fingerprint(preference: DigestPreference) -> str:
    return hashlib.sha256(json.dumps({
        "enabled": preference.enabled, "frequency": preference.frequency,
        "sources": sorted(preference.sources or []), "severities": sorted(preference.severities or []),
    }, sort_keys=True).encode()).hexdigest()


def _selection_context(delivery: DigestDelivery) -> dict:
    return {"version": PREPARATION_VERSION, "delivery_id": delivery.id,
            "organization_id": delivery.organization_id, "user_id": delivery.user_id,
            "preference_id": delivery.preference_id,
            "period_start": _iso(delivery.period_start), "period_end": _iso(delivery.period_end)}


def _validate_selection(delivery: DigestDelivery, checkpoint: dict) -> None:
    if any(checkpoint.get(key) != value for key, value in _selection_context(delivery).items()):
        raise DomainError("The digest checkpoint does not match this delivery.", 409, "digest_checkpoint_invalid")
    try:
        datetime.fromisoformat(checkpoint["admitted_before"])
        ids = checkpoint["event_ids"]
        if not isinstance(ids, list) or len(ids) > 51 or len(set(ids)) != len(ids):
            raise ValueError("Invalid selected event IDs")
        if not all(isinstance(value, str) and 0 < len(value) <= 36 for value in ids):
            raise ValueError("Invalid selected event ID")
        if not all(type(checkpoint[key]) is int and checkpoint[key] >= 0 for key in ("processed", "batches", "restarts")):
            raise ValueError("Invalid preparation counters")
        if type(checkpoint["complete"]) is not bool:
            raise ValueError("Invalid preparation state")
        if checkpoint.get("cursor"):
            datetime.fromisoformat(checkpoint["cursor"]["detected_at"])
            if not isinstance(checkpoint["cursor"]["id"], str):
                raise ValueError("Invalid event cursor")
    except (KeyError, TypeError, ValueError) as exc:
        raise DomainError("The digest checkpoint cannot be resumed.", 409, "digest_checkpoint_invalid") from exc


def _recipient(session: Session, delivery: DigestDelivery, *, lock: bool = False) -> User:
    user_query = select(User).where(User.id == delivery.user_id, User.active.is_(True))
    member_query = select(OrganizationMembership.id).where(
        OrganizationMembership.organization_id == delivery.organization_id,
        OrganizationMembership.user_id == delivery.user_id,
    )
    user = session.scalar(user_query.with_for_update() if lock else user_query)
    member = session.scalar(member_query.with_for_update() if lock else member_query)
    if not user or not member:
        raise DomainError("The digest recipient no longer has access to this organization.", 409, "digest_recipient_inactive")
    return user


def prepare_batch(session: Session, delivery_id: str, checkpoint: dict | None = None) -> dict:
    """Prepare <=50 event keys. Caller commits cursor and queue yield atomically."""
    delivery = session.scalar(select(DigestDelivery).where(DigestDelivery.id == delivery_id).with_for_update())
    if not delivery:
        raise DomainError("The digest delivery was not found.", 404, "not_found")
    preference = session.get(DigestPreference, delivery.preference_id)
    if not preference:
        raise DomainError("The digest preference was not found.", 404, "not_found")
    _recipient(session, delivery)
    if checkpoint is not None and not isinstance(checkpoint, dict):
        raise DomainError("The digest checkpoint cannot be resumed.", 409, "digest_checkpoint_invalid")
    checkpoint = dict(checkpoint or {})
    if checkpoint:
        _validate_selection(delivery, checkpoint)
    fingerprint = _preference_fingerprint(preference)
    if not checkpoint or checkpoint.get("preference_fingerprint") != fingerprint:
        checkpoint = {**_selection_context(delivery), "admitted_before": _iso(utcnow()),
                      "preference_fingerprint": fingerprint, "cursor": None, "event_ids": [],
                      "processed": 0, "batches": 0, "complete": False,
                      "restarts": checkpoint.get("restarts", 0) + bool(checkpoint)}
    if checkpoint["complete"] or delivery.status == "succeeded" or not preference.enabled:
        return {**checkpoint, "complete": True}
    reader = ImpactInboxReader(delivery.organization_id, delivery.user_id)
    filters = replace(inbox_filters(preference, delivery.period_start, delivery.period_end),
                      admitted_before=datetime.fromisoformat(checkpoint["admitted_before"]))
    page = reader.event_page(session, filters, cursor=checkpoint["cursor"])
    summary = filtered_summary(page, preference, delivery.period_start, delivery.period_end)
    ids = list(dict.fromkeys(checkpoint["event_ids"] + [item["event_id"] for item in summary["events"]]))[:51]
    return {**checkpoint, "event_ids": ids, "cursor": page["cursor"],
            "processed": checkpoint["processed"] + page["scanned"], "batches": checkpoint["batches"] + 1,
            "complete": len(ids) == 51 or not page["has_more"]}


def deliver(database: Database, settings: Settings, delivery_id: str, *, selection: dict | None = None,
            job_id: str | None = None, worker: str | None = None) -> dict | None:
    with database.session() as session:
        if job_id:
            owned_job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if not owned_job or owned_job.type != "digest_delivery" or owned_job.target_id != delivery_id or owned_job.state != "running" or owned_job.lease_owner != worker:
                return None
            if owned_job.cancel_requested:
                raise jobs.JobCancelled()
        delivery = session.scalar(select(DigestDelivery).where(DigestDelivery.id == delivery_id).with_for_update())
        if not delivery:
            raise DomainError("The digest delivery was not found.", 404, "not_found")
        if delivery.status == "succeeded":
            return serialize_delivery(delivery)
        preference = session.scalar(select(DigestPreference).where(DigestPreference.id == delivery.preference_id).with_for_update())
        if not preference:
            raise DomainError("The digest preference was not found.", 404, "not_found")
        user = _recipient(session, delivery, lock=True)
        if not preference.enabled:
            delivery.status, delivery.error = "skipped", "Email digest disabled by recipient."
            session.commit()
            return serialize_delivery(delivery)
        filters = inbox_filters(preference, delivery.period_start, delivery.period_end)
        reader = ImpactInboxReader(delivery.organization_id, delivery.user_id)
        if selection is not None:
            _validate_selection(delivery, selection)
            if not selection.get("complete") or selection.get("preference_fingerprint") != _preference_fingerprint(preference):
                raise DomainError("Digest preferences changed; preparation will restart before sending.", 409, "digest_preferences_changed")
            filters = replace(filters, event_ids=tuple(selection["event_ids"]),
                              admitted_before=datetime.fromisoformat(selection["admitted_before"]))
        # Recheck current access, personal state and saved conclusions for at most
        # 51 selected events. A completed preparation is never a permission cache.
        groups = reader.iter_groups(session, filters)
        delivery.summary = summarize_groups(groups, preference, delivery.period_start, delivery.period_end)
        delivery.item_count = len(delivery.summary["events"])
        if not delivery.item_count:
            delivery.status = "skipped"
            delivery.error = None
            preference.last_sent_at = max(_aware(preference.last_sent_at), _aware(delivery.period_end)) if preference.last_sent_at else delivery.period_end
            session.commit()
            return serialize_delivery(delivery)
        subject, body, html = render_message(settings, delivery, user)
        try:
            mode = AuthMailer(settings).send_message(
                user.email,
                subject,
                body,
                html,
                user.locale,
                message_id=f"<{delivery.id}@helvetic-lens.local>",
            )
        except DomainError as exc:
            delivery.status = "failed"
            delivery.error = exc.message[:1000]
            if job_id:
                owned_job.heartbeat_at = utcnow()
            session.commit()
            raise
        if mode == "disabled":
            delivery.status = "skipped"
            delivery.error = "Email delivery is not configured; the web digest remains available."
        else:
            delivery.status = "succeeded"
            delivery.error = None
            delivery.sent_at = utcnow()
        preference.last_sent_at = max(_aware(preference.last_sent_at), _aware(delivery.period_end)) if preference.last_sent_at else delivery.period_end
        if job_id:
            owned_job.heartbeat_at = utcnow()
        session.commit()
        return serialize_delivery(delivery)
