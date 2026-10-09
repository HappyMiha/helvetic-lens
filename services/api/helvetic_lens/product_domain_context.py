"""Optional human-provided domain context, separate from evidence and work settings."""
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Request
from pydantic import Field, ValidationError, create_model, field_validator
from sqlalchemy import select

from .db import utcnow
from .domain_packs import for_product
from .legal_profiles import Input
from .product_access import require
from .product_api import Product, dossier, fail, iso
from .product_models import DossierEntry
from .product_operations import audit, fingerprint, require_revision


@dataclass(frozen=True)
class ContextField:
    key: str
    label: str
    kind: Literal["list", "text", "dates"] = "list"
    hint: str = "One value per line. Leave empty when unknown."

    def payload(self):
        return {"key": self.key, "label": self.label, "kind": self.kind, "hint": self.hint}


FIELDS = MappingProxyType({
    "general-context/v1": (ContextField("subjects", "Subjects"), ContextField("questions", "Research questions"),
        ContextField("places", "Places"), ContextField("relevant_dates", "Relevant dates", "dates")),
    "legal-context/v1": (
        ContextField("jurisdictions", "Jurisdictions"),
        ContextField("legal_areas", "Legal areas"),
        ContextField("parties", "Parties"),
        ContextField("organisations", "Organisations"),
        ContextField("courts", "Courts"),
        ContextField("authorities", "Authorities"),
        ContextField("laws", "Laws"),
        ContextField("articles", "Articles"),
        ContextField("case_ids", "Case identifiers"),
        ContextField("procedural_stage", "Procedural stage", "text", "Your recorded stage; leave empty when unknown."),
        ContextField("relevant_dates", "Relevant dates", "dates", "One date per line, YYYY-MM-DD. Dates do not establish legal applicability."),
        ContextField("tags", "Tags"),
    ),
    "pharma-context/v1": (
        ContextField("product_names", "Product names"),
        ContextField("active_substances", "Active substances"),
        ContextField("indications", "Indications"),
        ContextField("countries", "Countries / markets"),
        ContextField("company_names", "Companies"),
        ContextField("therapeutic_areas", "Therapeutic areas"),
        ContextField("regulatory_ids", "Regulatory identifiers"),
        ContextField("market_access_ids", "Market access identifiers"),
        ContextField("trial_ids", "Trial identifiers"),
        ContextField("competitors", "Comparators / competitors"),
        ContextField("tags", "Tags"),
    ),
})

Value = Annotated[str, Field(strict=True, min_length=1, max_length=240)]
Values = Annotated[list[Value], Field(max_length=30, strict=True)]
Text = Annotated[str, Field(strict=True, max_length=240)]


class ContextValues(Input):
    @field_validator("*", mode="after")
    @classmethod
    def normalize(cls, value, info):
        if isinstance(value, list):
            value = list(dict.fromkeys(value))  # Exact duplicates only; never resolve aliases.
            if info.field_name == "relevant_dates":
                for item in value:
                    if date.fromisoformat(item).isoformat() != item:
                        raise ValueError("Use dates in YYYY-MM-DD format.")
        return value


SCHEMAS = MappingProxyType({
    key: create_model(key.replace("-", "_").replace("/", "_"), __base__=ContextValues,
        **{field.key: (Text, "") if field.kind == "text" else (Values, Field(default_factory=list))
           for field in fields})
    for key, fields in FIELDS.items()
})


class ContextInput(Input):
    expected_revision: int = Field(ge=1, strict=True)
    request_key: UUID
    schema_id: str = Field(min_length=1, max_length=80)
    values: dict = Field(max_length=12)


def validated(schema_id, values):
    try:
        result = SCHEMAS[schema_id].model_validate(values).model_dump(mode="json")
    except ValidationError as exc:
        fields = ", ".join(sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]}))
        # Never echo submitted private values in errors/logs.
        fail(f"Check these context fields: {fields}. Use up to 30 values per field, 240 characters each; dates use YYYY-MM-DD.")
    if sum(len(item) for value in result.values() for item in (value if isinstance(value, list) else [value])) > 12000:
        fail("Keep the combined dossier subject details within 12,000 characters.")
    return result


def payload(row):
    pack = for_product(row.product)
    saved = row.domain_context_json or {}
    schema_id = saved.get("schema_id", pack.context_schema_id)
    if (schema_id != pack.context_schema_id or schema_id not in SCHEMAS
            or saved and (saved.get("domain") != pack.domain or saved.get("pack_id") != pack.id)):
        fail("This saved context uses an unavailable schema. Its data is retained; the rest of the dossier remains available.",
             409, "domain_context_schema_unavailable")
    return {"domain": pack.domain, "pack_id": pack.id, "pack_version": saved.get("pack_version", pack.version),
            "schema_id": schema_id, "revision": row.revision, "saved": bool(saved),
            "updated_at": saved.get("updated_at"), "values": validated(schema_id, saved.get("values", {})),
            "fields": [field.payload() for field in FIELDS[schema_id]]}


def brief_fields(row):
    # Leave older/future schema bytes untouched; a printout must not reinterpret them.
    saved = row.domain_context_json or {}
    if not saved:
        return []
    pack = for_product(row.product)
    if saved.get("schema_id") != pack.context_schema_id or saved.get("domain") != pack.domain:
        return [("Dossier context", "Saved schema unavailable; retained in the private JSON export.")]
    values = validated(pack.context_schema_id, saved.get("values", {}))
    return [(field.label, "; ".join(value) if isinstance(value, list) else value)
            for field in FIELDS[pack.context_schema_id] if (value := values.get(field.key))]


def routes(router, service, actor):
    @router.get("/dossiers/{identifier}/domain-context")
    def read_context(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            row, _ = dossier(session, product, identifier, identity.user_id)
            return payload(row)

    @router.put("/dossiers/{identifier}/domain-context")
    def save_context(product: Product, identifier: str, data: ContextInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            row, profile = dossier(session, product, identifier, identity.user_id)
            require(session, row, profile, identity.user_id, "edit")
            pack = for_product(row.product)
            if data.schema_id != pack.context_schema_id:
                fail("Reload the dossier context before saving. Its schema does not match this dossier.", 409,
                     "domain_context_schema_unavailable")
            current = payload(row)  # Refuse to overwrite an unknown saved schema.
            values = validated(data.schema_id, data.values)
            signature = fingerprint({"expected_revision": data.expected_revision, "schema_id": data.schema_id,
                                     "values": values})
            key = "domain_context:" + str(data.request_key)
            previous = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                                                                 DossierEntry.request_key == key))
            if previous:
                if previous.actor_user_id != identity.user_id or previous.data_json.get("request_fingerprint") != signature:
                    fail("This context request was already used for another change.", 409, "product_revision_conflict")
                return current
            require_revision(row, data.expected_revision)
            if values == current["values"]:
                # Empty and unchanged forms are reads, not new subject history.
                # Keep authorization, replay-key and revision checks above this.
                return current
            before = row.domain_context_json or {}
            row.domain_context_json = {"domain": pack.domain, "pack_id": pack.id, "pack_version": pack.version,
                "schema_id": pack.context_schema_id, "values": values, "updated_at": iso(utcnow())}
            row.revision += 1
            audit(session, row, identity.user_id, "domain_context", "Dossier subject updated",
                  "User-provided subject details saved. Monitoring and source coverage are unchanged.",
                  {"request_fingerprint": signature, "revision": row.revision,
                   "before": before, "after": row.domain_context_json}, key)
            session.commit()
            return payload(row)
