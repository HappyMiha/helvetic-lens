"""Transactional storage for HL-089; never call an LLM inside a DB transaction.

This is an internal repository, not an admission or authorization API. A worker
must assemble ALL current admitted interests and revalidate that dossier before
prepare/finish. Durable scheduling, quotas and delivery are separate integrations.
Explicit tenant predicates also protect calls from privileged worker sessions.
"""

from uuid import uuid4

from sqlalchemy import select, update

from .config import DomainError
from .db import utcnow
from .interest_assessment import SYSTEM, BriefDraft, Dossier, finalize, fingerprint, manifest
from .models import InterestAssessmentBinding, InterestEventAssessment, RegulatoryEventState


class AssessmentStore:
    def __init__(self, organization_id: str):
        self.organization_id = organization_id

    def _scope(self, assessment_id):
        return (InterestEventAssessment.organization_id == self.organization_id,
                InterestEventAssessment.id == assessment_id)

    def prepare(self, session, dossier: Dossier, *, instructions: str = SYSTEM):
        if dossier.organization_id != self.organization_id:
            raise DomainError("The dossier does not belong to this organization.", 404, "not_found")
        # An event-admission row is the serialization point for concurrent
        # reservations. No-op UPDATE locks on PostgreSQL and SQLite alike, before
        # any read/upgrade race. It does not change topic generation or feed state.
        visible = session.execute(update(RegulatoryEventState).where(
            RegulatoryEventState.organization_id == self.organization_id,
            RegulatoryEventState.event_id == dossier.event.id,
        ).values(topic_match_generation=RegulatoryEventState.topic_match_generation))
        if visible.rowcount != 1:
            raise DomainError("The event is not in this organization's radar.", 404, "not_found")
        bindings = manifest(dossier, instructions)
        key = fingerprint(bindings)
        scope = (InterestEventAssessment.organization_id == self.organization_id,
                 InterestEventAssessment.event_id == dossier.event.id)
        existing = session.scalar(select(InterestEventAssessment).where(
            *scope, InterestEventAssessment.input_fingerprint == key))
        # A newly admitted input invalidates only unfinished work. Completed
        # results remain immutable history, reusable only by their exact key.
        session.execute(update(InterestEventAssessment).where(
            *scope, InterestEventAssessment.input_fingerprint != key,
            InterestEventAssessment.status.in_(["queued", "running"]),
        ).values(status="superseded", finished_at=utcnow(), attempt_key=None))
        if existing is not None:
            return existing, False
        record = InterestEventAssessment(organization_id=self.organization_id,
            event_id=dossier.event.id, input_fingerprint=key, input_manifest=bindings)
        session.add(record)
        session.flush()
        for row in bindings["interests"]:
            session.add(InterestAssessmentBinding(organization_id=self.organization_id,
                assessment_id=record.id, kind=row["kind"], reference_id=row["id"],
                revision=row["revision"], fingerprint=row["fingerprint"]))
        for row in bindings["evidence"]:
            session.add(InterestAssessmentBinding(organization_id=self.organization_id,
                assessment_id=record.id, kind="evidence", reference_id=row["id"],
                revision=row["version_id"], fingerprint=fingerprint(row)))
        session.flush()
        return record, True

    def claim(self, session, assessment_id: str, input_fingerprint: str) -> str | None:
        token = str(uuid4())
        changed = session.execute(update(InterestEventAssessment).where(
            *self._scope(assessment_id), InterestEventAssessment.status == "queued",
            InterestEventAssessment.input_fingerprint == input_fingerprint,
        ).values(status="running", attempt_key=token, started_at=utcnow(), finished_at=None,
                 attempts=InterestEventAssessment.attempts + 1, error_code=None))
        return token if changed.rowcount == 1 else None

    def finish(self, session, assessment_id: str, token: str, dossier: Dossier,
               result: dict, *, provider_calls: int, instructions: str = SYSTEM) -> bool:
        if dossier.organization_id != self.organization_id:
            return False
        if type(provider_calls) is not int or not 0 < provider_calls <= 2:
            raise ValueError("A brief must have one or two measured provider calls.")
        # Revalidate even internal callers; don't persist extra model keys, URLs,
        # official facts, fabricated references, or arbitrary provenance/secrets.
        draft = {key: result[key] for key in BriefDraft.model_fields}
        draft["why_in_radar"] = [
            {key: value for key, value in reason.items()
             if key not in {"interest_kind", "legal_relationship_status"}}
            for reason in draft["why_in_radar"]
        ]
        verified = finalize(draft, dossier)
        key = fingerprint(manifest(dossier, instructions))
        changed = session.execute(update(InterestEventAssessment).where(
            *self._scope(assessment_id), InterestEventAssessment.status == "running",
            InterestEventAssessment.attempt_key == token,
            InterestEventAssessment.input_fingerprint == key,
        ).values(status="succeeded", result=verified, finished_at=utcnow(), attempt_key=None,
                 provenance={"provider_calls": provider_calls, "provider_call_limit": 2}))
        return changed.rowcount == 1

    def fail(self, session, assessment_id: str, token: str, error_code: str) -> bool:
        # Raw provider errors may contain echoed credentials or prompts. Persist
        # a safe category; detailed redacted diagnostics belong to integration logs.
        allowed = {"invalid_citation", "invalid_model_output", "model_timeout", "model_budget_exhausted",
                   "interest_context_exceeded", "cloud_not_approved", "cancelled", "provider_unavailable"}
        safe_code = error_code if error_code in allowed else "provider_unavailable"
        changed = session.execute(update(InterestEventAssessment).where(
            *self._scope(assessment_id), InterestEventAssessment.status == "running",
            InterestEventAssessment.attempt_key == token,
        ).values(status="failed", error_code=safe_code, finished_at=utcnow(), attempt_key=None))
        return changed.rowcount == 1

    def retry(self, session, assessment_id: str, input_fingerprint: str) -> bool:
        """Explicit retry only; readers must never requeue a failed generation."""
        changed = session.execute(update(InterestEventAssessment).where(
            *self._scope(assessment_id), InterestEventAssessment.input_fingerprint == input_fingerprint,
            InterestEventAssessment.status == "failed", InterestEventAssessment.attempts < 3,
        ).values(status="queued", error_code=None, finished_at=None))
        return changed.rowcount == 1

    def get(self, session, assessment_id: str):
        return session.scalar(select(InterestEventAssessment).where(*self._scope(assessment_id)))

    def exact(self, session, event_id: str, input_fingerprint: str):
        return session.scalar(select(InterestEventAssessment).where(
            InterestEventAssessment.organization_id == self.organization_id,
            InterestEventAssessment.event_id == event_id,
            InterestEventAssessment.input_fingerprint == input_fingerprint))
