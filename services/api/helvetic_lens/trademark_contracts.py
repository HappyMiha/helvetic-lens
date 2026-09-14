"""B7 internal portfolio/facts contracts, not an IPI wire schema or licence."""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from .trademark_deadline_contracts import DeadlinePreference

Language = Literal["de", "fr", "it", "rm", "en"]
NiceClass = Annotated[int, Field(strict=True, ge=1, le=45)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
NORMALIZATION_VERSION = "unicode-nfkc-casefold-whitespace-v1:" + unicodedata.unidata_version
MATCHER_VERSION = "trademark-candidates-v1"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def exact(value):
    """Keep punctuation/accents/scripts; originals remain in the contract."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def words(value):
    return tuple(re.findall(r"[^\W_]+(?:[+#]+)?", exact(value)))


def valid_text(value):
    if not value.strip() or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} and c not in "\n\r\t" for c in value):
        raise ValueError("Use non-empty visible text without control characters")
    return value


def distinct(values, *, normalized=False):
    keys = [exact(v) for v in values] if normalized else values
    if len(keys) != len(set(keys)):
        raise ValueError("Selections must be distinct")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Phrase(Contract):
    language: Language
    text: str = Field(min_length=1, max_length=200)

    @field_validator("text")
    @classmethod
    def meaningful(cls, value):
        valid_text(value)
        if not words(value):
            raise ValueError("Use a phrase with words")
        return value


class GoodsInterest(Contract):
    name: str = Field(min_length=1, max_length=100)
    phrases: tuple[Phrase, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def consistent(self):
        valid_text(self.name)
        distinct([(p.language, words(p.text)) for p in self.phrases])
        return self


class Brand(Contract):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    name: str = Field(min_length=1, max_length=256)
    language: Language
    exact_name: bool = Field(default=True, strict=True)
    similar_names: bool = Field(default=True, strict=True)
    word_variants: tuple[str, ...] = Field(default=(), max_length=8)
    owners_of_interest: tuple[str, ...] = Field(default=(), max_length=8)
    relevant_classes: tuple[NiceClass, ...] = Field(default=(), max_length=45)
    goods_services: tuple[GoodsInterest, ...] = Field(default=(), max_length=12)

    @model_validator(mode="after")
    def consistent(self):
        valid_text(self.name)
        if not words(self.name) or not (self.exact_name or self.similar_names or self.owners_of_interest):
            raise ValueError("Select at least one name or owner interest")
        distinct(self.relevant_classes)
        distinct([self.name, *self.word_variants], normalized=True)
        distinct(self.owners_of_interest, normalized=True)
        distinct([g.name for g in self.goods_services], normalized=True)
        for value in (*self.word_variants, *self.owners_of_interest):
            if len(value) > 256 or not words(valid_text(value)):
                raise ValueError("Use bounded visible names")
        return self


class TrademarkPortfolio(Contract):
    template_id: Literal["trademark-watch"] = "trademark-watch"
    template_version: Literal[1] = 1
    jurisdiction: Literal["CH"] = "CH"
    name: str = Field(min_length=1, max_length=100)
    brands: tuple[Brand, ...] = Field(min_length=1, max_length=20)
    deadline_context: DeadlinePreference | None = None

    @model_serializer(mode="wrap")
    def optional_deadline(self, handler):
        result = handler(self)
        if self.deadline_context is None:
            result.pop("deadline_context", None)
        return result

    @model_validator(mode="after")
    def consistent(self):
        valid_text(self.name)
        distinct([b.key for b in self.brands])
        distinct([(exact(b.name), b.language) for b in self.brands])
        return self

    def fingerprint(self):
        return fingerprint(self.model_dump(mode="json"))


class GoodsStatement(Contract):
    # Original language and text, never machine-inferred class or translation.
    language: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")
    text: str = Field(min_length=1, max_length=20000)
    class_number: NiceClass | None = None

    @field_validator("text")
    @classmethod
    def meaningful(cls, value):
        return valid_text(value)


class TrademarkPublication(Contract):
    identifier: str = Field(min_length=1, max_length=100)
    office_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    publication_date: date | None = None
    action_date: date | None = None
    category: str | None = Field(default=None, min_length=1, max_length=300)
    change_descriptions: tuple[str, ...] = Field(default=(), max_length=20)
    change_texts: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def original_text(self):
        for value in (self.identifier, self.category, *self.change_descriptions, *self.change_texts):
            if value is not None:
                if len(value) > 5000:
                    raise ValueError("Publication text exceeds the bounded field size")
                valid_text(value)
        return self


class TrademarkFacts(Contract):
    """Internal normalization target; the native XML adapter must supply evidence."""
    official_id: str = Field(min_length=1, max_length=100)
    origin: Literal["national_ch", "international_designating_ch"]
    source_url: str = Field(min_length=1, max_length=2048)
    source_sha256: Sha256
    source_document_sha256: Sha256 | None = None
    mark: str | None = Field(default=None, min_length=1, max_length=256)
    mark_type: str | None = Field(default=None, min_length=1, max_length=100)
    owners: tuple[str, ...] | None = Field(default=None, max_length=100)
    representatives: tuple[str, ...] | None = Field(default=None, max_length=100)
    classes: tuple[NiceClass, ...] | None = Field(default=None, max_length=45)
    goods_services: tuple[GoodsStatement, ...] | None = Field(default=None, max_length=135)
    application_date: date | None = None
    publication_date: date | None = None
    registration_date: date | None = None
    renewal_date: date | None = None
    expiry_date: date | None = None
    cancellation_date: date | None = None
    application_numbers: tuple[str, ...] = Field(default=(), max_length=10)
    registration_numbers: tuple[str, ...] = Field(default=(), max_length=10)
    publications: tuple[TrademarkPublication, ...] | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def retained_facts(self):
        valid_text(self.official_id)
        url = urlsplit(self.source_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError("Use a source evidence HTTPS URL without credentials")
        for value in (self.mark, self.mark_type, self.status):
            if value is not None:
                valid_text(value)
        for group in (self.owners, self.representatives):
            if group is not None:
                for value in group:
                    if len(value) > 1000:
                        raise ValueError("Party name is too long")
                    valid_text(value)
        for group in (self.application_numbers, self.registration_numbers):
            distinct(group)
            for value in group:
                if len(value) > 100:
                    raise ValueError("Official number is too long")
                valid_text(value)
        if sum(len(v) for p in self.publications or () for v in (*p.change_descriptions, *p.change_texts)) > 200000:
            raise ValueError("Publication history exceeds the bounded record size")
        if self.classes is not None:
            distinct(self.classes)
        if sum(len(g.text) for g in self.goods_services or ()) > 100000:
            raise ValueError("Goods/services evidence exceeds the bounded record size")
        return self

    def material_fingerprint(self):
        # Retrieval URL/hash changes alone do not reopen a review. Each evidence
        # revision is still preserved by the later source journal.
        return fingerprint(self.model_dump(mode="json", exclude={"source_sha256", "source_url", "source_document_sha256"}))


class SimilarityCalibration(Contract):
    """Internal reviewed configuration, never accepted from a portfolio request."""
    version: str = Field(min_length=1, max_length=100)
    matcher_version: Literal["trademark-candidates-v1"] = MATCHER_VERSION
    normalization_version: str = Field(min_length=1, max_length=100)
    language: Language
    lexical_minimum: int = Field(strict=True, ge=1, le=100)
    word_extension_minimum: int | None = Field(default=None, strict=True, ge=1, le=100)
    phonetic_method: Literal["disabled", "soundex-en-v1"] = "disabled"
    phonetic_lexical_floor: int = Field(default=60, strict=True, ge=1, le=100)
    training_sha256: Sha256
    validation_sha256: Sha256
    review_reference: str = Field(min_length=1, max_length=1000)
    reviewed_at: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def reviewed(self):
        valid_text(self.version)
        valid_text(self.review_reference)
        if self.training_sha256 == self.validation_sha256:
            raise ValueError("Training and validation must be separate")
        if any(v.tzinfo is None or v.utcoffset() is None for v in (self.reviewed_at, self.valid_until)):
            raise ValueError("Calibration timestamps need explicit timezone")
        if self.reviewed_at >= self.valid_until:
            raise ValueError("Calibration must have a valid review interval")
        if self.phonetic_method != "disabled" and self.language != "en":
            raise ValueError("This pronunciation method is scoped to reviewed English names")
        return self

    def fingerprint(self):
        return fingerprint(self.model_dump(mode="json"))
