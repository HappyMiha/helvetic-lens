"""C02c1 internal draft rehearsal ledger; caller owns commit/rollback.

No route or worker calls this repository. Samples are unverified rehearsal input,
not admitted live evidence. Material IDs are candidates, never dispatch requests.
"""

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import DomainError
from .models import (
    MonitoringEvaluationEntry,
    MonitoringEvaluationStream,
    MonitoringSubject,
    MonitoringSubjectRevision,
    new_id,
)
from .monitoring_subjects import _actor, _owned, _savepoint
from .pollen_contracts import PollenConfiguration
from .pollen_numeric import NumericBinding, NumericState, evaluate_numeric
from .pollen_thresholds import PollenSample, _hash


def _authorize(session, user_id, binding, *, write=False):
    organization_id = _actor(session, user_id, write=write)
    if binding.organization_id != organization_id or binding.owner_id != user_id:
        raise DomainError("Evaluation not found.", 404, "evaluation_not_found")
    subject = _owned(session, organization_id, user_id, binding.subject_id)
    revision = session.scalar(select(MonitoringSubjectRevision).where(
        MonitoringSubjectRevision.subject_id == subject.id,
        MonitoringSubjectRevision.organization_id == organization_id,
        MonitoringSubjectRevision.revision == binding.configuration_revision,
    ))
    if revision is None:
        raise DomainError("Evaluation configuration not found.", 404, "evaluation_not_found")
    config = PollenConfiguration.model_validate(revision.configuration_json)
    matching = any(selection.allergen == binding.series.allergen and binding.rule in selection.rules
                   for selection in config.selections)
    if (subject.template_id != config.template_id or subject.template_version != config.template_version
            or config.station_id != binding.series.station_id or not matching):
        raise DomainError("Evaluation does not match the saved configuration.", 422, "evaluation_binding_invalid")
    return organization_id


def _stream(session, binding):
    return session.scalar(select(MonitoringEvaluationStream).where(
        MonitoringEvaluationStream.organization_id == binding.organization_id,
        MonitoringEvaluationStream.subject_id == binding.subject_id,
        MonitoringEvaluationStream.binding_hash == _hash(binding.model_dump()),
    ).execution_options(populate_existing=True))


def _entry_view(row):
    return {"id": row.id, "sequence": row.sequence, "evidence_kind": "draft_rehearsal",
            "request": deepcopy(row.request_json), "decision": deepcopy(row.decision_json), "material_id": row.material_id}


def _sequence(value, *, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise DomainError("Invalid evaluation sequence.", 422, "evaluation_sequence_invalid")


def evaluate_draft(
    session: Session, *, user_id: str, binding: NumericBinding, current: PollenSample,
    as_of: datetime, expected_sequence: int, request_key: str, baseline: PollenSample | None = None,
) -> dict:
    organization_id = _authorize(session, user_id, binding, write=True)
    _sequence(expected_sequence, zero=True)
    if (not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 120
            or any(ord(char) < 32 for char in request_key)):
        raise DomainError("A bounded evaluation request key is required.", 422, "evaluation_request_invalid")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DomainError("Evaluation time must be timezone aware.", 422, "evaluation_time_invalid")
    request_hash = _hash({"version": 1, "binding": binding.model_dump(), "current": current.model_dump(),
                          "baseline": baseline.model_dump() if baseline else None, "as_of": as_of,
                          "expected_sequence": expected_sequence})
    with _savepoint(session):
        # A conditional no-op UPDATE holds the subject write lock until the caller
        # commits. Concurrent revision/delete cannot slip between admission and append.
        locked = session.execute(update(MonitoringSubject).where(
            MonitoringSubject.id == binding.subject_id, MonitoringSubject.organization_id == organization_id,
            MonitoringSubject.owner_user_id == user_id, MonitoringSubject.status == "draft",
            MonitoringSubject.current_revision == binding.configuration_revision,
        ).values(current_revision=MonitoringSubject.current_revision).execution_options(synchronize_session=False))
        if locked.rowcount != 1:
            raise DomainError("Draft configuration changed or is no longer editable.", 409, "evaluation_configuration_conflict")
        # Recheck access after a possible wait for another transaction's lock.
        _actor(session, user_id, write=True)
        stream = _stream(session, binding)
        if stream:
            if NumericBinding.model_validate(stream.binding_json) != binding:
                raise DomainError("Stored evaluation binding is inconsistent.", 503, "evaluation_state_invalid")
            existing = session.scalar(select(MonitoringEvaluationEntry).where(
                MonitoringEvaluationEntry.organization_id == organization_id,
                MonitoringEvaluationEntry.stream_id == stream.id, MonitoringEvaluationEntry.request_key == request_key,
            ))
            if existing:
                if existing.request_hash != request_hash:
                    raise DomainError("This evaluation request key has different input.", 409, "evaluation_request_conflict")
                return _entry_view(existing)
        sequence = stream.sequence if stream else 0
        if expected_sequence != sequence:
            raise DomainError("Evaluation checkpoint changed; reload before retrying.", 409, "evaluation_sequence_conflict")
        prior = NumericState.model_validate(stream.state_json) if stream else None
        decision = evaluate_numeric(binding, current, as_of=as_of, baseline=baseline, prior=prior)
        state_json = decision.state.model_dump(mode="json")
        if stream:
            changed = session.execute(update(MonitoringEvaluationStream).where(
                MonitoringEvaluationStream.id == stream.id, MonitoringEvaluationStream.organization_id == organization_id,
                MonitoringEvaluationStream.sequence == expected_sequence,
            ).values(sequence=sequence + 1, state_json=state_json).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise DomainError("Evaluation checkpoint changed.", 409, "evaluation_sequence_conflict")
        else:
            stream = MonitoringEvaluationStream(id=new_id(), organization_id=organization_id,
                subject_id=binding.subject_id, configuration_revision=binding.configuration_revision,
                binding_hash=_hash(binding.model_dump()), binding_json=binding.model_dump(mode="json"),
                sequence=1, state_json=state_json)
            session.add(stream)
            session.flush()
        entry = MonitoringEvaluationEntry(id=new_id(), organization_id=organization_id, stream_id=stream.id,
            sequence=sequence + 1, request_key=request_key, request_hash=request_hash,
            request_json={"version": 1, "evidence_kind": "draft_rehearsal", "binding": binding.model_dump(mode="json"),
                          "current": current.model_dump(mode="json"), "baseline": baseline.model_dump(mode="json") if baseline else None,
                          "as_of": as_of.astimezone(UTC).isoformat(), "expected_sequence": expected_sequence},
            decision_json=decision.model_dump(mode="json"), material_id=decision.material_id)
        session.add(entry)
        session.flush()
        return _entry_view(entry)


def get_checkpoint(session: Session, *, user_id: str, binding: NumericBinding) -> dict:
    _authorize(session, user_id, binding)
    stream = _stream(session, binding)
    return {"sequence": stream.sequence if stream else 0, "evidence_kind": "draft_rehearsal",
            "state": deepcopy(stream.state_json) if stream else None}


def evaluation_history(session: Session, *, user_id: str, binding: NumericBinding,
                       limit: int = 50, before_sequence: int | None = None) -> dict:
    _authorize(session, user_id, binding)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("History limit must be between 1 and 100.", 422, "evaluation_limit_invalid")
    if before_sequence is not None:
        _sequence(before_sequence)
    stream = _stream(session, binding)
    if stream is None:
        return {"items": [], "next_before_sequence": None}
    statement = select(MonitoringEvaluationEntry).where(
        MonitoringEvaluationEntry.organization_id == binding.organization_id,
        MonitoringEvaluationEntry.stream_id == stream.id,
    )
    if before_sequence is not None:
        statement = statement.where(MonitoringEvaluationEntry.sequence < before_sequence)
    rows = list(session.scalars(statement.order_by(MonitoringEvaluationEntry.sequence.desc()).limit(limit + 1)))
    return {"items": [_entry_view(row) for row in rows[:limit]],
            "next_before_sequence": rows[limit - 1].sequence if len(rows) > limit else None}
