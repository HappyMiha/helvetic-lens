"""Internal measured local brief admission/execution; no public or cloud route.

One observed runtime and reviewed task/locale scope, one complete measured
request, at most two generation HTTP attempts. All inference is outside DB
transactions. ``schedule`` binds durable work; matching policy and reader/delivery
integration remain separate from this internal execution boundary.
"""

import asyncio
import json
import time

from sqlalchemy import select

from .analysis import InferenceBudget, ModelClient
from .config import DomainError
from .corpus_access import visible
from .interest_admission import current_key
from .interest_assessment import (
    MAX_PROVIDER_CALLS,
    MAX_SECONDS,
    BriefDraft,
    ModelIdentity,
    fingerprint,
    generate,
    input_envelope,
)
from .interest_assessment_store import AssessmentStore
from .interest_prompts import current_instructions
from .models import RegulatoryEvent, RegulatoryEventState, RegulatoryWork
from .relation_analysis import configuration_fingerprint


def _identity(client, runtime, decision):
    if (runtime is None or runtime.identity_fingerprint() is None
            or runtime.prompt_budget_schema is None):
        raise DomainError("A verified local model with token measurement is required for event briefs.",
                          503, "model_runtime_unavailable")
    if decision.mode != "generated_explanation" or decision.budget is None:
        raise DomainError("This local profile has no independent interest-brief approval for this language. Saved source evidence remains available.",
                          409, "interest_capability_unavailable")
    return ModelIdentity(provider="docker", model=runtime.served_model_id,
        runtime_fingerprint=runtime.cache_identity()["fingerprint"],
        configuration_fingerprint=fingerprint({"configuration": configuration_fingerprint(client.settings),
                                             "capability": decision.fingerprint}))


def _saved(record, *, cached=False):
    return {"id": record.id, "event_id": record.event_id, "status": record.status,
            "cached": cached, "result": record.result, "error_code": record.error_code,
            "provenance": record.provenance}


class LocalBriefRunner:
    def __init__(self, db, organization_id: str, client: ModelClient):
        self.db, self.organization_id, self.client = db, organization_id, client
        self.store = AssessmentStore(organization_id)

    async def schedule(self, event_id: str, *, locale="en", guard=None):
        """Measured admission only; persist a job/outbox without generating text."""
        return await self._run(event_id, locale=locale, schedule_only=True, guard=guard)

    async def run(self, event_id: str, *, locale="en", instructions=None,
                  expected=None, guard=None):
        return await self._run(event_id, locale=locale, instructions=instructions,
                               expected=expected, guard=guard)

    async def _run(self, event_id: str, *, locale="en", instructions=None,
                   expected=None, guard=None, schedule_only=False):
        # Construct one runner per job. Keep mutable execution state inside this
        # call, so concurrent callers cannot exchange assessment IDs or tokens.
        if locale not in {"de", "fr", "it", "rm", "en"}:
            raise DomainError("Unsupported event brief language.", 422, "invalid_locale")
        if self.client.settings.apertus_provider != "docker":
            raise DomainError("This worker uses the local model only; cloud fallback is not enabled.",
                              409, "cloud_not_approved")
        budget = InferenceBudget(MAX_PROVIDER_CALLS, max_seconds=MAX_SECONDS)
        started = time.monotonic()
        assessment_id = attempt_token = None
        saved_prompt = instructions is None
        with self.db.organization_context(self.organization_id), self.client.runtime_scope():
            # Authorize before contacting the runtime, even in privileged tasks.
            with self.db.session() as session:
                if guard:
                    guard(session)
                allowed = session.scalar(select(RegulatoryEvent.id)
                    .join(RegulatoryEventState, RegulatoryEventState.event_id == RegulatoryEvent.id)
                    .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
                    .where(RegulatoryEvent.id == event_id, RegulatoryEventState.organization_id == self.organization_id,
                           visible(RegulatoryWork, self.organization_id)))
                if allowed is None:
                    raise DomainError("The event is not admitted to this organization.", 404, "not_found")
                if saved_prompt:
                    instructions = current_instructions(session, self.organization_id)
            trace_token = self.client.begin_trace(priority="background")
            trace = []
            try:
                async with asyncio.timeout(MAX_SECONDS):
                    runtime = await self.client.bound_runtime(budget)
                    with self.client.capability_scope("interest_brief", f"{locale}-CH") as decision:
                        identity = _identity(self.client, runtime, decision)
                        with self.db.session() as session:
                            if guard:
                                guard(session)
                            if saved_prompt and current_instructions(session, self.organization_id) != instructions:
                                raise DomainError("The saved brief prompt changed; retry with current instructions.",
                                                  409, "interest_inputs_changed")
                            dossier, input_key = current_key(session, self.organization_id, event_id,
                                model=identity, locale=locale, instructions=instructions)
                            if expected and input_key != expected[1]:
                                raise DomainError("Queued brief inputs changed; a new admission is required.",
                                                  409, "interest_inputs_changed")
                            existing = self.store.exact(session, event_id, input_key)
                            if expected and (existing is None or existing.id != expected[0]):
                                raise DomainError("The queued assessment is no longer available.", 409, "interest_inputs_changed")
                            if existing and existing.status != "queued":
                                # No token-count or generation calls on exact reuse,
                                # concurrent running work, failure or supersession.
                                return _saved(existing, cached=existing.status == "succeeded")
                        system, payload, _ = input_envelope(dossier,
                            context_char_limit=self.client.settings.apertus_context_chars, instructions=instructions)
                        measured = await self.client.count_prompt(system,
                            json.dumps({"task": "interest_event_brief", **payload}, ensure_ascii=False),
                            response_schema=BriefDraft.model_json_schema(), budget=budget)
                        if not self.client.evidence_fits(measured):
                            raise DomainError("The complete event brief does not fit the measured, reviewed model budget; no evidence was dropped.",
                                              422, "capability_budget_exceeded")
                        self.client.check_capability()
                        with self.db.session() as session:
                            if schedule_only:
                                from .interest_jobs import lock_organization
                                lock_organization(session, self.organization_id)
                            if guard:
                                guard(session)
                            if saved_prompt and current_instructions(session, self.organization_id) != instructions:
                                raise DomainError("The saved brief prompt changed; retry with current instructions.",
                                                  409, "interest_inputs_changed")
                            record, _, current = self.store.prepare_current(session, event_id, model=identity,
                                locale=locale, instructions=instructions,
                                context_char_limit=self.client.settings.apertus_context_chars)
                            if record.input_fingerprint != input_key:
                                raise DomainError("The event inputs changed during token measurement; retry with current evidence.",
                                                  409, "interest_inputs_changed")
                            if schedule_only:
                                from .interest_jobs import enqueue
                                result = enqueue(session, self.organization_id, record, locale)
                                session.commit()
                                return result
                            assessment_id = record.id
                            attempt_token = self.store.claim(session, record.id, input_key)
                            if not attempt_token:
                                return _saved(record, cached=record.status == "succeeded")
                            session.commit()
                        result, usage = await generate(self.client, current,
                            context_char_limit=self.client.settings.apertus_context_chars,
                            instructions=instructions, budget=budget)
                        # Re-observe after generation rather than treating a cached
                        # execution pin as evidence the currently serving model is unchanged.
                        with self.client.runtime_scope():
                            fresh_runtime = await self.client.bound_runtime(budget)
                            with self.client.capability_scope("interest_brief", f"{locale}-CH") as fresh_decision:
                                fresh_identity = _identity(self.client, fresh_runtime, fresh_decision)
                        trace = self.client.end_trace(trace_token)
                        trace_token = None
                        execution = {
                            "runtime_fingerprint": identity.runtime_fingerprint,
                            "capability_fingerprint": decision.fingerprint,
                            "admission_measurement": measured.model_dump(mode="json"),
                            "generation_measurements": [row["prompt_token_measurement"] for row in trace
                                                        if row.get("prompt_token_measurement")],
                            "duration_ms": round((time.monotonic() - started) * 1000), "max_seconds": MAX_SECONDS,
                        }
                        with self.db.session() as session:
                            if guard:
                                guard(session)
                            publication_instructions = (current_instructions(session, self.organization_id)
                                                        if saved_prompt else instructions)
                            self.store.finish_current(session, assessment_id, attempt_token, current, result,
                                model=fresh_identity, provider_calls=usage["provider_calls"],
                                instructions=publication_instructions, execution=execution)
                            session.commit()
                            return _saved(self.store.get(session, assessment_id))
            except (Exception, asyncio.CancelledError) as error:
                if assessment_id and attempt_token:
                    code = ("cancelled" if isinstance(error, asyncio.CancelledError) else
                            "model_timeout" if isinstance(error, TimeoutError) else
                            error.code if isinstance(error, DomainError) else "provider_unavailable")
                    with self.db.session() as session:
                        self.store.fail(session, assessment_id, attempt_token, code)
                        session.commit()
                if isinstance(error, TimeoutError):
                    raise DomainError("The local brief exceeded its total time budget; saved evidence remains available.",
                                      504, "model_timeout") from error
                raise
            finally:
                if trace_token is not None:
                    self.client.end_trace(trace_token)
