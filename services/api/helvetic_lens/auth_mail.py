"""Small authentication-message delivery boundary for the single-server beta."""

from __future__ import annotations

import json
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import quote

from .config import DomainError, Settings


class AuthMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, email: str, purpose: str, token: str) -> str:
        if purpose == "verify_email":
            subject = "Verify your Helvetic Lens email"
            path = f"/login?verify={quote(token, safe='')}"
            action = "Verify email"
        elif purpose == "reset_password":
            subject = "Reset your Helvetic Lens password"
            path = f"/login?reset={quote(token, safe='')}"
            action = "Reset password"
        else:
            raise ValueError("unsupported authentication message")
        link = self.settings.public_base_url + path
        body = (
            f"{action}: {link}\n\n"
            "This one-time link expires automatically. If you did not request it, ignore this message."
        )
        if self.settings.auth_email_mode == "disabled":
            return "disabled"
        if self.settings.auth_email_mode == "development":
            self._write_development_message(email, subject, body)
            return "development"
        self._send_smtp(email, subject, body)
        return "smtp"

    def _write_development_message(self, email: str, subject: str, body: str) -> None:
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
                {"to": email, "subject": subject, "body": body, "created_at": stamp.isoformat()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _send_smtp(self, email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.auth_email_from
        message["To"] = email
        message["Subject"] = subject
        message.set_content(body)
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
