"""Official-channel contracts and strict byte decoding for Pollen Watch.

No browser-supplied source admission and no dated-fixture fallback. An operator
must explicitly approve a versioned channel after the source review. Discovery,
download success and a numeric value never grant that approval themselves.
"""

import csv
import hashlib
import io
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from .pollen_categories import CategoryScale
from .pollen_contracts import ContractModel, PollenAllergen, PollenConfiguration, PollenPeriod
from .pollen_thresholds import PollenSample, PollenSeries, Sha256, _hash

ATTRIBUTION = "Source: MeteoSwiss"
TERMS = "https://opendatadocs.meteoswiss.ch/general/terms-of-use"
OBSERVATION_SOURCE = "meteoswiss:ogd-pollen"
HOURLY_METHOD = "meteoswiss-automatic-hourly-v1"
PARSER_VERSION = "meteoswiss-pollen-csv-v1"
HOURLY_PARAMETERS = {
    "alder": "kaalnuh0", "birch": "kabetuh0", "hazel": "kacoryh0",
    "beech": "kafaguh0", "ash": "kafraxh0", "oak": "kaquerh0", "grasses": "khpoach0",
}
FORECAST_VARIABLES = {
    "alder": "ALNUsnc", "birch": "BETUsnc", "hazel": "CORYsnc",
    "grasses": "POACsnc", "ragweed": "AMBRsnc",
}


def channel_hash(*, source_id, method_version, station_id, allergen, period):
    return _hash({"source_id": source_id, "method_version": method_version,
                  "station_id": station_id, "allergen": allergen, "period": period})


def sample_channel_hash(series: PollenSeries):
    return channel_hash(**series.model_dump(exclude={"forecast", "unit"}))


class ChannelApproval(ContractModel):
    """Deployment-owned source decision, tied to a retained review hash."""

    version: str = Field(min_length=1, max_length=128)
    review_sha256: Sha256
    source_id: str = Field(min_length=1, max_length=128)
    method_version: str = Field(min_length=1, max_length=128)
    period: PollenPeriod
    stations: tuple[str, ...] = Field(min_length=1, max_length=100)
    allergens: tuple[PollenAllergen, ...] = Field(min_length=1, max_length=8)
    status: Literal["approved", "unverified", "revoked"] = "unverified"
    valid_from: datetime
    valid_until: datetime
    freshness_seconds: int = Field(strict=True, ge=60, le=172800)
    poll_seconds: int = Field(strict=True, ge=1200, le=86400)
    retention_days: int = Field(strict=True, ge=1, le=365)
    raw_export_allowed: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        for value in (self.valid_from, self.valid_until):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("Source approval dates must be explicit UTC")
        if self.valid_until <= self.valid_from:
            raise ValueError("Source approval expiry must follow its start")
        if len(set(self.stations)) != len(self.stations) or any(
            not re.fullmatch(r"[A-Z]{3}", station) for station in self.stations
        ) or len(set(self.allergens)) != len(self.allergens):
            raise ValueError("Source scope must contain unique supported identifiers")
        return self

    def admits(self, series: PollenSeries, at: datetime) -> bool:
        return self.status == "approved" and self.covers(series, at)

    def covers(self, series: PollenSeries, at: datetime) -> bool:
        return bool(self.valid_from <= at < self.valid_until
                    and series.source_id == self.source_id and series.method_version == self.method_version
                    and series.period == self.period and series.station_id in self.stations
                    and series.allergen in self.allergens)


class PollenSourcePolicy(ContractModel):
    channels: tuple[ChannelApproval, ...] = Field(default=(), max_length=32)
    category_scales: tuple[CategoryScale, ...] = Field(default=(), max_length=128)

    def category_scale(self, series):
        matches = [scale for scale in self.category_scales if scale.matches(series)]
        return matches[0] if len(matches) == 1 and matches[0].status == "approved" else None

    def approval(self, series: PollenSeries, at: datetime) -> ChannelApproval | None:
        # Ambiguous overlapping approvals are not silently resolved by list order.
        matches = [channel for channel in self.channels if channel.covers(series, at)]
        return matches[0] if len(matches) == 1 and matches[0].status == "approved" else None

    def coverage(self, configuration: PollenConfiguration, at: datetime) -> list[dict]:
        coverage = []
        for selection in configuration.selections:
            periods = {rule.period for rule in selection.rules} | {PollenPeriod.OBSERVATION_HOURLY,
                                                                    PollenPeriod.FORECAST_INSTANT}
            for period in sorted(periods):
                matches = [c for c in self.channels if c.period == period
                           and c.valid_from <= at < c.valid_until and configuration.station_id in c.stations
                           and selection.allergen in c.allergens]
                accepted = len(matches) == 1 and matches[0].status == "approved"
                coverage.append({"allergen": selection.allergen, "period": period,
                                 "status": "approved" if accepted else "unverified",
                                 "policy_version": matches[0].version if accepted else None,
                                 "required_by_rule": any(r.period == period for r in selection.rules)})
        return coverage


class DecodedObservation(ContractModel):
    series: PollenSeries
    valid_at: datetime
    value: Decimal | None
    artifact_hash: Sha256
    row_hash: Sha256

    def sample(self, *, revision: int, fetched_at: datetime, approval: ChannelApproval) -> PollenSample:
        if not approval.admits(self.series, fetched_at):
            raise ValueError("Observation is outside the approved channel")
        return PollenSample(series=self.series, valid_at=self.valid_at, source_revision=revision,
                            value=self.value, quality="missing" if self.value is None else "usable",
                            rights="approved", policy_version=approval.version, parser_version=PARSER_VERSION,
                            artifact_hashes=(self.artifact_hash,), fetched_at=fetched_at,
                            fresh_until=self.valid_at + timedelta(seconds=approval.freshness_seconds))


def decode_hourly(body: bytes, *, station_id: str, fetched_at: datetime) -> list[DecodedObservation]:
    """Decode one bounded official station h_now CSV. Blank is missing, never zero.

    Whole artifacts fail closed on malformed/duplicate rows or unexpected station
    identity; partial parsing must not silently manufacture current availability.
    Hash both artifact and canonical source row, so unchanged rows in an updated
    artifact do not become corrections. Input order has no chronological meaning.
    """
    if not re.fullmatch(r"[A-Z]{3}", station_id):
        raise ValueError("Invalid station identifier")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() != timedelta(0):
        raise ValueError("Fetch time must be explicit UTC")
    if not body or len(body) > 4 * 1024 * 1024:
        raise ValueError("Hourly artifact size is outside the accepted bound")
    reader = csv.DictReader(io.StringIO(body.decode("cp1252", errors="strict")), delimiter=";")
    required = {"station_abbr", "reference_timestamp", *HOURLY_PARAMETERS.values()}
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or not required.issubset(reader.fieldnames):
        raise ValueError("Unexpected hourly CSV columns")
    artifact_hash = hashlib.sha256(body).hexdigest()
    result, seen = [], set()
    for row_number, row in enumerate(reader, 1):
        if row_number > 2000 or None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed or oversized hourly series")
        if row["station_abbr"] != station_id:
            raise ValueError("Station identity differs from the requested channel")
        when = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
        if when.minute or when > fetched_at or when in seen:
            raise ValueError("Ambiguous, non-hourly or future observation instant")
        seen.add(when)
        for allergen, parameter in HOURLY_PARAMETERS.items():
            raw = row[parameter]
            if raw and not re.fullmatch(r"[0-9]{1,12}(\.[0-9]{1,12})?", raw):
                raise ValueError("Unrecognized concentration or missing marker")
            value = Decimal(raw) if raw else None
            series = PollenSeries(source_id=OBSERVATION_SOURCE, method_version=HOURLY_METHOD,
                                  station_id=station_id, allergen=allergen, period="observation_hourly")
            digest = hashlib.sha256(f"{station_id}|{parameter}|{when.isoformat()}|{raw}".encode()).hexdigest()
            result.append(DecodedObservation(series=series, valid_at=when, value=value,
                                             artifact_hash=artifact_hash, row_hash=digest))
    if not result:
        raise ValueError("Hourly artifact contains no observations")
    return sorted(result, key=lambda item: (item.valid_at, item.series.allergen))


def decode_daily(body: bytes, *, station_id: str, fetched_at: datetime, period: PollenPeriod) -> list[DecodedObservation]:
    """Official d0/d1 daily means, keyed by completed UTC interval end.

    Metadata explicitly maps d0 to 06–06 following day and d1 to 00–00.
    Pre-2023 manual readings require a different reviewed method/adapter.
    """
    if period not in {PollenPeriod.OBSERVATION_DAILY_00, PollenPeriod.OBSERVATION_DAILY_06}:
        raise ValueError("Unknown daily aggregation period")
    if not re.fullmatch(r"[A-Z]{3}", station_id) or not body or len(body) > 4 * 1024 * 1024:
        raise ValueError("Invalid daily station or artifact bound")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() != timedelta(0):
        raise ValueError("Fetch time must be explicit UTC")
    suffix = "d0" if period == PollenPeriod.OBSERVATION_DAILY_06 else "d1"
    parameters = {allergen: parameter[:-2] + suffix for allergen, parameter in HOURLY_PARAMETERS.items()}
    reader = csv.DictReader(io.StringIO(body.decode("cp1252", errors="strict")), delimiter=";")
    required = {"station_abbr", "reference_timestamp", *parameters.values()}
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required.issubset(reader.fieldnames):
        raise ValueError("Unexpected daily CSV columns")
    digest, seen, result = hashlib.sha256(body).hexdigest(), set(), []
    for number, row in enumerate(reader, 1):
        if number > 800 or None in row or any(value is None for value in row.values()) or row["station_abbr"] != station_id:
            raise ValueError("Malformed daily observation series")
        reference = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
        if reference.year < 2023 or reference.hour or reference.minute or reference in seen:
            raise ValueError("Unexpected daily reference date or historical method")
        seen.add(reference)
        end = reference + timedelta(hours=30 if suffix == "d0" else 24)
        if end > fetched_at:
            continue  # An incomplete daily interval cannot be a completed mean.
        for allergen, parameter in parameters.items():
            raw = row[parameter]
            if raw and not re.fullmatch(r"[0-9]{1,12}(\.[0-9]{1,12})?", raw):
                raise ValueError("Unrecognized daily concentration or missing marker")
            series = PollenSeries(source_id=OBSERVATION_SOURCE, method_version="meteoswiss-automatic-daily-v1",
                                  station_id=station_id, allergen=allergen, period=period)
            result.append(DecodedObservation(series=series, valid_at=end, value=Decimal(raw) if raw else None,
                artifact_hash=digest, row_hash=hashlib.sha256(f"{station_id}|{parameter}|{reference.isoformat()}|{raw}".encode()).hexdigest()))
    if not result:
        raise ValueError("Daily artifact contains no completed observations")
    return sorted(result, key=lambda item: (item.valid_at, item.series.allergen))
