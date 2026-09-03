"""Small authentication-message delivery boundary for the single-server beta."""

from __future__ import annotations

import json
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import quote

from .config import DomainError, Settings
from .locales import normalize_locale

_MESSAGES = {
    "de-CH": {
        "verify_email": ("E-Mail für Helvetic Lens bestätigen", "E-Mail bestätigen"),
        "reset_password": ("Passwort für Helvetic Lens zurücksetzen", "Passwort zurücksetzen"),
        "note": "Dieser einmalige Link läuft automatisch ab. Falls Sie ihn nicht angefordert haben, ignorieren Sie diese Nachricht.",
    },
    "fr-CH": {
        "verify_email": ("Confirmez votre adresse Helvetic Lens", "Confirmer l’adresse"),
        "reset_password": ("Réinitialisez votre mot de passe Helvetic Lens", "Réinitialiser le mot de passe"),
        "note": "Ce lien à usage unique expire automatiquement. Si vous ne l’avez pas demandé, ignorez ce message.",
    },
    "it-CH": {
        "verify_email": ("Conferma l’e-mail di Helvetic Lens", "Conferma e-mail"),
        "reset_password": ("Reimposta la password di Helvetic Lens", "Reimposta password"),
        "note": "Questo link monouso scade automaticamente. Se non lo hai richiesto, ignora questo messaggio.",
    },
    "rm-CH": {
        "verify_email": ("Conferma tia adressa per Helvetic Lens", "Confermar l’adressa"),
        "reset_password": ("Redefinescha tes pled-clav per Helvetic Lens", "Redefinir il pled-clav"),
        "note": "Questa colliaziun d’in diever scada automaticamain. Sche ti n’has betg dumandà ella, ignorescha quest messadi.",
    },
    "en-CH": {
        "verify_email": ("Verify your Helvetic Lens email", "Verify email"),
        "reset_password": ("Reset your Helvetic Lens password", "Reset password"),
        "note": "This one-time link expires automatically. If you did not request it, ignore this message.",
    },
}


class AuthMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, email: str, purpose: str, token: str, locale: str = "en-CH") -> str:
        selected = normalize_locale(locale, self.settings.default_locale)
        messages = _MESSAGES[selected]
        if purpose == "verify_email":
            path = f"/login?verify={quote(token, safe='')}"
        elif purpose == "reset_password":
            path = f"/login?reset={quote(token, safe='')}"
        else:
            raise ValueError("unsupported authentication message")
        subject, action = messages[purpose]
        link = self.settings.public_base_url + path + f"&locale={quote(selected)}"
        body = f"{action}: {link}\n\n{messages['note']}"
        html = (
            f'<html lang="{selected}"><body><p><a href="{link}">{action}</a></p>'
            f"<p>{messages['note']}</p></body></html>"
        )
        return self.send_message(email, subject, body, html, selected)

    def send_message(
        self,
        email: str,
        subject: str,
        body: str,
        html: str,
        locale: str = "en-CH",
        *,
        message_id: str | None = None,
    ) -> str:
        if self.settings.auth_email_mode == "disabled":
            return "disabled"
        if self.settings.auth_email_mode == "development":
            self._write_development_message(email, subject, body, html, locale)
            return "development"
        self._send_smtp(email, subject, body, html, message_id=message_id)
        return "smtp"

    def _write_development_message(
        self, email: str, subject: str, body: str, html: str, locale: str
    ) -> None:
        folder = self.settings.storage_path / "auth-mailbox"
        folder.mkdir(parents=True, exist_ok=True)
        cutoff = datetime.now(UTC) - timedelta(hours=48)
        for candidate in folder.glob("*.json"):
            try:
                if datetime.fromtimestamp(candidate.stat().st_mtime, UTC) < cutoff:
                    candidate.unlink()
            except OSError:
                continue
        stamp = datetime.now(UTC)
        target = folder / f"{stamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        target.write_text(
            json.dumps(
                {
                    "to": email,
                    "subject": subject,
                    "body": body,
                    "html": html,
                    "locale": locale,
                    "created_at": stamp.isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _send_smtp(
        self,
        email: str,
        subject: str,
        body: str,
        html: str,
        *,
        message_id: str | None = None,
    ) -> None:
        message = EmailMessage()
        message["From"] = self.settings.auth_email_from
        message["To"] = email
        message["Subject"] = subject
        if message_id:
            message["Message-ID"] = message_id
        message.set_content(body)
        message.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(
                self.settings.auth_smtp_host,
                self.settings.auth_smtp_port,
                timeout=20,
            ) as client:
                if self.settings.auth_smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if self.settings.auth_smtp_username:
                    client.login(
                        self.settings.auth_smtp_username,
                        self.settings.auth_smtp_password.get_secret_value(),
                    )
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise DomainError(
                "The account email could not be delivered. Try again later.",
                503,
                "auth_email_unavailable",
            ) from exc
