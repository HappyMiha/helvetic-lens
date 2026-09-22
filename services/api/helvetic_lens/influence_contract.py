"""Bounded, explicit evidence claims. URLs are retained, never fetched here."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$")]
Short = Annotated[str, Field(min_length=1, max_length=240)]
Paragraph = Annotated[str, Field(min_length=1, max_length=2000)]
Status = Literal["documented", "reported", "disputed", "not_established"]
Kind = Literal[
    "family", "role", "campaign", "ownership", "business", "policy_proposal", "potential_impact", "dividend"
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Source(Input):
    id: Identifier
    title: Short
    publisher: Short
    url: str = Field(min_length=8, max_length=3000)
    kind: Literal["primary_corporate", "primary_government", "primary_campaign", "reporting"]
    language: Literal["en", "de", "fr", "it", "rm", "uk"]
    publishedOn: date | None
    checkedOn: date
    snapshotText: str | None = Field(default=None, max_length=16000)

    @field_validator("url")
    @classmethod
    def https_url(cls, value):
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not any(ord(c) < 32 for c in value)
            ):
                return value
        except ValueError:
            pass
        raise ValueError("Use an HTTPS source URL without credentials.")

    @model_validator(mode="after")
    def chronological(self):
        if self.checkedOn > datetime.now(UTC).date() or (
            self.publishedOn and self.publishedOn > self.checkedOn
        ):
            raise ValueError("A source cannot be checked before publication or in the future.")
        return self


class Entity(Input):
    id: Identifier
    name: Short
    kind: Literal["person", "company", "initiative", "policy", "group"]
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    x: float = Field(ge=0, le=12000)
    y: float = Field(ge=0, le=12000)


class Evidence(Input):
    sourceId: Identifier
    locator: Short
    summary: Paragraph
    quote: str | None = Field(default=None, min_length=1, max_length=1000)


class Money(Input):
    amount: float = Field(gt=0, le=1e16)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    periodStart: date
    periodEnd: date
    basis: Literal["paid", "proposed"]
    evidenceSourceId: Identifier

    @model_validator(mode="after")
    def period(self):
        if self.periodEnd < self.periodStart:
            raise ValueError("Payment period is reversed.")
        return self


class Edge(Input):
    id: Identifier
    from_: Identifier = Field(alias="from")
    to: Identifier
    kind: Kind
    status: Status
    label: Short
    statement: Paragraph
    asOf: date | None
    supporting: list[Evidence] = Field(min_length=1, max_length=12)
    disputing: list[Evidence] = Field(default_factory=list, max_length=12)
    limits: list[Paragraph] = Field(min_length=1, max_length=12)
    money: Money | None = None


class Document(Input):
    id: Identifier
    title: Short
    checkedOn: date
    summaryLanguage: Literal["en", "de", "fr", "it", "rm", "uk"]
    sources: list[Source] = Field(max_length=100)
    entities: list[Entity] = Field(max_length=100)
    edges: list[Edge] = Field(max_length=250)
    gaps: list[Paragraph] = Field(max_length=30)

    @model_validator(mode="after")
    def evidence_integrity(self):
        if self.checkedOn > datetime.now(UTC).date():
            raise ValueError("The dossier review date cannot be in the future.")
        for records in (self.sources, self.entities, self.edges):
            if len({item.id for item in records}) != len(records):
                raise ValueError("IDs must be unique within each record type.")
        sources = {item.id: item for item in self.sources}
        entities = {item.id for item in self.entities}
        for source in self.sources:
            if source.checkedOn > self.checkedOn:
                raise ValueError("A source review cannot follow the dossier review date.")
        for edge in self.edges:
            if edge.from_ not in entities or edge.to not in entities or edge.from_ == edge.to:
                raise ValueError("A relationship must connect two different saved entities.")
            if edge.asOf and edge.asOf > self.checkedOn:
                raise ValueError("Relationship date is after dossier review.")
            for ref in edge.supporting + edge.disputing:
                if ref.sourceId not in sources:
                    raise ValueError("A relationship refers to a missing source.")
                if ref.quote and ref.quote not in (sources[ref.sourceId].snapshotText or ""):
                    raise ValueError("An exact quote must occur in the retained source extract.")
            primary = [
                sources[ref.sourceId] for ref in edge.supporting if sources[ref.sourceId].kind != "reporting"
            ]
            if edge.status == "documented" and (not primary or edge.disputing):
                raise ValueError(
                    "Documented claims require primary evidence and no unresolved counter-statement."
                )
            if edge.status == "disputed" and not edge.disputing:
                raise ValueError("Disputed claims need a counter-statement.")
            if edge.kind == "potential_impact" and edge.status == "documented":
                raise ValueError("Potential effects cannot be presented as documented outcomes.")
            if edge.money:
                money = edge.money
                source = sources.get(money.evidenceSourceId)
                if (
                    edge.kind != "dividend"
                    or not source
                    or money.evidenceSourceId not in {ref.sourceId for ref in edge.supporting}
                ):
                    raise ValueError("Money needs an explicit payment relation and its supporting source.")
                if money.periodEnd > source.checkedOn and money.basis == "paid":
                    raise ValueError("A future payment cannot be marked paid.")
                if edge.status == "documented" and (money.basis != "paid" or source.kind == "reporting"):
                    raise ValueError("Documented money must be paid and supported by a primary source.")
        if len(canonical(self.model_dump(mode="json", by_alias=True)).encode()) > 600000:
            raise ValueError("Dossier exceeds the 600 KB storage limit.")
        return self


class Save(Input):
    document: Document
    note: str = Field(min_length=3, max_length=2000)
    requestId: UUID
    expectedRevision: int = Field(default=0, strict=True, ge=0)


class Review(Input):
    expectedRevision: int = Field(strict=True, ge=1)
    requestId: UUID
    decision: Literal["reviewed", "needs_revision"]
    note: str = Field(min_length=3, max_length=2000)


class Archive(Input):
    expectedRevision: int = Field(strict=True, ge=1)
    requestId: UUID
    archived: bool = Field(strict=True)
    note: str = Field(min_length=3, max_length=2000)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
