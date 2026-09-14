"""Internal reviewed calibration registry; no customer grant/configuration endpoint."""

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .monitoring_subjects import _savepoint
from .trademark_contracts import MATCHER_VERSION, NORMALIZATION_VERSION, SimilarityCalibration, fingerprint
from .trademark_repository import _fail
from .trademark_sources import _clock
from .trademark_workflow_models import TrademarkCalibration, TrademarkCalibrationSelection


def retain(session, configuration):
    value = SimilarityCalibration.model_validate(configuration)
    identifier = value.fingerprint()
    row = session.get(TrademarkCalibration, identifier)
    if row is None:
        session.add(TrademarkCalibration(id=identifier, configuration=value.model_dump(mode="json")))
        session.flush()
    return identifier


def read(session, identifier, *, now, historical=False):
    now = _clock(now)
    query = select(TrademarkCalibration).where(TrademarkCalibration.id == identifier)
    row = session.scalar((query if historical else query.with_for_update()).execution_options(populate_existing=True))
    if row is None or row.revoked_at is not None:
        _fail("trademark_calibration_unavailable")
    try:
        value = SimilarityCalibration.model_validate(row.configuration)
    except ValidationError:
        _fail("trademark_calibration_invalid", 503)
    if value.fingerprint() != row.id:
        _fail("trademark_calibration_invalid", 503)
    if not historical and (not value.reviewed_at <= now < value.valid_until
            or value.matcher_version != MATCHER_VERSION or value.normalization_version != NORMALIZATION_VERSION):
        _fail("trademark_calibration_unavailable")
    return value


def select_current(session, identifier, *, expected_id, now):
    value = read(session, identifier, now=now)
    try:
        with _savepoint(session):
            row = session.scalar(select(TrademarkCalibrationSelection).where(TrademarkCalibrationSelection.language == value.language)
                .with_for_update().execution_options(populate_existing=True))
            if (row.calibration_id if row else None) != expected_id:
                _fail("trademark_calibration_conflict")
            if row:
                row.calibration_id = identifier
            else:
                session.add(TrademarkCalibrationSelection(language=value.language, calibration_id=identifier))
            session.flush()
    except IntegrityError:
        _fail("trademark_calibration_conflict")


def current(session, portfolio, *, now):
    """Load in language order before source locks; missing calibration is explicit."""
    from .config import DomainError
    languages = sorted({b.language for b in portfolio.brands if b.similar_names})
    values, missing = [], []
    for language in languages:
        selected = session.get(TrademarkCalibrationSelection, language, populate_existing=True)
        if selected is None:
            missing.append(language)
            continue
        identifier = selected.calibration_id
        try:
            value = read(session, identifier, now=now)
            selected = session.scalar(select(TrademarkCalibrationSelection).where(TrademarkCalibrationSelection.language == language)
                .with_for_update().execution_options(populate_existing=True))
            if selected is None or selected.calibration_id != identifier or value.language != language:
                _fail("trademark_calibration_conflict")
            values.append(value)
        except DomainError:
            missing.append(language)
    return values, missing


def evaluation_hash(portfolio, facts, result, identifiers):
    return fingerprint({"profile": portfolio.fingerprint(), "facts": facts.material_fingerprint(),
        "matcher": MATCHER_VERSION, "normalization": NORMALIZATION_VERSION, "result": result, "calibrations": identifiers})


def revoke(session, identifier, *, now):
    row = session.scalar(select(TrademarkCalibration).where(TrademarkCalibration.id == identifier).with_for_update())
    if row is None:
        _fail("trademark_calibration_unavailable")
    row.revoked_at = row.revoked_at or _clock(now)
    session.flush()
