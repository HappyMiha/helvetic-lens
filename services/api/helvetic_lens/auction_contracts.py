"""B8 domain contract. Native source adapters and permissions remain separate."""

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["real_estate", "vehicles", "equipment", "furniture", "bicycles", "jewellery", "precious_metals", "other"]
PriceKind = Literal["current_bid", "starting_price", "minimum_price", "estimate"]
Status = Literal["announced", "open", "closed", "cancelled", "postponed", "unknown"]
Money = Annotated[int, Field(strict=True, ge=0, le=10**15)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
CANTONS = frozenset("AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split())
RULE_VERSION = "auction-rules-v1"
NORMALIZATION_VERSION = "nfkc-casefold-words-v1:" + unicodedata.unidata_version


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def visible(value):
    if not value.strip() or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} and c not in "\n\r\t" for c in value):
        raise ValueError("Use nonempty visible text")
    return value


def words(value):
    return tuple(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def phrase_in(phrase, value):
    wanted, supplied = words(phrase), words(value)
    return bool(wanted) and any(supplied[i:i + len(wanted)] == wanted for i in range(len(supplied) - len(wanted) + 1))


def clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An explicit timestamp offset is required")
    return value.astimezone(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Notifications(Contract):
    new_match: bool = Field(default=True, strict=True)
    price_above_limit: bool = Field(default=True, strict=True)
    every_bid_change: bool = Field(default=False, strict=True)
    deadline_change: bool = Field(default=True, strict=True)
    documents_change: bool = Field(default=True, strict=True)
    conditions_change: bool = Field(default=True, strict=True)
    cancellation: bool = Field(default=True, strict=True)
    ending_soon_hours: int | None = Field(default=None, strict=True, ge=1, le=720)


class AuctionProfile(Contract):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    categories: tuple[Category, ...] = Field(min_length=1, max_length=8)
    cantons: tuple[str, ...] = Field(default=("TI",), min_length=1, max_length=26)
    locations: tuple[str, ...] = Field(default=(), max_length=30)
    keywords: tuple[str, ...] = Field(default=(), max_length=30)
    brands: tuple[str, ...] = Field(default=(), max_length=30)
    maximum_price_chf_cents: Money | None = None
    budget_price_kind: PriceKind = "current_bid"
    notify: Notifications = Field(default_factory=Notifications)

    @model_validator(mode="after")
    def consistent(self):
        visible(self.name)
        if not set(self.cantons).issubset(CANTONS):
            raise ValueError("Select an official Swiss canton code")
        for values in (self.categories, self.cantons, self.locations, self.keywords, self.brands):
            if len({words(v) for v in values}) != len(values):
                raise ValueError("Selections must be distinct")
        for value in (*self.locations, *self.keywords, *self.brands):
            visible(value)
            if len(value) > 160 or not words(value):
                raise ValueError("Use a bounded word or phrase")
        return self

    def fingerprint(self):
        return fingerprint(self.model_dump(mode="json"))


class Price(Contract):
    kind: PriceKind
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount_minor: Money
    # A normalized field always names where the adapter obtained it.
    locator: str = Field(min_length=1, max_length=500)


class Document(Contract):
    official_id: str = Field(min_length=1, max_length=200)
    sha256: Sha256 | None = None
    # No temporary download token is an identity or a retained source link.
    title: str = Field(min_length=1, max_length=500)


class Documents(Contract):
    state: Literal["complete", "partial", "unavailable"]
    items: tuple[Document, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def consistent(self):
        if len({d.official_id for d in self.items}) != len(self.items):
            raise ValueError("Document identifiers must be distinct")
        if self.state == "unavailable" and self.items:
            raise ValueError("An unavailable observation cannot assert document contents")
        return self


class AuctionFacts(Contract):
    schema_version: Literal[1] = 1
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    canton: str
    auction_id: str = Field(min_length=1, max_length=200)
    lot_id: str | None = Field(default=None, min_length=1, max_length=200)
    authority: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=100000)
    category: Category | None = None
    asset_location: str | None = Field(default=None, max_length=1000)
    brand: str | None = Field(default=None, max_length=300)
    prices: tuple[Price, ...] = Field(default=(), max_length=4)
    bid_count: int | None = Field(default=None, strict=True, ge=0, le=10**9)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: Status = "unknown"
    documents: Documents = Field(default_factory=lambda: Documents(state="unavailable"))
    conditions_sha256: Sha256 | None = None
    source_url: str = Field(min_length=1, max_length=2000)
    raw_sha256: Sha256
    observed_at: datetime

    @field_validator("observed_at", "starts_at", "ends_at")
    @classmethod
    def timestamps(cls, value):
        return clock(value) if value is not None else None

    @field_validator("source_url")
    @classmethod
    def source_link(cls, value):
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.fragment or parts.query or parts.port not in (None, 443)
                or any(ord(c) < 33 or c == "\\" for c in value)):
            raise ValueError("Use a permanent HTTPS source URL without credentials or query tokens")
        return value

    @model_validator(mode="after")
    def consistent(self):
        if self.canton not in CANTONS:
            raise ValueError("Unknown Swiss canton")
        for value in (self.auction_id, self.authority, self.title):
            visible(value)
        for value in (self.lot_id, self.asset_location, self.brand):
            if value is not None:
                visible(value)
        if len({p.kind for p in self.prices}) != len(self.prices):
            raise ValueError("Each price type must be unambiguous")
        if self.bid_count == 0 and any(p.kind == "current_bid" for p in self.prices):
            raise ValueError("Zero bids cannot establish a current bid")
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValueError("Auction end must follow its start")
        return self

    def identity(self):
        return fingerprint([self.source_key, self.canton, self.auction_id, self.lot_id])

    def state_hash(self):
        value = self.model_dump(mode="json", exclude={"observed_at", "source_url", "raw_sha256"})
        value["prices"] = sorted(value["prices"], key=lambda p: p["kind"])
        # Locator-only rendering changes remain evidence changes, not price changes.
        for price in value["prices"]:
            price.pop("locator")
        value["documents"]["items"].sort(key=lambda d: d["official_id"])
        return fingerprint(value)

    def price(self, kind):
        return next((p for p in self.prices if p.kind == kind), None)
