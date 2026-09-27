"""Actor-bound receipts for explicitly saving public catalogue metadata, never full text."""
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Request
from pydantic import Field, field_validator
from sqlalchemy import select

from . import legal_profiles
from .db import utcnow
from .membership_locks import require_current_admin
from .models import User, UserSession
from .monitoring_subjects import _actor
from .product_api import EntryInput, Product, dossier, entry_payload, fail
from .product_models import DossierEntry

FORMAT = "helveticlens.discovery-record.v1"
LIFETIME = timedelta(minutes=30)
MAX_RECEIPT = 24576


class SourceRecord(legal_profiles.Input):
    id: str = Field(min_length=1, max_length=2000)
    kind: Literal["literature", "official_metadata", "web_source"]
    provider: Literal["Europe PMC", "Fedlex", "Search1API"]
    title: str = Field(max_length=700)
    summary: str = Field(max_length=700)
    url: str = Field(min_length=1, max_length=2000)
    date: str | None = Field(default=None, max_length=40)
    retrieval_queries: list[Annotated[str, Field(min_length=2, max_length=300)]] = Field(default_factory=list, max_length=3)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return EntryInput.valid_url(value)


class ImportReference(legal_profiles.Input):
    request_key: UUID
    receipt: str = Field(min_length=1, max_length=MAX_RECEIPT)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def principal(session, identity, now, *, write=False, lock=False, dossier_id=None):
    from .product_guest_access import principal_scope

    foreign = session.info.get("organization_id") != identity.organization_id
    if foreign and not principal_scope(session, identity, dossier_id):
        fail("Dossier access is no longer available.", 401)
    from .product_access import current_principal_grant

    delegated = write and current_principal_grant(session, identity)
    if write and not delegated:
        require_current_admin(session, identity)
    user = session.get(User, identity.user_id, populate_existing=True, with_for_update=write or lock)
    login = session.get(UserSession, identity.session_id, populate_existing=True, with_for_update=write or lock)
    if (not user or not user.active or not login or login.user_id != user.id
            or login.organization_id != identity.organization_id or login.revoked_at
            or login.expires_at.replace(tzinfo=UTC) <= now):
        fail("Your session changed. Sign in again before saving sources.", 401)
    if foreign and not principal_scope(session, identity, dossier_id):
        fail("Dossier access is no longer available.", 401)
    if not foreign:
        _actor(session, identity.user_id, write=write and not delegated)
    return user


def signature(user, identity, value):
    scoped = [FORMAT, identity.user_id, identity.organization_id, identity.session_id, value]
    return hmac.new(user.password_hash.encode(), canonical(scoped).encode(), hashlib.sha256).hexdigest()


def prepare(session, identity, product, provider, query, details, now, *, retrieved_at=None):
    user = principal(session, identity, now)
    retrieved_at = retrieved_at or now
    for item in details["items"]:
        record = SourceRecord.model_validate(item).model_dump()
        value = {"format": FORMAT, "product": product, "provider": provider, "query": query,
                 "retrieved_at": retrieved_at.isoformat(), "expires_at": (retrieved_at + LIFETIME).isoformat(),
                 "page_number": details["page_number"], "record": record}
        receipt = base64.urlsafe_b64encode(canonical({**value, "signature": signature(user, identity, value)}).encode()).decode()
        if len(receipt) > MAX_RECEIPT:
            fail("This source record is too large to save. Refine the search.", 502)
        item.update(record, discovery_receipt=receipt)


def decode(user, identity, product, receipt, now):
    try:
        value = json.loads(base64.b64decode(receipt, altchars=b"-_", validate=True))
        if set(value) != {"format", "product", "provider", "query", "retrieved_at", "expires_at", "page_number", "record", "signature"}:
            raise ValueError
        supplied = value.pop("signature")
        if not isinstance(supplied, str) or not hmac.compare_digest(signature(user, identity, value), supplied):
            raise ValueError
        retrieved, expires = (datetime.fromisoformat(value[key]) for key in ("retrieved_at", "expires_at"))
        if (value["format"] != FORMAT or value["product"] != product
                or retrieved.tzinfo is None or expires.tzinfo is None or retrieved > now
                or expires - retrieved != LIFETIME):
            raise ValueError
        return value, expires
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        fail("This search record cannot be verified. Run the search again before saving it.", 409)


def provenance_routes(router, service, actor):
    @router.post("/dossiers/{identifier}/discovery-references", status_code=201)
    def save(product: Product, identifier: str, data: ImportReference, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            now = utcnow()
            user = principal(session, identity, now, write=True)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            value, expires = decode(user, identity, product, data.receipt, now)
            digest = hashlib.sha256(data.receipt.encode()).hexdigest()
            previous = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.id,
                DossierEntry.request_key == str(data.request_key)))
            if previous:
                if (previous.kind != "reference" or previous.actor_user_id != identity.user_id
                        or previous.data_json.get("discovery_receipt_sha256") != digest):
                    fail("This request key belongs to a different saved entry.", 409)
                return entry_payload(session, previous)
            if now >= expires:
                fail("This search record expired after 30 minutes. Run the search again before saving it.", 409)
            record = value["record"]
            provenance = {key: value[key] for key in ("provider", "query", "retrieved_at", "page_number", "record")}
            entry = DossierEntry(dossier_id=parent.id, request_key=str(data.request_key), kind="reference",
                title=record["title"][:240], body=f"Catalogue metadata from {record['provider']} ({record['kind']}). {record['summary']}",
                url=record["url"], actor_user_id=identity.user_id,
                data_json={"relevance": "uncertain", "discovery": provenance, "discovery_receipt_sha256": digest})
            session.add(entry)
            session.commit()
            return entry_payload(session, entry)
