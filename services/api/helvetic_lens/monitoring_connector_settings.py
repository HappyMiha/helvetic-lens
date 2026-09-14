"""Validated source snapshots shared by HTTP requests and scheduled collectors."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import delete, select, update

from .config import DomainError
from .credential_crypto import CredentialCipher
from .monitoring_connector_models import MonitoringConnectorConfiguration as Configuration


def permission_model(key):
    from .auction_source_models import AuctionSourcePermission
    from .commute_models import CommuteSourcePermission
    from .hazard_source_models import HazardSourcePermission
    from .road_models import RoadSourcePermission
    from .trademark_source_models import TrademarkSourcePermission
    return {"aste_source_permission_id": AuctionSourcePermission, "ipi_source_permission_id": TrademarkSourcePermission,
        "road_source_permission_id": RoadSourcePermission, "hazard_source_permission_id": HazardSourcePermission,
        "commute_gtfs_rt_permission_id": CommuteSourcePermission, "commute_gtfs_sa_permission_id": CommuteSourcePermission}[key]

# Only actual native connector options belong here. Section visibility and
# source-approval documents are deliberately not editable collector switches.
FIELDS = {
    "pollen": {}, "river": {}, "air": {},
    "warnings": {"hazard_source_enabled": "boolean", "hazard_source_permission_id": "permission"},
    "commute": {"commute_source_enabled": "boolean", "commute_static_enabled": "boolean",
        "commute_static_dataset_id": "identifier", "commute_static_cache_max_bytes": "integer",
        "commute_gtfs_rt_permission_id": "permission", "commute_gtfs_sa_permission_id": "permission",
        "commute_gtfs_rt_key": "secret", "commute_gtfs_sa_key": "secret"},
    "traffic": {"road_source_enabled": "boolean", "road_source_permission_id": "permission", "road_source_key": "secret"},
    "tenders": {"simap_public_source_enabled": "boolean", "tender_public_storage_max_bytes": "integer",
        "tender_monitor_max_versions": "integer"},
    "ip": {"ipi_source_enabled": "boolean", "ipi_source_permission_id": "permission",
        "ipi_username": "login", "ipi_password": "password"},
    "auctions": {"aste_source_enabled": "boolean", "aste_source_permission_id": "permission"},
}
SECRET_KINDS = {"secret", "login", "password"}
LIMITS = {"commute_static_cache_max_bytes": (512_000_000, 100_000_000_000),
    "tender_public_storage_max_bytes": (1, 100_000_000_000), "tender_monitor_max_versions": (1, 1_000_000)}


def domain_fields(domain):
    if domain not in FIELDS:
        raise DomainError("Monitoring category not found.", 404, "not_found")
    return FIELDS[domain]


def credentials(row, cipher):
    if not row.encrypted_credentials:
        return {}
    try:
        if not cipher.is_encrypted(row.encrypted_credentials):
            raise ValueError()
        payload = json.loads(cipher.decrypt(row.encrypted_credentials))
        if payload["domain"] != row.domain or not isinstance(payload["values"], dict):
            raise ValueError()
        values = payload["values"]
        if any(domain_fields(row.domain).get(key) not in SECRET_KINDS or not isinstance(value, str)
               for key, value in values.items()):
            raise ValueError()
        return values
    except (ValueError, KeyError, TypeError):
        raise DomainError("Saved connector credentials are unavailable.", 503, "connector_credentials_unavailable") from None


def resolve(session, base, cipher):
    updates = {}
    revisions = {}
    for row in session.scalars(select(Configuration)):
        revisions[row.domain] = row.revision
        schema = domain_fields(row.domain)
        if any(key not in schema or schema[key] in SECRET_KINDS for key in row.values):
            raise DomainError("Saved source configuration is invalid.", 503, "connector_configuration_invalid")
        updates.update(row.values)
        try:
            saved = credentials(row, cipher)
        except DomainError:
            # Keep administration reachable for repair, but never fall back to an
            # environment key when a saved credential cannot be authenticated.
            saved = {key: "" for key, kind in schema.items() if kind in SECRET_KINDS}
            updates.update({key: False for key in schema if key.endswith("_enabled")})
        updates.update({key: SecretStr(value) for key, value in saved.items()})
    # A concrete immutable-in-use snapshot: never mutate shared process settings.
    value = base.model_copy(update=updates, deep=True)
    object.__setattr__(value, "_monitoring_connector_fields", frozenset(updates))
    object.__setattr__(value, "_monitoring_connector_revisions", revisions)
    return value


def assert_current(database, settings, domain):
    revisions = getattr(settings, "_monitoring_connector_revisions", None)
    if revisions is not None:
        with database.session() as session:
            current = session.scalar(select(Configuration.revision).where(Configuration.domain == domain))
        if current != revisions.get(domain):
            raise DomainError("Source configuration changed during the operation.", 409, "connector_configuration_changed")


def load(database, base):
    with database.session() as session:
        return resolve(session, base, CredentialCipher(base))


class RequestSettings:
    """Native routers read the service's existing request-local settings context."""

    def __init__(self, service, base):
        self.service = service
        self.base = base

    def __getattr__(self, key):
        current = self.service.settings
        return getattr(current if key in getattr(current, "_monitoring_connector_fields", ()) else self.base, key)


def read(session, base, cipher, domain):
    schema = domain_fields(domain)
    row = session.get(Configuration, domain)
    if row is None:
        raise DomainError("Connector settings migration is required.", 503, "connector_configuration_unavailable")
    credential_error = False
    try:
        saved = credentials(row, cipher)
    except DomainError:
        credential_error = True
        saved = {key: "" for key, kind in schema.items() if kind in SECRET_KINDS}
    fields = []
    for key, kind in schema.items():
        field = {"id": key, "kind": kind}
        if kind in SECRET_KINDS:
            field["configured"] = bool(saved.get(key, getattr(base, key).get_secret_value())) if key not in saved else bool(saved[key])
            field["origin"] = "saved" if key in saved else "environment"
        else:
            field["value"] = row.values.get(key, getattr(base, key))
            if kind == "permission":
                model = permission_model(key)
                choices = list(session.scalars(select(model.id).order_by(model.accepted_at.desc(), model.id).limit(100)))
                if field["value"] and field["value"] not in choices:
                    choices.append(field["value"])
                field["choices"] = choices
        if key in LIMITS:
            field["minimum"], field["maximum"] = LIMITS[key]
        fields.append(field)
    advanced = {}
    if domain == "pollen":
        advanced = {"source_policy": base.pollen_source_policy.model_dump(mode="json"), "decoder": base.pollen_decoder_url}
    if domain == "commute":
        advanced = {"feed_redirect_origins": list(base.commute_feed_redirect_origins),
            "static_redirect_origins": list(base.commute_static_redirect_origins)}
    return {"domain": domain, "revision": row.revision, "fields": fields, "credential_error": credential_error, "advanced": advanced,
        "updated_at": row.updated_at.isoformat(),
        "check": row.check_result if row.check_revision == row.revision else None}


def save(session, base, cipher, domain, revision, values, secrets):
    schema = domain_fields(domain)
    if set(values) & set(secrets) or any(schema.get(key) in SECRET_KINDS or key not in schema for key in values) or any(
            schema.get(key) not in SECRET_KINDS for key in secrets):
        raise DomainError("Unsupported connector field.", 422, "invalid_connector_field")
    for key, value in values.items():
        kind = schema[key]
        if kind == "boolean":
            valid = type(value) is bool
        elif kind == "integer":
            valid = type(value) is int and LIMITS[key][0] <= value <= LIMITS[key][1]
        elif kind == "permission":
            valid = isinstance(value, str) and len(value) <= 36 and all(32 <= ord(c) < 127 for c in value)
        else:
            valid = isinstance(value, str) and len(value) <= 100
            if valid and value:
                try:
                    valid = str(UUID(value)) == value
                except ValueError:
                    valid = False
        if not valid:
            raise DomainError("Invalid connector value.", 422, "invalid_connector_value")
        if kind == "permission" and value and session.get(permission_model(key), value) is None:
            raise DomainError("Select an existing reviewed source permission.", 422, "connector_permission_not_found")
    for key, value in secrets.items():
        maximum = 320 if schema[key] == "login" else 4096 if schema[key] == "password" else 8192
        if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise DomainError("Invalid credential value.", 422, "invalid_connector_credential")
        if schema[key] == "secret" and any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise DomainError("Invalid API key.", 422, "invalid_connector_credential")
    row = session.get(Configuration, domain)
    if row is None or row.revision != revision:
        raise DomainError("Reload settings before saving again.", 409, "connector_revision_conflict")
    try:
        retained = credentials(row, cipher)
    except DomainError:
        if {key for key, kind in schema.items() if kind in SECRET_KINDS} - secrets.keys():
            raise DomainError("Replace or clear every credential to repair this connection.", 422, "connector_credentials_repair_required") from None
        retained = {}
    previous_login = retained.get("ipi_username", base.ipi_username.get_secret_value()) if domain == "ip" else None
    retained.update(secrets)  # An explicit empty string overrides an environment credential.
    result = session.execute(update(Configuration).where(Configuration.domain == domain, Configuration.revision == revision)
        .values(values={**row.values, **values}, encrypted_credentials=cipher.encrypt(json.dumps({"domain": domain, "values": retained})),
            revision=revision + 1, updated_at=datetime.now(UTC), check_result=None, check_revision=None)
        .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise DomainError("Reload settings before saving again.", 409, "connector_revision_conflict")
    if domain == "ip" and secrets:
        from .ipi_models import IPITokenCache
        accounts = {hashlib.sha256(login.encode()).hexdigest() for login in
            (previous_login, retained.get("ipi_username", base.ipi_username.get_secret_value())) if login}
        session.execute(delete(IPITokenCache).where(IPITokenCache.account_hash.in_(accounts)))
    session.expire_all()
    return read(session, base, cipher, domain)
