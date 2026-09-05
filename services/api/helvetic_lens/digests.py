"""Opt-in digests built only from the persisted organization impact inbox."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import select

from . import jobs
from .auth_mail import AuthMailer
from .config import DomainError, Settings
from .db import Database, utcnow
from .impact_inbox import ImpactInboxFilters, ImpactInboxReader
from .locales import normalize_locale
from .models import DigestDelivery, DigestPreference, User

SEVERITIES = {"high", "medium", "low", "none", "unknown"}
FREQUENCIES = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}

_MESSAGES = {
    "de-CH": {
        "subject": "Helvetic Lens: {count} Änderungen zur Prüfung",
        "heading": "Ihr regulatorischer Überblick",
        "empty": "Für diesen Zeitraum gibt es keine passenden neuen Hinweise.",
        "open": "Impact-Inbox öffnen",
        "unsubscribe": "E-Mail-Digest abbestellen",
        "evidence": "Beleg öffnen",
        "severity": {"high": "hoch", "medium": "mittel", "low": "niedrig", "none": "keine", "unknown": "unklar"},
    },
    "fr-CH": {
        "subject": "Helvetic Lens : {count} changements à examiner",
        "heading": "Votre synthèse réglementaire",
        "empty": "Aucun nouvel élément correspondant pour cette période.",
        "open": "Ouvrir la boîte d’impact",
        "unsubscribe": "Se désabonner du résumé e-mail",
        "evidence": "Ouvrir la preuve",
        "severity": {"high": "élevée", "medium": "moyenne", "low": "faible", "none": "aucune", "unknown": "incertaine"},
    },
    "it-CH": {
        "subject": "Helvetic Lens: {count} modifiche da esaminare",
        "heading": "Il tuo riepilogo normativo",
        "empty": "Nessun nuovo elemento corrispondente per questo periodo.",
        "open": "Apri la casella impatti",
        "unsubscribe": "Annulla il riepilogo e-mail",
        "evidence": "Apri la prova",
        "severity": {"high": "alta", "medium": "media", "low": "bassa", "none": "nessuna", "unknown": "incerta"},
    },
    "rm-CH": {
        "subject": "Helvetic Lens: {count} midadas da controllar",
        "heading": "Tia survista regulativa",
        "empty": "I na dat nagins novs avis adattads per questa perioda.",
        "open": "Avrir la posta d’impacts",
        "unsubscribe": "Deabunar il resumaziun per e-mail",
        "evidence": "Avrir la cumprova",
        "severity": {"high": "auta", "medium": "mesauna", "low": "bassa", "none": "nagina", "unknown": "intschertezza"},
    },
    "en-CH": {
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
        cards.append(
            f"<section><h2>{escape(event['title'])}</h2>"
            f"<p>{escape(event['source'])} · {escape(severity)}</p>"
            f"<ul>{''.join(impacts)}</ul></section>"
        )
    if not events:
        lines.append("\n" + message["empty"])
    lines.extend([f"\n{message['open']}: {inbox_url}", f"{message['unsubscribe']}: {unsubscribe_url}"])
    html = (
        f'<html lang="{locale}"><body><h1>{escape(message["heading"])}</h1>'
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


def deliver(database: Database, settings: Settings, delivery_id: str) -> dict:
    with database.session() as session:
        delivery = session.get(DigestDelivery, delivery_id)
        if not delivery:
            raise DomainError("The digest delivery was not found.", 404, "not_found")
        if delivery.status == "succeeded":
            return serialize_delivery(delivery)
        preference = session.get(DigestPreference, delivery.preference_id)
        user = session.get(User, delivery.user_id)
        if not preference or not user or not user.active:
            raise DomainError("The digest recipient is no longer active.", 409, "digest_recipient_inactive")
        groups = ImpactInboxReader(delivery.organization_id, delivery.user_id).iter_groups(
            session, inbox_filters(preference, delivery.period_start, delivery.period_end)
        )
        delivery.summary = summarize_groups(groups, preference, delivery.period_start, delivery.period_end)
        delivery.item_count = len(delivery.summary["events"])
        if not delivery.item_count:
            delivery.status = "skipped"
            delivery.error = None
            preference.last_sent_at = delivery.period_end
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
            session.commit()
            raise
        if mode == "disabled":
            delivery.status = "skipped"
            delivery.error = "Email delivery is not configured; the web digest remains available."
        else:
            delivery.status = "succeeded"
            delivery.error = None
            delivery.sent_at = utcnow()
        preference.last_sent_at = delivery.period_end
        session.commit()
        return serialize_delivery(delivery)
