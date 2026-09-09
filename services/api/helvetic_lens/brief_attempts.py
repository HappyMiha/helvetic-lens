"""Fenced, append-only attempt identity and strictly whitelisted telemetry."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from .config import DomainError
from .db import utcnow
from .models import InterestAssessmentAttempt as Attempt
from .models import InterestEventAssessment as Assessment
from .runtime_binding import PromptTokenMeasurement
from .topic_matching import _iso


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["brief-attempt-usage-v1"] = "brief-attempt-usage-v1"
    http_attempts_started: int = Field(ge=0, le=2)
    elapsed_run_ms: int = Field(ge=0)
    measured_input_requests: int = Field(ge=0, le=2)
    measured_input_tokens: int | None = Field(default=None, ge=0)
    reported_output_requests: int = Field(ge=0, le=2)
    reported_output_tokens: int | None = Field(default=None, ge=0)
    observed_queue_requests: int = Field(ge=0, le=2)
    observed_queue_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def consistent_samples(self):
        for count, total in [(self.measured_input_requests, self.measured_input_tokens),
                             (self.reported_output_requests, self.reported_output_tokens),
                             (self.observed_queue_requests, self.observed_queue_ms)]:
            if count > self.http_attempts_started or (count == 0) != (total is None):
                raise ValueError("Usage totals must match their observed request coverage")
        return self


def summarize(trace, calls, elapsed_ms):
    inputs, outputs, queue = [], [], []
    for row in trace:
        if not isinstance(row, dict):
            continue
        if row.get("prompt_token_measurement"):
            try:
                inputs.append(PromptTokenMeasurement.model_validate(row["prompt_token_measurement"], strict=True).input_tokens)
            except (ValueError, TypeError):
                pass
        if row.get("outcome") == "success":
            usage = row.get("usage")
            output = usage.get("completion_tokens") if isinstance(usage, dict) else None
            if type(output) is int and output >= 0:
                outputs.append(output)
            wait = row.get("queue_wait_ms")
            if row.get("queue_wait_observed") is True and type(wait) in {int, float} and math.isfinite(wait) and wait >= 0:
                queue.append(float(wait))
    # Invalid/duplicated trace samples do not turn into seemingly complete totals.
    if len(inputs)>calls:
        inputs=[]
    if len(outputs)>calls:
        outputs=[]
    if len(queue)>calls:
        queue=[]
    return Measurement(http_attempts_started=calls, elapsed_run_ms=elapsed_ms,
        measured_input_requests=len(inputs), measured_input_tokens=sum(inputs) if inputs else None,
        reported_output_requests=len(outputs), reported_output_tokens=sum(outputs) if outputs else None,
        observed_queue_requests=len(queue), observed_queue_ms=sum(queue) if queue else None).model_dump(mode="json")


def begin(session, organization, assessment_id, token):
    row = session.execute(select(Assessment.attempts, Assessment.started_at).where(
        Assessment.id == assessment_id, Assessment.organization_id == organization,
        Assessment.attempt_key == token, Assessment.status == "running")).one()
    session.add(Attempt(id=token, organization_id=organization, assessment_id=assessment_id,
                        number=row.attempts, status="running", started_at=row.started_at))
    session.flush()


def close(session, organization, assessment_id, token, status, error_code=None):
    session.execute(update(Attempt).where(Attempt.organization_id == organization,
        Attempt.assessment_id == assessment_id, Attempt.id == token, Attempt.status == "running")
        .values(status=status, error_code=error_code, finished_at=utcnow()))


def record(session, organization, assessment_id, token, values):
    verified = Measurement.model_validate(values, strict=True).model_dump(mode="json")
    changed = session.execute(update(Attempt).where(Attempt.organization_id == organization,
        Attempt.assessment_id == assessment_id, Attempt.id == token, Attempt.measurement.is_(None))
        .values(measurement=verified))
    return changed.rowcount == 1


def read(session, organization, assessment_id):
    if session.scalar(select(Assessment.id).where(Assessment.organization_id == organization, Assessment.id == assessment_id)) is None:
        raise DomainError("This assessment is unavailable.", 404, "not_found")
    rows = session.scalars(select(Attempt).where(Attempt.organization_id == organization,
        Attempt.assessment_id == assessment_id).order_by(Attempt.number.desc()).limit(50))
    items=[]
    for row in rows:
        try:
            usage=Measurement.model_validate(row.measurement, strict=True).model_dump(mode="json")
        except (ValueError, TypeError):
            usage=None
        items.append({"number": row.number, "status": row.status,
            "started_at": _iso(row.started_at), "finished_at": _iso(row.finished_at),
            "error_code": row.error_code, "measurement": usage})
    return {"assessment_id": assessment_id, "items": items, "ai_calls": 0,
            "legacy_attempts_not_backfilled": True}
