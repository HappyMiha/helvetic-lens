"""Private live lifecycle and evidence. API/worker callers own transactions.

Reads only the official collector ledger. Rehearsal evaluation rows never enter
this module. Source policy, ownership and rollout are checked on every operation.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from . import jobs
from .config import DomainError
from .models import Job, MonitoringSubject, MonitoringSubjectRevision, OrganizationMembership, User, new_id
from .monitoring_contracts import ReaderMode
from .monitoring_live_models import (
    MonitoringCommand,
    MonitoringDelivery,
    MonitoringLiveEntry,
    MonitoringLiveStream,
    MonitoringReview,
    MonitoringRuntime,
    MonitoringSourceSample,
)
from .monitoring_subjects import _actor, _owned, _savepoint, _view
from .pollen_categories import evaluate_category
from .pollen_contracts import PollenConfiguration
from .pollen_numeric import NumericBinding, NumericState, evaluate_numeric
from .pollen_sources import ATTRIBUTION, TERMS, channel_hash
from .pollen_thresholds import PollenSample, _hash, _source_order


def _now(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Runtime clock must be timezone aware")
    return value.astimezone(UTC)


def _iso(value):
    # SQLite drops the offset on DateTime(timezone=True); persisted clocks are UTC.
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _mode(settings, organization_id):
    return settings.monitoring_rollout.reader_mode(workspace_id=organization_id,
        template_id="pollen-watch", template_version=1, implementation_ready=True, source_ready=True)


def _require_live(settings, organization_id):
    if settings.deployment_instance != "monitoring-v2" or _mode(settings, organization_id) != ReaderMode.ENABLED:
        raise DomainError("Live monitoring is not enabled for this workspace.", 409, "monitoring_live_not_enabled")


def _configuration(session, subject):
    return PollenConfiguration.model_validate(_view(session, subject)["configuration"])


def _coverage(settings, configuration, now):
    coverage = settings.pollen_source_policy.coverage(configuration, now)
    if settings.app_environment == "test":
        return coverage  # Explicit isolated contract fixtures; never a browser setting.
    implementations = {("meteoswiss:ogd-pollen", "meteoswiss-automatic-hourly-v1", "observation_hourly"),
        ("meteoswiss:ogd-pollen", "meteoswiss-automatic-daily-v1", "observation_daily_00_24_utc"),
        ("meteoswiss:ogd-pollen", "meteoswiss-automatic-daily-v1", "observation_daily_06_06_utc")}
    if settings.pollen_decoder_url:
        implementations.add(("meteoswiss:icon-ch2", "icon-ch2-control-nearest-lowest-layer-v1", "forecast_instant"))
    for row in coverage:
        if row["status"] == "approved" and not any((c.source_id, c.method_version, c.period) in implementations
            and c.version == row["policy_version"] and c.period == row["period"] and c.status == "approved"
            and configuration.station_id in c.stations and row["allergen"] in c.allergens and c.valid_from <= now < c.valid_until
            for c in settings.pollen_source_policy.channels):
            row["status"] = "unverified"
            row["policy_version"] = None
    return coverage


def _gate(settings, configuration, now):
    coverage = _coverage(settings, configuration, now)
    for selection in configuration.selections:
        channels = [c for c in coverage if c["allergen"] == selection.allergen]
        if (not any(c["status"] == "approved" for c in channels)
                or any(c["required_by_rule"] and c["status"] != "approved" for c in channels)):
            raise DomainError("Official source acceptance is pending for these settings.", 409, "pollen_source_not_ready")
        for rule in selection.rules:
            if rule.category_change:
                matching = [scale for scale in settings.pollen_source_policy.category_scales
                    if scale.allergen == selection.allergen and scale.period == rule.period
                    and any(c.source_id == scale.source_id and c.method_version == scale.method_version
                            and c.period == scale.period and c.status == "approved" and c.valid_from <= now < c.valid_until
                            and configuration.station_id in c.stations and selection.allergen in c.allergens
                            for c in settings.pollen_source_policy.channels)]
                if len(matching) != 1 or matching[0].status != "approved":
                    raise DomainError("A matching approved category scale is required.", 409, "pollen_category_not_ready")
    return coverage


def _runtime_view(runtime):
    if runtime is None:
        return {"version": 0, "run_id": None, "health": "not_started", "email_consent": False, "muted": False}
    return {"version": runtime.version, "run_id": runtime.run_id, "health": runtime.health,
            "email_consent": runtime.email_consent, "muted": runtime.muted,
            "configuration_revision": runtime.configuration_revision,
            "started_at": _iso(runtime.started_at),
            "last_poll_at": _iso(runtime.last_poll_at) if runtime.last_poll_at else None}


def preview(session, *, settings, user_id, configuration, now):
    organization_id = _actor(session, user_id, write=True)
    now = _now(now)
    from .monitoring_subjects import _configuration as validate
    payload, digest = validate(configuration)
    config = PollenConfiguration.model_validate(payload)
    coverage = _coverage(settings, config, now)
    reasons = []
    try:
        _require_live(settings, organization_id)
        _gate(settings, config, now)
    except DomainError as error:
        reasons.append(error.code)
    return {"configuration": payload, "configuration_hash": digest, "preview_kind": "source_coverage",
            "coverage": coverage, "start_available": not reasons, "blocking_reasons": reasons,
            "attribution": ATTRIBUTION, "terms": TERMS}


def _locked_subject(session, user_id, subject_id):
    organization_id = _actor(session, user_id, write=True)
    subject = _owned(session, organization_id, user_id, subject_id)
    # A committed membership/active-user withdrawal must win before any private
    # mutation or SMTP send; hold these rows through the caller's transaction.
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    session.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id).with_for_update())
    # An UPDATE also serializes SQLite writers; SELECT FOR UPDATE alone does not.
    session.execute(update(MonitoringSubject).where(MonitoringSubject.id == subject_id,
        MonitoringSubject.organization_id == organization_id, MonitoringSubject.owner_user_id == user_id,
    ).values(updated_at=MonitoringSubject.updated_at).execution_options(synchronize_session=False))
    session.refresh(subject)  # Another writer may have changed state while this lock waited.
    session.get(MonitoringRuntime, subject_id, populate_existing=True)
    _actor(session, user_id, write=True)
    return subject


def command(session, *, settings, user_id, subject_id, action, expected_revision,
            expected_version, request_key, now, email_consent=False):
    now = _now(now)
    if (not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 120
            or any(ord(c) < 32 for c in request_key)):
        raise DomainError("A bounded command key is required.", 422, "subject_request_key_invalid")
    if action not in {"start", "pause", "resume", "archive", "mute", "unmute", "unsubscribe", "consent_email"}:
        raise DomainError("Unknown monitoring command.", 422, "monitoring_command_invalid")
    if type(expected_revision) is not int or expected_revision < 1 or type(expected_version) is not int or expected_version < 0:
        raise DomainError("Valid configuration and runtime revisions are required.", 422, "subject_revision_invalid")
    if type(email_consent) is not bool or (email_consent and action not in {"start", "resume", "consent_email"}):
        raise DomainError("Explicit delivery consent is required.", 422, "monitoring_consent_invalid")
    payload_hash = _hash({"action": action, "revision": expected_revision, "version": expected_version,
                          "email_consent": email_consent})
    with _savepoint(session):
        subject = _locked_subject(session, user_id, subject_id)
        previous = session.scalar(select(MonitoringCommand).where(
            MonitoringCommand.subject_id == subject_id, MonitoringCommand.organization_id == subject.organization_id,
            MonitoringCommand.request_key == request_key))
        if previous:
            if previous.request_hash != payload_hash:
                raise DomainError("Command key was used for another operation.", 409, "subject_request_conflict")
            return deepcopy(previous.result_json)
        runtime = session.get(MonitoringRuntime, subject_id)
        if subject.current_revision != expected_revision or (runtime.version if runtime else 0) != expected_version:
            raise DomainError("Monitoring changed; review its current state.", 409, "monitoring_version_conflict")
        config = _configuration(session, subject)
        if action in {"start", "resume"}:
            if subject.status != ("draft" if action == "start" else "paused"):
                raise DomainError("Monitoring cannot start from this state.", 409, "monitoring_state_conflict")
            _require_live(settings, subject.organization_id)
            _gate(settings, config, now)
            if email_consent and config.delivery.email == "off":
                raise DomainError("Choose an email schedule before consenting.", 409, "monitoring_consent_invalid")
            if runtime is None:
                runtime = MonitoringRuntime(subject_id=subject.id, organization_id=subject.organization_id)
                session.add(runtime)
            runtime.version = expected_version + 1
            runtime.run_id, runtime.configuration_revision = new_id(), subject.current_revision
            runtime.started_at, runtime.next_poll_at, runtime.health = now, now, "waiting"
            runtime.email_consent, runtime.muted = email_consent, False
            subject.status = "active"
            session.flush()
            refresh_from_cache(session, settings=settings, user_id=user_id, subject_id=subject.id,
                               run_id=runtime.run_id, now=now, locked=True)
            jobs.enqueue(session, job_type="pollen_refresh", target_type="monitoring_subject", target_id=subject.id,
                         queue="ingest", idempotency_key=f"pollen-initial:{runtime.run_id}",
                         payload={"run_id": runtime.run_id}, max_attempts=3)
        else:
            if runtime is None or subject.status == "draft":
                raise DomainError("Monitoring has not started.", 409, "monitoring_state_conflict")
            if action == "pause":
                if subject.status != "active":
                    raise DomainError("Only active monitoring can pause.", 409, "monitoring_state_conflict")
                subject.status = "paused"
            elif action == "archive":
                subject.status = "archived"
            elif action == "consent_email":
                if subject.status != "active" or not email_consent or config.delivery.email == "off":
                    raise DomainError("Active monitoring and explicit email consent are required.", 409, "monitoring_consent_invalid")
                _require_live(settings, subject.organization_id)
                _gate(settings, config, now)
                runtime.email_consent = True
            elif action == "unsubscribe":
                runtime.email_consent = False
            elif action in {"mute", "unmute"}:
                runtime.muted = action == "mute"
            runtime.version += 1
            if action in {"pause", "archive", "unsubscribe"}:
                runtime.email_consent = False
            # No command grants consent for already queued detections. All queued
            # deliveries carry the old consent version and will be suppressed.
        subject.updated_at = now
        session.flush()
        result = {**_view(session, subject), "runtime": _runtime_view(runtime)}
        session.add(MonitoringCommand(organization_id=subject.organization_id, subject_id=subject.id,
                    request_key=request_key, request_hash=payload_hash, result_json=result))
        session.flush()
        return deepcopy(result)


def _samples(session, settings, configuration, now):
    """Bounded latest revisions for the configured station; no private source key."""
    selected = {s.allergen for s in configuration.selections}
    channels = {channel_hash(source_id=c.source_id, method_version=c.method_version,
                station_id=configuration.station_id, allergen=allergen, period=c.period)
                for c in settings.pollen_source_policy.channels
                if c.status == "approved" and c.valid_from <= now < c.valid_until and configuration.station_id in c.stations
                for allergen in selected if allergen in c.allergens}
    rows = []
    for key in sorted(channels):
        rows.extend(session.scalars(select(MonitoringSourceSample).where(MonitoringSourceSample.channel_hash == key)
            .where(MonitoringSourceSample.retention_until > now)
            .order_by(MonitoringSourceSample.valid_at.desc(), MonitoringSourceSample.revision.desc()).limit(2000)))
    result, seen = [], set()
    for row in rows:
        sample = PollenSample.model_validate(row.sample_json)
        if sample.fetched_at > now or sample.series.station_id != configuration.station_id or sample.series.allergen not in selected:
            continue
        key = (_hash(sample.series.model_dump()), sample.valid_at)
        if key in seen:
            continue
        seen.add(key)
        approval = settings.pollen_source_policy.approval(sample.series, now)
        if approval is None:
            continue
        # Policy renewal is visible to evaluation, but never rewrites source bytes.
        freshness_origin = sample.series.forecast.issue_at if sample.series.forecast else sample.valid_at
        sample = sample.model_copy(update={"rights": "approved", "policy_version": approval.version,
            "fresh_until": freshness_origin + timedelta(seconds=approval.freshness_seconds)})
        result.append(sample)
    return result


def _evidence(entry):
    return {"id": entry.id, "sequence": entry.sequence, "kind": entry.kind,
            "evidence_kind": "official_source", "material_id": entry.material_id,
            "created_at": _iso(entry.created_at), **deepcopy(entry.evidence_json)}


def refresh_from_cache(session, *, settings, user_id, subject_id, run_id, now, locked=False):
    now = _now(now)
    subject = _locked_subject(session, user_id, subject_id) if not locked else _owned(
        session, _actor(session, user_id, write=True), user_id, subject_id)
    runtime = session.get(MonitoringRuntime, subject_id)
    _require_live(settings, subject.organization_id)
    if not runtime or runtime.run_id != run_id or subject.status != "active":
        return {"status": "inactive"}
    config = _configuration(session, subject)
    if runtime.configuration_revision != subject.current_revision:
        return {"status": "configuration_changed"}
    rebaseline = runtime.health in {"source_not_approved", "access_or_source_unavailable", "source_unavailable"}
    try:
        _gate(settings, config, now)
    except DomainError:
        runtime.health = "source_not_approved"
        runtime.last_poll_at = now
        return {"status": runtime.health}
    samples = _samples(session, settings, config, now)
    # Show only the latest retrieved issue per public forecast channel. The
    # nearest retained point to tomorrow's UTC instant is labelled with its exact
    # validity; a model revision never overwrites an observation stream.
    issues = {}
    for sample in samples:
        if sample.series.forecast:
            public_channel = (sample.series.source_id, sample.series.method_version, sample.series.allergen)
            issues[public_channel] = max(issues.get(public_channel, sample.series.forecast.issue_at), sample.series.forecast.issue_at)
    latest = {}
    for sample in samples:
        if sample.series.forecast and sample.series.forecast.issue_at != issues[(sample.series.source_id, sample.series.method_version, sample.series.allergen)]:
            continue
        key = _hash(sample.series.model_dump())
        choose = sample.valid_at > latest[key].valid_at if key in latest else True
        if key in latest and sample.series.forecast:
            target = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=24)
            choose = abs(sample.valid_at - target) < abs(latest[key].valid_at - target)
        if key not in latest or choose:
            latest[key] = sample
    material_count = 0
    current_stream_ids = []
    for sample in latest.values():
        selection = next(s for s in config.selections if s.allergen == sample.series.allergen)
        rule = next((r for r in selection.rules if r.period == sample.series.period), None)
        scale = settings.pollen_source_policy.category_scale(sample.series) if rule and rule.category_change else None
        binding = {"organization_id": subject.organization_id, "owner_id": user_id, "subject_id": subject.id,
                   "configuration_revision": subject.current_revision, "series": sample.series.model_dump(mode="json"),
                   "rule": rule.model_dump(mode="json") if rule else None}
        binding_hash = _hash(binding)
        stream = session.scalar(select(MonitoringLiveStream).where(MonitoringLiveStream.subject_id == subject.id,
            MonitoringLiveStream.organization_id == subject.organization_id, MonitoringLiveStream.run_id == run_id,
            MonitoringLiveStream.binding_hash == binding_hash))
        if stream is None:
            stream = MonitoringLiveStream(id=new_id(), organization_id=subject.organization_id,
                subject_id=subject.id, run_id=run_id, binding_hash=binding_hash, binding_json=binding, sequence=0, state_json={})
            session.add(stream)
            session.flush()
        current_stream_ids.append(stream.id)
        previous = PollenSample.model_validate(stream.state_json["sample"]) if stream.state_json.get("sample") else None
        baseline = None
        if rule and rule.rapid_increase:
            target = sample.valid_at - timedelta(hours=rule.rapid_increase.window_hours)
            baseline = next((s for s in samples if s.series == sample.series and s.valid_at == target), None)
        available = sample.quality == "usable" and now < sample.fresh_until
        input_hash = _hash({"sample": sample.model_dump(), "baseline": baseline.model_dump() if baseline else None,
                            "available": available, "scale": scale.model_dump() if scale else None, "rebaseline": rebaseline})
        existing = session.scalar(select(MonitoringLiveEntry.id).where(
            MonitoringLiveEntry.stream_id == stream.id, MonitoringLiveEntry.input_hash == input_hash))
        if existing:
            continue
        reasons, material_id, numeric, state = [], None, None, None
        if rule and (rule.threshold or rule.rapid_increase):
            prior = NumericState.model_validate(stream.state_json["numeric"]) if stream.state_json.get("numeric") else None
            if prior and rebaseline:
                prior = prior.model_copy(update={
                    "threshold": prior.threshold.model_copy(update={"available": False}) if prior.threshold else None,
                    "rapid": prior.rapid.model_copy(update={"available": False}) if prior.rapid else None})
            numeric_binding = {**binding, "rule": rule.model_copy(update={"category_change": False}).model_dump(mode="json")}
            numeric = evaluate_numeric(NumericBinding.model_validate(numeric_binding), sample, baseline=baseline,
                                       prior=prior, as_of=now)
            state = numeric.state.model_dump(mode="json")
            reasons, material_id = list(numeric.reasons), numeric.material_id
        previous_category = stream.state_json.get("category")
        if previous_category and rebaseline:
            previous_category = {**previous_category, "available": False}
        category = evaluate_category(scale, sample, now=now, prior=previous_category) if scale else None
        if category and category["changed"]:
            reasons.append("category_changed")
            material_id = _hash({"numeric": material_id, "binding": binding, "category": category})
        kind = "initial" if previous is None else "state"
        if previous and _source_order(sample, previous) == "revised":
            kind = "revision"
        if not available:
            kind = "unavailable"
        elif previous and (rebaseline or not stream.state_json.get("available")):
            kind = "recovered"
        if material_id:
            kind = "material"
        stream.sequence += 1
        source_row = session.scalar(select(MonitoringSourceSample).where(
            MonitoringSourceSample.series_hash == _hash(sample.series.model_dump()), MonitoringSourceSample.valid_at == sample.valid_at,
            MonitoringSourceSample.revision == sample.source_revision))
        entry = MonitoringLiveEntry(id=new_id(), organization_id=subject.organization_id, stream_id=stream.id,
            sequence=stream.sequence, input_hash=input_hash, kind=kind, material_id=material_id, created_at=now,
            signal_hash=_hash({"series": sample.series.model_dump(), "valid_at": sample.valid_at,
                "source_revision": sample.source_revision, "rule": binding["rule"], "reasons": reasons}) if material_id else None,
            evidence_json={"binding": binding, "current": sample.model_dump(mode="json"),
                "previous": previous.model_dump(mode="json") if previous else None,
                "baseline": baseline.model_dump(mode="json") if baseline else None,
                "reasons": reasons, "decision": numeric.model_dump(mode="json") if numeric else None, "category": category,
                "attribution": ATTRIBUTION, "terms": TERMS, "run_id": run_id,
                "provenance": deepcopy(source_row.provenance_json) if source_row else {},
                "configuration_revision": subject.current_revision})
        session.add(entry)
        if (not numeric or numeric.disposition != "history_required") and (not category or category["disposition"] != "history_required"):
            stream.state_json = {"sample": sample.model_dump(mode="json"), "numeric": state,
                                 "available": available, "entry_id": entry.id, "category": category["state"] if category else None}
        session.flush()
        if material_id:
            material_count += 1
            if runtime.email_consent and not runtime.muted and config.delivery.email != "off":
                from .pollen_delivery import next_delivery_at
                session.add(MonitoringDelivery(organization_id=subject.organization_id, entry_id=entry.id,
                    owner_user_id=user_id, signal_hash=entry.signal_hash,
                    configuration_revision=subject.current_revision, consent_version=runtime.version,
                    due_at=next_delivery_at(config, now)))
    required_channels = {(s.allergen, r.period) for s in config.selections for r in s.rules}
    covered = {(s.series.allergen, s.series.period) for s in latest.values() if s.quality == "usable" and now < s.fresh_until}
    all_selections = {s.allergen for s in config.selections}.issubset({allergen for allergen, _period in covered})
    runtime.health = "ready" if latest and all_selections and required_channels.issubset(covered) else "waiting" if not latest else "unavailable"
    runtime.last_poll_at, runtime.next_poll_at = now, now + timedelta(minutes=20)
    runtime.current_stream_ids = current_stream_ids
    session.flush()
    return {"status": runtime.health, "material_changes": material_count}


def state(session, *, settings, user_id, subject_id, now):
    organization_id = _actor(session, user_id)
    subject = _owned(session, organization_id, user_id, subject_id)
    runtime = session.get(MonitoringRuntime, subject_id)
    streams = list(session.scalars(select(MonitoringLiveStream).where(
        MonitoringLiveStream.subject_id == subject_id, MonitoringLiveStream.organization_id == organization_id,
        MonitoringLiveStream.run_id == runtime.run_id if runtime else False,
        MonitoringLiveStream.id.in_(runtime.current_stream_ids if runtime else [])).limit(200)))
    current = []
    for stream in streams:
        if not stream.state_json.get("sample"):
            continue
        sample = PollenSample.model_validate(stream.state_json["sample"])
        approval = settings.pollen_source_policy.approval(sample.series, _now(now))
        if approval:
            origin = sample.series.forecast.issue_at if sample.series.forecast else sample.valid_at
            sample = sample.model_copy(update={"fresh_until": origin + timedelta(seconds=approval.freshness_seconds)})
        scale = settings.pollen_source_policy.category_scale(sample.series)
        category = stream.state_json.get("category")
        current.append({"stream_id": stream.id, "entry_id": stream.state_json["entry_id"],
                        "sample": sample.model_dump(mode="json") if approval else sample.model_copy(update={
                            "value": None, "quality": "unavailable", "rights": "unverified"}).model_dump(mode="json"),
                        "availability": "unverified" if approval is None else "stale" if now >= sample.fresh_until
                        else sample.quality,
                        "category": category if approval and scale and category and category.get("scale_sha256") == _hash(scale.model_dump()) and now < sample.fresh_until and sample.quality == "usable" else None})
    configuration = _configuration(session, subject)
    blocking = []
    try:
        _require_live(settings, organization_id)
        _gate(settings, configuration, _now(now))
    except DomainError as error:
        blocking.append(error.code)
    runtime_value = _runtime_view(runtime)
    if runtime and subject.status == "active":
        covered = {(row["sample"]["series"]["allergen"], row["sample"]["series"]["period"])
                   for row in current if row["availability"] == "usable"}
        required = {(selection.allergen, rule.period) for selection in configuration.selections for rule in selection.rules}
        complete = required.issubset(covered) and all(any(a == selection.allergen for a, _ in covered) for selection in configuration.selections)
        runtime_value["health"] = "source_not_approved" if blocking else "source_unavailable" if runtime.health == "source_unavailable" else "ready" if complete else "unavailable" if current else "waiting"
    from sqlalchemy import func
    delivery_counts = dict(session.execute(select(MonitoringDelivery.state, func.count()).join(MonitoringLiveEntry,
        MonitoringLiveEntry.id == MonitoringDelivery.entry_id).join(MonitoringLiveStream,
        MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(MonitoringLiveStream.subject_id == subject_id)
        .group_by(MonitoringDelivery.state)).all())
    return {**_view(session, subject), "runtime": runtime_value, "current": current, "delivery_counts": delivery_counts,
            "coverage": _coverage(settings, configuration, _now(now)),
            "start_available": not blocking, "blocking_reasons": blocking}


def history(session, *, user_id, subject_id, limit=20, before_id=None, material_only=False, settings=None, now=None):
    organization_id = _actor(session, user_id)
    _owned(session, organization_id, user_id, subject_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Invalid history limit.", 422, "subject_limit_invalid")
    statement = select(MonitoringLiveEntry).join(MonitoringLiveStream,
        MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(
        MonitoringLiveStream.subject_id == subject_id, MonitoringLiveStream.organization_id == organization_id)
    if material_only:
        statement = statement.where(MonitoringLiveEntry.material_id.is_not(None))
    if before_id:
        anchor = session.scalar(statement.where(MonitoringLiveEntry.id == before_id))
        if anchor is None:
            raise DomainError("History entry not found.", 404, "monitoring_entry_not_found")
        from sqlalchemy import and_, or_
        statement = statement.where(or_(MonitoringLiveEntry.created_at < anchor.created_at,
            and_(MonitoringLiveEntry.created_at == anchor.created_at, MonitoringLiveEntry.id < anchor.id)))
    rows = list(session.scalars(statement.order_by(MonitoringLiveEntry.created_at.desc(), MonitoringLiveEntry.id.desc()).limit(limit + 1)))
    items = []
    for entry in rows[:limit]:
        review = session.scalar(select(MonitoringReview).where(MonitoringReview.entry_id == entry.id,
            MonitoringReview.organization_id == organization_id).order_by(MonitoringReview.version.desc()).limit(1))
        value = _evidence(entry)
        if settings is not None:
            sample = PollenSample.model_validate(entry.evidence_json["current"])
            approval = settings.pollen_source_policy.approval(sample.series, _now(now or datetime.now(UTC)))
            value["raw_export_available"] = bool(approval and approval.raw_export_allowed)
            if approval is None:
                value.update(current=sample.model_copy(update={"value": None, "quality": "unavailable", "rights": "unverified"}).model_dump(mode="json"),
                    previous=None, baseline=None, decision=None, category=None, provenance={}, reasons=[], source_withheld=True)
        items.append({**value, "review": {"version": review.version, "decision": review.decision} if review else None})
    return {"items": items, "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def review_history(session, *, user_id, subject_id, entry_id, before_version=None):
    organization_id = _actor(session, user_id)
    _owned(session, organization_id, user_id, subject_id)
    entry = session.scalar(select(MonitoringLiveEntry).join(MonitoringLiveStream,
        MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(MonitoringLiveEntry.id == entry_id,
        MonitoringLiveStream.subject_id == subject_id, MonitoringLiveStream.organization_id == organization_id))
    if entry is None:
        raise DomainError("History entry not found.", 404, "monitoring_entry_not_found")
    statement = select(MonitoringReview).where(MonitoringReview.entry_id == entry_id)
    if before_version is not None:
        statement = statement.where(MonitoringReview.version < before_version)
    rows = list(session.scalars(statement.order_by(MonitoringReview.version.desc()).limit(101)))
    return {"items": [{"version": row.version, "decision": row.decision, "created_at": _iso(row.created_at)} for row in rows[:100]],
            "next_before_version": rows[99].version if len(rows) > 100 else None}


def export_records(database, *, settings, user_id, organization_id, subject_id):
    """Streaming private JSONL; only the final complete record certifies a full file.

    Each bounded page rechecks membership and ownership. Concurrent additions are
    excluded by descending cursors; the export identifies its snapshot start but
    is intentionally not a database backup or an importable live configuration.
    """
    import json

    from .monitoring_subjects import subject_history_page
    def line(record):
        return json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with database.organization_context(organization_id), database.session() as session:
        subject = _owned(session, _actor(session, user_id), user_id, subject_id)
        manifest = {"type": "manifest", "format": "pollen-private-history", "version": 1,
                    "started_at": datetime.now(UTC).isoformat(), "subject": _view(session, subject),
                    "complete": False, "raw_artifacts_included": False}
    yield line(manifest)
    cursor = None
    while True:
        with database.organization_context(organization_id), database.session() as session:
            page = subject_history_page(session, user_id=user_id, subject_id=subject_id, limit=100, before_revision=cursor)
        for item in page["items"]:
            yield line({"type": "configuration", "record": item})
        cursor = page["next_before_revision"]
        if cursor is None:
            break
    cursor = None
    while True:
        with database.organization_context(organization_id), database.session() as session:
            page = history(session, user_id=user_id, subject_id=subject_id, limit=100, before_id=cursor,
                           settings=settings, now=datetime.now(UTC))
        for item in page["items"]:
            yield line({"type": "activity", "record": item})
            before = None
            while True:
                with database.organization_context(organization_id), database.session() as session:
                    reviews = review_history(session, user_id=user_id, subject_id=subject_id, entry_id=item["id"], before_version=before)
                for review_item in reviews["items"]:
                    yield line({"type": "review", "entry_id": item["id"], "record": review_item})
                before = reviews["next_before_version"]
                if before is None:
                    break
        cursor = page["next_cursor"]
        if cursor is None:
            break
    with database.organization_context(organization_id), database.session() as session:
        _owned(session, _actor(session, user_id), user_id, subject_id)
    yield line({"type": "complete", "complete": True})


def review(session, *, user_id, subject_id, entry_id, decision, expected_version):
    if decision not in {"reviewed", "not_relevant", "continue", "action_required"} or type(expected_version) is not int or expected_version < 0:
        raise DomainError("Invalid review decision.", 422, "monitoring_review_invalid")
    with _savepoint(session):
        subject = _locked_subject(session, user_id, subject_id)
        entry = session.scalar(select(MonitoringLiveEntry).join(MonitoringLiveStream,
            MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(
            MonitoringLiveEntry.id == entry_id, MonitoringLiveStream.subject_id == subject.id,
            MonitoringLiveStream.organization_id == subject.organization_id))
        if entry is None:
            raise DomainError("History entry not found.", 404, "monitoring_entry_not_found")
        prior = session.scalar(select(MonitoringReview).where(MonitoringReview.entry_id == entry_id,
            MonitoringReview.organization_id == subject.organization_id).order_by(MonitoringReview.version.desc()).limit(1))
        version = prior.version if prior else 0
        if version == expected_version + 1 and prior.decision == decision:
            return {"version": version, "decision": decision}
        if version != expected_version:
            raise DomainError("This review changed; reload its current decision.", 409, "monitoring_review_conflict")
        session.add(MonitoringReview(organization_id=subject.organization_id, entry_id=entry_id,
                                    version=version + 1, decision=decision))
        # A repeated identical signal across this owner's monitors is one review
        # development. Preserve a revision on every linked private evidence entry.
        if entry.signal_hash:
            linked_query = select(MonitoringLiveEntry).join(MonitoringLiveStream,
                MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).join(MonitoringSubject,
                MonitoringSubject.id == MonitoringLiveStream.subject_id).where(
                MonitoringSubject.owner_user_id == user_id, MonitoringSubject.organization_id == subject.organization_id,
                MonitoringLiveEntry.signal_hash == entry.signal_hash, MonitoringLiveEntry.id != entry_id)
            after_id = None
            while True:
                page = linked_query.where(MonitoringLiveEntry.id > after_id) if after_id else linked_query
                linked = list(session.scalars(page.order_by(MonitoringLiveEntry.id).limit(100)))
                if not linked:
                    break
                for other in linked:
                    previous_review = session.scalar(select(MonitoringReview).where(MonitoringReview.entry_id == other.id)
                        .order_by(MonitoringReview.version.desc()).limit(1))
                    session.add(MonitoringReview(organization_id=subject.organization_id, entry_id=other.id,
                        version=(previous_review.version if previous_review else 0) + 1, decision=decision))
                after_id = linked[-1].id
        session.flush()
        return {"version": version + 1, "decision": decision}


def revise_paused(session, *, user_id, subject_id, expected_revision, configuration, now):
    from .monitoring_subjects import _configuration as validate
    payload, digest = validate(configuration)
    with _savepoint(session):
        subject = _locked_subject(session, user_id, subject_id)
        if subject.status != "paused" or subject.current_revision != expected_revision:
            raise DomainError("Pause and review current settings before editing.", 409, "subject_revision_conflict")
        runtime = session.get(MonitoringRuntime, subject_id)
        if runtime is None:
            raise DomainError("Monitoring state is unavailable.", 409, "monitoring_state_conflict")
        subject.current_revision += 1
        subject.updated_at = _now(now)
        session.add(MonitoringSubjectRevision(organization_id=subject.organization_id, subject_id=subject_id,
            revision=subject.current_revision, configuration_json=payload, configuration_hash=digest))
        runtime.configuration_revision = subject.current_revision
        runtime.version += 1
        runtime.run_id, runtime.health, runtime.email_consent = new_id(), "waiting", False
        runtime.current_stream_ids = []
        session.flush()
        return _view(session, subject)


def remove(session, *, user_id, subject_id, expected_revision, expected_version):
    with _savepoint(session):
        subject = _locked_subject(session, user_id, subject_id)
        runtime = session.get(MonitoringRuntime, subject_id)
        if (type(expected_version) is not int or expected_version < 1 or runtime is None
                or runtime.version != expected_version or subject.current_revision != expected_revision):
            raise DomainError("Monitoring changed; review it before deletion.", 409, "subject_revision_conflict")
        session.execute(update(Job).where(Job.organization_id == subject.organization_id,
            Job.target_type == "monitoring_subject", Job.target_id == subject_id,
            Job.state.in_({"queued", "dispatched", "running", "retrying"})).values(cancel_requested=True))
        session.execute(delete(MonitoringSubject).where(MonitoringSubject.id == subject_id,
            MonitoringSubject.organization_id == subject.organization_id, MonitoringSubject.owner_user_id == user_id))
        session.flush()


def artifact_path(session, *, settings, user_id, subject_id, entry_id, artifact_hash, now):
    import hashlib
    import re

    from .monitoring_live_models import MonitoringSourceArtifact
    organization_id = _actor(session, user_id)
    _owned(session, organization_id, user_id, subject_id)
    if not re.fullmatch(r"[a-f0-9]{64}", artifact_hash):
        raise DomainError("Source evidence not found.", 404, "monitoring_evidence_not_found")
    entry = session.scalar(select(MonitoringLiveEntry).join(MonitoringLiveStream,
        MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).where(MonitoringLiveEntry.id == entry_id,
        MonitoringLiveStream.subject_id == subject_id, MonitoringLiveStream.organization_id == organization_id))
    if entry is None:
        raise DomainError("Source evidence not found.", 404, "monitoring_evidence_not_found")
    current = PollenSample.model_validate(entry.evidence_json["current"])
    approval = settings.pollen_source_policy.approval(current.series, _now(now))
    if approval is None or not approval.raw_export_allowed or artifact_hash not in current.artifact_hashes:
        raise DomainError("Source evidence is unavailable under the current policy.", 404, "monitoring_evidence_not_found")
    artifact = session.get(MonitoringSourceArtifact, artifact_hash)
    path = settings.data_dir / "monitoring-public-artifacts" / artifact_hash[:2] / artifact_hash
    if artifact is None or artifact.retention_until.replace(tzinfo=UTC) <= _now(now) or not path.is_file():
        raise DomainError("Retained source evidence is unavailable.", 410, "monitoring_evidence_expired")
    if path.stat().st_size != artifact.byte_count or artifact.byte_count > 64 * 1024 * 1024:
        raise DomainError("Source evidence integrity check failed.", 503, "monitoring_evidence_integrity")
    with path.open("rb") as body:
        digest = hashlib.file_digest(body, "sha256").hexdigest()
    if digest != artifact_hash:
        raise DomainError("Source evidence integrity check failed.", 503, "monitoring_evidence_integrity")
    return path


def today(session, *, settings, user_id, now, before_id=None):
    from sqlalchemy import and_, func, or_
    organization_id = _actor(session, user_id)
    if settings.deployment_instance != "monitoring-v2" or _mode(settings, organization_id) != ReaderMode.ENABLED:
        return {"items": [], "next_cursor": None}
    latest = select(MonitoringLiveEntry.stream_id, func.max(MonitoringLiveEntry.sequence).label("sequence")).where(
        MonitoringLiveEntry.material_id.is_not(None)).group_by(MonitoringLiveEntry.stream_id).subquery()
    decision = select(MonitoringReview.decision).where(MonitoringReview.entry_id == MonitoringLiveEntry.id).order_by(
        MonitoringReview.version.desc()).limit(1).correlate(MonitoringLiveEntry).scalar_subquery()
    statement = select(MonitoringLiveEntry, MonitoringSubject.id, MonitoringRuntime.current_stream_ids).join(latest,
        and_(latest.c.stream_id == MonitoringLiveEntry.stream_id, latest.c.sequence == MonitoringLiveEntry.sequence))
    statement = statement.join(MonitoringLiveStream, MonitoringLiveStream.id == MonitoringLiveEntry.stream_id).join(
        MonitoringSubject, MonitoringSubject.id == MonitoringLiveStream.subject_id).join(MonitoringRuntime,
        and_(MonitoringRuntime.subject_id == MonitoringSubject.id, MonitoringRuntime.run_id == MonitoringLiveStream.run_id)).where(
        MonitoringSubject.owner_user_id == user_id, MonitoringSubject.organization_id == organization_id,
        MonitoringSubject.status.in_({"active", "paused"}), or_(decision.is_(None), decision.in_({"continue", "action_required"})))
    ranked = statement.add_columns(func.row_number().over(partition_by=MonitoringLiveEntry.signal_hash,
        order_by=(MonitoringLiveEntry.created_at.desc(), MonitoringLiveEntry.id.desc())).label("signal_rank")).subquery()
    statement = statement.where(MonitoringLiveEntry.id.in_(select(ranked.c.id).where(ranked.c.signal_rank == 1)))
    if before_id:
        anchor = session.execute(statement.where(MonitoringLiveEntry.id == before_id)).first()
        if anchor is None:
            raise DomainError("The review page changed. Reload it.", 409, "monitoring_page_changed")
        entry = anchor[0]
        statement = statement.where(or_(MonitoringLiveEntry.created_at < entry.created_at,
            and_(MonitoringLiveEntry.created_at == entry.created_at, MonitoringLiveEntry.id < entry.id)))
    rows = list(session.execute(statement.order_by(MonitoringLiveEntry.created_at.desc(), MonitoringLiveEntry.id.desc()).limit(101)))
    items = []
    for entry, subject_id, current_ids in rows[:100]:
        if entry.stream_id not in current_ids:
            continue
        sample = PollenSample.model_validate(entry.evidence_json["current"])
        if settings.pollen_source_policy.approval(sample.series, _now(now)) is None:
            continue
        items.append({"id": entry.id, "subject_id": subject_id, "station_id": sample.series.station_id,
                      "allergen": sample.series.allergen, "reasons": entry.evidence_json["reasons"],
                      "detected_at": _iso(entry.created_at)})
        if len(items) == 20:
            return {"items": items, "next_cursor": entry.id}
    return {"items": items, "next_cursor": rows[99][0].id if len(rows) > 100 else None}
