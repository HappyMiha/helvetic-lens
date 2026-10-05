"""Author-private topic proposals on the existing interactive job/outbox lane."""
import asyncio
from copy import deepcopy
from datetime import UTC, timedelta
from uuid import uuid4

from sqlalchemy import select

from . import domain_packs, jobs, legal_profiles, monitoring_topics
from .config import DomainError
from .db import utcnow
from .interest_jobs import lock_organization
from .legal_profile_models import LegalMonitoringProfile
from .models import Job
from .product_access import organization_member, require
from .product_models import ProductDossier
from .product_operations import fingerprint

TYPE = "profile_topic_suggestions"
TARGET = "profile_suggestions"
BUSY = {"model_rate_limited", "model_busy", "model_provider_busy"}


def owned(session, profile_id, user_id, *, write=False):
    row = session.get(LegalMonitoringProfile, profile_id)
    if not row:
        raise DomainError("Monitoring profile not found.", 404, "not_found")
    membership = organization_member(session, user_id, row.organization_id)
    if not membership:
        raise DomainError("Monitoring profile not found.", 404, "not_found")
    parent = session.scalar(select(ProductDossier).where(ProductDossier.profile_id == row.id))
    if parent:
        require(session, parent, row, user_id, action="configure" if write else "read")
    else:
        if row.created_by_user_id != user_id:
            raise DomainError("Monitoring profile not found.", 404, "not_found")
        if write and membership.role != "organization_admin":
            raise DomainError("A workspace administrator must edit this profile.", 403, "dossier_access_required")
    return row


def _query(profile, user_id):
    return select(Job).where(Job.organization_id == profile.organization_id, Job.type == TYPE,
        Job.target_id == profile.id, Job.payload["actor_id"].as_string() == user_id)


def _binding(profile, request, pack):
    return fingerprint({"config": profile.config_json, "revision": request["expected_revision"],
        "feedback": request["feedback"], "locale": request["locale"], "pack": pack.descriptor()})


def project(session, row, job):
    if job is None:
        return {"request": None}
    data = job.payload
    result = job.result_json if job.state == "succeeded" else None
    revision = result["profile"]["revision"] if result else data["expected_revision"]
    stale = row.status != "draft" or row.revision != revision or job.error_code == "topic_inputs_changed"
    status = ("superseded" if stale else "waiting" if job.error_code in BUSY and job.state not in {*jobs.TERMINAL_STATES, "running"} else
        {"succeeded": "completed", "running": "running", "failed": "failed", "cancelled": "cancelled"}.get(job.state, "queued"))
    message = ("The draft changed. Request fresh suggestions when ready." if stale else
        "Waiting for the configured model to become available. Your request is saved." if status == "waiting" else
        "Suggestions could not be completed. Your draft is unchanged; you can request them again or add topics manually."
        if status == "failed" else None)
    return {"request": {"id": job.id, "request_key": data["request_key"], "status": status,
        "expected_revision": data["expected_revision"], "created_at": job.created_at,
        "updated_at": job.updated_at, "error": message, "result": result if status == "completed" else None}}


def latest(session, profile_id, user_id):
    row = owned(session, profile_id, user_id)
    job = session.scalar(_query(row, user_id).order_by(Job.created_at.desc(), Job.id.desc()).limit(1))
    return project(session, row, job)


def enqueue(service, session, profile_id, identity, data):
    lock_organization(session, service.organization_id)
    row = owned(session, profile_id, identity.user_id, write=True)
    request = data.model_dump(mode="json")
    key = "profile-suggest:" + fingerprint([identity.user_id, profile_id, str(data.request_key)])
    previous = session.scalar(select(Job).where(Job.idempotency_key == key))
    if previous:
        if any(previous.payload.get(name) != value for name, value in request.items()):
            raise DomainError("This request key belongs to different suggestions.", 409, "suggestion_request_conflict")
        return project(session, row, previous)
    if row.status != "draft" or row.revision != data.expected_revision:
        raise DomainError("Reload the current draft before requesting suggestions.", 409, "legal_profile_conflict")
    if not row.config_json["goal"]:
        raise DomainError("Describe what you want to monitor first.", 422, "legal_profile_invalid")
    pack = domain_packs.for_profile(session, row)
    binding = _binding(row, request, pack)
    pending = list(session.scalars(_query(row, identity.user_id).where(Job.state.not_in(jobs.TERMINAL_STATES))))
    for other in pending:
        if other.payload.get("input_fingerprint") == binding:
            return project(session, row, other)
    for other in pending:
        jobs.cancel(session, other.id)
    job, _ = jobs.enqueue(session, job_type=TYPE, target_type=TARGET, target_id=row.id,
        queue="ai_interactive", priority=9, idempotency_key=key, max_attempts=service.settings.job_max_attempts,
        payload={**request, "actor_id": identity.user_id, "input_fingerprint": binding,
                 "pack": pack.descriptor()}, steps=[("Suggest monitoring topics", {})])
    session.commit()
    return project(session, row, job)


def _lease(job):
    return job.lease_owner, job.leased_at.replace(tzinfo=UTC) if job.leased_at else None, job.attempts


def _current(session, service, job_id, lease):
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (not job or job.state != "running" or job.cancel_requested or _lease(job) != lease
            or not job.heartbeat_at or (utcnow() - job.heartbeat_at.replace(tzinfo=UTC)).total_seconds()
            >= service.settings.job_lease_seconds):
        raise jobs.JobCancelled()
    return job


def _inputs(session, job):
    data = job.payload
    row = owned(session, job.target_id, data["actor_id"], write=True)
    pack = domain_packs.for_profile(session, row)
    if (row.status != "draft" or row.revision != data["expected_revision"]
            or _binding(row, data, pack) != data["input_fingerprint"]):
        raise DomainError("The draft changed before suggestions completed.", 409, "topic_inputs_changed")
    return row, pack


async def execute(service, job_id, worker):
    with service.write_guard, service.db.session() as session:
        lock_organization(session, service.organization_id)
        job = session.get(Job, job_id)
        if not job or job.type != TYPE:
            raise DomainError("Suggestion request not found.", 404, "not_found")
        if job.available_at.replace(tzinfo=UTC) > utcnow():
            return {"id": job.id, "state": job.state}
        job = jobs.claim(session, job_id, worker)
        if not job:
            session.commit()
            return {"id": job_id, "state": "not_claimed"}
        lease = _lease(job)
        session.commit()
    try:
        with service.db.session() as session:
            job = _current(session, service, job_id, lease)
            row, pack = _inputs(session, job)
            config, data = deepcopy(row.config_json), deepcopy(job.payload)
            context = monitoring_topics.draft_context(session)
            seconds = min(95, service.settings.job_lease_seconds - 5 -
                (utcnow() - job.heartbeat_at.replace(tzinfo=UTC)).total_seconds())
        async with asyncio.timeout(max(0, seconds)):
            result = await legal_profiles.suggest_topics(service.model_client, config, context,
                legal_profiles.SuggestInput(**{key: data[key] for key in ("expected_revision", "feedback", "locale")}), pack=pack)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            job = _current(session, service, job_id, lease)
            row, pack = _inputs(session, job)
            cards = [legal_profiles.TopicCard(id=uuid4(), **item.model_dump()).model_dump(mode="json") for item in result.topics]
            provenance = {card["id"]: {"provider": service.settings.apertus_provider,
                "model": service.settings.apertus_model, "prompt_revision": service.prompt_revision,
                "domain_pack": pack.descriptor()} for card in cards}
            row.proposals_json = {**{key: value for key, value in row.proposals_json.items()
                if key in {card["id"] for card in config["topics"]}}, **provenance}
            row.config_json = {**config, "feedback": data["feedback"]}
            row.revision, row.updated_at = row.revision + 1, utcnow()
            jobs.complete(session, job.id, result_type=TARGET, result_id=row.id, result_json={
                "profile": legal_profiles.payload(session, row), "suggestions": cards,
                "provider": service.settings.apertus_provider, "model": service.settings.apertus_model})
            session.commit()
            return {"id": job.id, "state": job.state}
    except jobs.JobCancelled:
        return {"id": job_id, "state": "not_owned"}
    except (DomainError, TimeoutError) as error:
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            try:
                job = _current(session, service, job_id, lease)
            except jobs.JobCancelled:
                return {"id": job_id, "state": "not_owned"}
            code = error.code if isinstance(error, DomainError) else "model_timeout"
            if code in BUSY:
                jobs.defer_until(session, job, utcnow() + timedelta(seconds=30), code=code,
                    detail="Waiting for the configured model; the suggestion request is retained.")
            elif code in {"topic_inputs_changed", "not_found", "dossier_access_required"}:
                jobs.cancel(session, job.id)
                job.error_code = "topic_inputs_changed"
            else:
                jobs.fail(session, job.id, code=code, detail="Topic suggestions could not be completed.", retry_delay=30)
            session.commit()
            return {"id": job.id, "state": job.state}
