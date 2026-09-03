"""Authenticated encryption for provider credentials stored in PostgreSQL."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import DomainError, Settings

PREFIX = "enc:v1:"
AAD = b"helvetic-lens:provider-credential:v1"


class CredentialCipher:
    """Use the deployment key, or a volume-persisted key for local development."""

    def __init__(self, settings: Settings):
        configured = settings.credential_encryption_key.get_secret_value().encode("utf-8")
        material = configured or self._local_key(settings.storage_path)
        self._key = hashlib.sha256(material).digest()

    @staticmethod
    def _local_key(storage_path: Path) -> bytes:
        storage_path.mkdir(parents=True, exist_ok=True)
        key_path = storage_path / ".credential-key"
        try:
            value = key_path.read_bytes().strip()
            if value:
                return value
        except FileNotFoundError:
            pass
        value = base64.urlsafe_b64encode(os.urandom(32))
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as target:
                target.write(value)
        except FileExistsError:
            value = key_path.read_bytes().strip()
        if not value:
            raise DomainError(
                "The deployment credential key could not be initialized.",
                500,
                "credential_key_unavailable",
            )
        return value

    @staticmethod
    def is_encrypted(value: str | None) -> bool:
        return bool(value and value.startswith(PREFIX))

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        nonce = os.urandom(12)
        encrypted = AESGCM(self._key).encrypt(nonce, value.encode("utf-8"), AAD)
        return PREFIX + base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    def decrypt(self, value: str | None) -> str:
        if not value:
            return ""
        if not self.is_encrypted(value):
            return value  # Migrated on service initialization or the next save.
        try:
            payload = base64.urlsafe_b64decode(value[len(PREFIX) :].encode("ascii"))
            return AESGCM(self._key).decrypt(payload[:12], payload[12:], AAD).decode("utf-8")
        except (InvalidTag, ValueError, UnicodeError) as exc:
            raise DomainError(
                "The saved provider credential cannot be decrypted with this deployment key.",
                500,
                "credential_decryption_failed",
            ) from exc
