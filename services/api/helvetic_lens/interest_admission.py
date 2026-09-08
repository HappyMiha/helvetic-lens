"""Assemble current organization inputs, independently of truncated feed cards.

Internal worker API: no HTTP admission, inference, commits, private chat or
personal read state. Whole saved documents are supported when they fit; larger
inputs fail explicitly and need the material-change planner, never sampling.
"""

import json
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import or_, select

from .config import DomainError
from .corpus_access import accessible_versions, visible
from .identity import assess_comparison_identity
from .interest_assessment import Dossier, Event, Evidence, Interest, ProfileFact, fingerprint
from .models import (
    Comparison,
    DocumentWatch,
    IdentityDecision,
    Law,
    LegacyDocumentMapping,
    MonitoringTopic,
    MonitoringTopicRevision,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    Profile,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
    TopicEventMatch,
    Version,
)
from .relation_candidates import RULE_REVISION, score_pair
from .relation_identity import relation_direction
from .topic_matching import describe_matches

MAX_INTERESTS = 64
MAX_UNITS = 64


def _fail(code, message):
    raise DomainError(message, 409, code)


def _batch(session, query, model):
    """Traverse all candidates, including long runs of stale matches."""
    after = ""
    while True:
        rows = list(session.scalars(query.where(model.id > after).order_by(model.id).limit(100)))
        if not rows:
            return
        yield rows
        after = rows[-1].id


def _bound(items):
    if len(items) > MAX_INTERESTS:
        _fail("interest_context_exceeded", "The complete interest set needs aggregation; no interests were dropped.")


def _signals(value):
    rows = value if isinstance(value, list) else [value]
    return [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in rows]


def _topics(session, organization_id, event_id):
    query = (select(TopicEventMatch)
        .join(MonitoringTopic, MonitoringTopic.id == TopicEventMatch.topic_id)
        .join(MonitoringTopicRevision, MonitoringTopicRevision.id == TopicEventMatch.topic_revision_id)
        .where(TopicEventMatch.organization_id == organization_id, TopicEventMatch.event_id == event_id,
               MonitoringTopic.organization_id == organization_id,
               MonitoringTopicRevision.organization_id == organization_id,
               MonitoringTopicRevision.topic_id == MonitoringTopic.id))
    result = []
    for batch in _batch(session, query, TopicEventMatch):
        names = dict(session.execute(select(MonitoringTopicRevision.id, MonitoringTopicRevision.name).where(
            MonitoringTopicRevision.organization_id == organization_id,
            MonitoringTopicRevision.id.in_([row.topic_revision_id for row in batch]))).all())
        for row in describe_matches(session, batch):
            if not row["is_current"] or (row["decision_is_current"] and row["decision"] in {"muted", "rejected"}):
                continue
            result.append(dict(id=row["id"], kind="topic", revision=row["topic_revision_id"],
                fingerprint=fingerprint({key: row[key] for key in (
                    "evaluation_fingerprint", "rule_fingerprint", "reasons", "review_id", "decision", "decision_is_current")}),
                name=names[row["topic_revision_id"]], reason_signals=_signals(row["reasons"])))
            _bound(result)
    return result


def _watches(session, organization_id, work_id, watch_id=None):
    query = select(DocumentWatch).join(Law, Law.id == DocumentWatch.law_id)
    query = (query
        .join(LegacyDocumentMapping, LegacyDocumentMapping.law_id == Law.id)
        .where(DocumentWatch.organization_id == organization_id, DocumentWatch.active.is_(True),
               LegacyDocumentMapping.work_id == work_id, visible(Law, organization_id),
               visible(LegacyDocumentMapping, organization_id)))
    if watch_id:
        query = query.where(DocumentWatch.id == watch_id)
    return list(session.scalars(query.order_by(DocumentWatch.id).limit(MAX_INTERESTS + 1)))


def _laws(session, organization_id, event):
    source = session.scalar(select(RegulatoryWork).where(RegulatoryWork.id == event.work_id,
                                                        visible(RegulatoryWork, organization_id)))
    if source is None:
        _fail("interest_evidence_unavailable", "The event source is no longer available to this organization.")
    query = (select(OrganizationRelationCandidate)
        .join(RelationCandidate, RelationCandidate.id == OrganizationRelationCandidate.candidate_id)
        .where(OrganizationRelationCandidate.organization_id == organization_id,
               OrganizationRelationCandidate.status.not_in(["dismissed", "expired"]),
               RelationCandidate.event_id == event.id,
               RelationCandidate.rule_revision == RULE_REVISION,
               RelationCandidate.status.in_(["active", "promoted"]),
               or_(RelationCandidate.expires_at.is_(None), RelationCandidate.expires_at > datetime.now(UTC))))
    result = []
    for batch in _batch(session, query, OrganizationRelationCandidate):
        for delivery in batch:
            candidate = session.get(RelationCandidate, delivery.candidate_id)
            if candidate.source_work_id != event.work_id or candidate.source_version_id != event.document_version_id:
                continue
            watches = _watches(session, organization_id, candidate.target_work_id, delivery.watch_id)
            watch = next((row for row in watches if row.id == delivery.watch_id), None)
            target = session.scalar(select(RegulatoryWork).where(RegulatoryWork.id == candidate.target_work_id,
                                                               visible(RegulatoryWork, organization_id)))
            if not watch or target is None:
                continue
            relation = session.get(RegulatoryRelation, candidate.relation_id) if candidate.relation_id else None
            if relation and not relation_direction(relation, source.id, target.id):
                relation = None
            # A current rule label alone does not prove the saved retrieval
            # signals survived a metadata correction. Re-evaluate without
            # rewriting the candidate or promoting similarity to legal evidence.
            scored = score_pair(source, event, target, relation)
            if scored is None:
                continue
            review = session.scalar(select(OrganizationRelationReview).where(
                OrganizationRelationReview.organization_id == organization_id,
                OrganizationRelationReview.organization_candidate_id == delivery.id
            ).order_by(OrganizationRelationReview.created_at.desc(), OrganizationRelationReview.id.desc()).limit(1))
            if review and review.decision == "rejected":
                continue
            result.append((dict(id=delivery.id, kind="law", revision=str(candidate.evidence_revision),
                fingerprint=fingerprint({"candidate": candidate.id, "revision": candidate.evidence_revision,
                    "rule": candidate.rule_revision, "why": scored.why, "score": scored.components,
                    "relation": [relation.id, relation.evidence_revision] if relation else None,
                    "target_version": candidate.target_version_id, "target_revision": target.evidence_revision,
                    "watch": watch.id, "name": watch.display_name,
                    "review": [review.id, review.decision] if review else None}),
                name=watch.display_name, reason_signals=list(scored.why)),
                candidate.target_version_id, candidate.target_work_id))
            _bound(result)
    return result


def _saved_document(session, organization_id, version_id, work_id, source_kind, expression_id=None):
    # Do not accept a version merely because its ID exists in a privileged worker
    # session. Grants AND every legacy parent AND exact work binding must match.
    row = session.execute(accessible_versions(organization_id).where(
        RegulatoryDocumentVersion.id == version_id, RegulatoryWork.id == work_id)).first()
    if row is None:
        _fail("interest_evidence_unavailable", "A saved document is unavailable to this organization.")
    native = row[0]
    if expression_id and native.expression_id != expression_id:
        _fail("interest_evidence_unavailable", "The event and saved document language identities disagree.")
    if source_kind == "monitored_law":
        latest = session.scalar(accessible_versions(organization_id).with_only_columns(RegulatoryDocumentVersion.id).where(
            RegulatoryDocumentVersion.expression_id == native.expression_id
        ).order_by(RegulatoryDocumentVersion.created_at.desc(), RegulatoryDocumentVersion.id.desc()).limit(1))
        if latest != native.id:
            _fail("interest_evidence_unavailable", "The monitored law has a newer saved version; recheck its candidate before enrichment.")
    version = native
    if native.legacy_version_id:
        version = session.scalar(select(Version).join(Law, Law.id == Version.law_id).where(
            Version.id == native.legacy_version_id, visible(Version, organization_id), visible(Law, organization_id)))
        mapped = session.scalar(select(LegacyDocumentMapping.id).where(
            LegacyDocumentMapping.law_id == version.law_id, LegacyDocumentMapping.work_id == work_id,
            visible(LegacyDocumentMapping, organization_id))) if version else None
        if not mapped:
            _fail("interest_evidence_unavailable", "The saved legacy document no longer belongs to this work.")
    if not version.artifact_key or not version.source_url:
        _fail("interest_evidence_unavailable", "The original document identity or publisher URL is missing.")
    passages = version.passages or []
    if not isinstance(passages, list) or not passages:
        _fail("interest_evidence_unavailable", "Saved citable document passages are required, not metadata-only discovery leads.")
    for passage in passages:
        if (not isinstance(passage, dict) or not isinstance(passage.get("id"), str)
                or not isinstance(passage.get("text"), str) or not passage["text"].strip()):
            _fail("interest_evidence_unavailable", "A saved passage is malformed; source evidence needs repair.")
    if len({row["id"] for row in passages}) != len(passages):
        _fail("interest_evidence_unavailable", "Saved passage IDs are ambiguous; source evidence needs repair.")
    return native, version, {"native_id": native.id, "native_revision": native.evidence_revision,
                            "version_id": version.id, "revision": version.evidence_revision,
                            "text_hash": fingerprint(version.text), "passage_hash": fingerprint(passages)}


def _document(session, organization_id, version_id, work_id, source_kind, expression_id=None):
    _, version, binding = _saved_document(session, organization_id, version_id, work_id, source_kind, expression_id)
    if len(version.passages) > MAX_UNITS:
        _fail("interest_context_exceeded", "This complete document needs material-unit planning; it was not sampled.")
    evidence = []
    for passage in version.passages:
        evidence.append(Evidence(id="ev_" + fingerprint([version.id, passage["id"], source_kind])[:32],
            version_id=version.id, artifact_id=version.artifact_key, unit_id=passage["id"],
            text=passage["text"], source_url=version.source_url, source_kind=source_kind, primary_source=True))
    return evidence, binding


def _event_document(session, organization_id, event, watches):
    from .interest_material import plan
    native, after, source_binding = _saved_document(session, organization_id, event.document_version_id,
        event.work_id, "event", event.expression_id)
    comparison = None
    if native.legacy_version_id:
        query = select(Comparison).where(Comparison.new_version_id == after.id,
            Comparison.law_id == after.law_id, visible(Comparison, organization_id))
        baselines = {row.selected_baseline_version_id for row in watches if row.selected_baseline_version_id}
        if len(baselines) > 1:
            _fail("interest_comparison_ambiguous", "Monitoring has conflicting saved baselines; no comparison was guessed.")
        if baselines:
            query = query.where(Comparison.old_version_id == next(iter(baselines)))
        # Two distinct pairs are enough to establish ambiguity. Never choose
        # an earlier legal version by import timestamp or by model suggestion.
        pairs = list(session.scalars(query.with_only_columns(Comparison.old_version_id).distinct().limit(2)))
        if len(pairs) > 1:
            _fail("interest_comparison_ambiguous", "Several saved baselines exist; select a monitoring baseline before change analysis.")
        if pairs:
            comparison = session.scalar(query.order_by(Comparison.id).limit(1))
    if comparison is None:
        evidence, binding = _document(session, organization_id, native.id, event.work_id, "event", event.expression_id)
        return evidence, binding, None
    # Imported legacy baselines are already viewable under Version/Law ownership
    # but may not have a corpus mirror. Do not create one as a read side effect.
    before = session.scalar(select(Version).join(Law, Law.id == Version.law_id).where(
        Version.id == comparison.old_version_id, Version.law_id == after.law_id,
        visible(Version, organization_id), visible(Law, organization_id)))
    if before is None or not before.artifact_key or not before.source_url:
        _fail("interest_evidence_unavailable", "The baseline or its saved original is unavailable to this organization.")
    before_native = session.scalar(select(RegulatoryDocumentVersion).where(
        RegulatoryDocumentVersion.legacy_version_id == before.id))
    if before_native and before_native.expression_id != native.expression_id:
        _fail("interest_evidence_unavailable", "The mapped baseline and current work/language identities disagree.")
    languages = {(row.identity_json or {}).get("language") for row in (before, after)} - {None, "unknown", "und"}
    if len(languages) > 1:
        _fail("interest_evidence_unavailable", "The baseline and current version use different languages.")
    if (not isinstance(before.passages, list) or not before.passages
            or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
                   or not isinstance(row.get("text"), str) or not row["text"].strip() for row in before.passages)):
        _fail("interest_evidence_unavailable", "The baseline has no complete citable saved passages.")
    before_binding = {"version_id": before.id, "revision": before.evidence_revision,
                      "text_hash": fingerprint(before.text), "passage_hash": fingerprint(before.passages),
                      "native": [before_native.id, before_native.evidence_revision] if before_native else None}
    law = session.scalar(select(Law).where(Law.id == after.law_id, visible(Law, organization_id)))
    identity = assess_comparison_identity(law, before, after)
    if identity["status"] == "mismatch":
        _fail("document_identity_mismatch", "These saved artifacts identify different legal works.")
    for side, version in (("old", before), ("new", after)):
        report = identity[side]
        if report["status"] == "unknown" and not session.scalar(select(IdentityDecision.id).where(
            IdentityDecision.organization_id == organization_id, IdentityDecision.version_id == version.id,
            IdentityDecision.action == "confirm_assignment", IdentityDecision.identity_fingerprint == report["fingerprint"]).limit(1)):
            _fail("document_identity_unknown", "The baseline assignment needs confirmation before change analysis.")
    # Historical/monitoring/saved-version modes may retain several records for
    # the same pair. An obsolete record must not hide a valid complete one.
    for candidate in session.scalars(query.order_by(Comparison.id)):
        try:
            evidence, context = plan(candidate, before, after)
            break
        except DomainError as error:
            if error.code != "interest_comparison_unavailable":
                raise
    else:
        _fail("interest_comparison_unavailable", "No saved comparison covers both exact versions; rebuild it before AI analysis.")
    return evidence, {"after": source_binding, "before": before_binding,
                      "comparison": context.diff_fingerprint, "identity": identity["fingerprint"]}, context


def assemble(session, organization_id: str, event_id: str, *, model, locale="en") -> Dossier:
    """Return all current admitted interests or an explicit unavailable/oversize state.

    Caller owns a short transaction, reassembles before publication, and resolves
    the actual approved runtime separately. This does not approve a model route.
    """
    session.flush()
    # A worker may reuse a session after inference. Reload ORM identities so a
    # second currentness check cannot reuse values cached before a source edit.
    session.expire_all()
    event = session.scalar(select(RegulatoryEvent).join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
        .join(RegulatoryEventState, RegulatoryEventState.event_id == RegulatoryEvent.id)
        .where(RegulatoryEvent.id == event_id, RegulatoryEventState.organization_id == organization_id,
               visible(RegulatoryWork, organization_id)))
    if event is None:
        raise DomainError("The event is not admitted to this organization.", 404, "not_found")
    work = session.scalar(select(RegulatoryWork).where(RegulatoryWork.id == event.work_id,
                                                      visible(RegulatoryWork, organization_id)))
    if event.expression_id:
        expression = session.scalar(select(RegulatoryExpression).where(
            RegulatoryExpression.id == event.expression_id, RegulatoryExpression.work_id == event.work_id))
        if expression is None:
            _fail("interest_evidence_unavailable", "Event language and work identities disagree.")
    topics, laws = _topics(session, organization_id, event_id), _laws(session, organization_id, event)
    watches = _watches(session, organization_id, event.work_id)
    _bound(topics + laws + watches)
    if not topics and not laws and not watches:
        _fail("interest_not_current", "No current admitted monitoring interest remains for this event.")
    try:
        evidence, source_binding, comparison = _event_document(session, organization_id, event, watches)
        event_refs = [row.id for row in evidence]
        interests = [Interest(**row, evidence_ids=event_refs) for row in topics]
        for watch in watches:
            interests.append(Interest(id=watch.id, kind="direct_watch", revision=watch.id,
                fingerprint=fingerprint({"law": watch.law_id, "name": watch.display_name,
                                         "baseline": watch.selected_baseline_version_id}),
                name=watch.display_name, reason_signals=["The organization actively monitors this exact work."],
                evidence_ids=event_refs))
        targets = {}
        for values, version_id, work_id in laws:
            if (version_id, work_id) not in targets:
                units, binding = _document(session, organization_id, version_id, work_id, "monitored_law")
                targets[version_id, work_id] = (units, binding)
                evidence.extend(units)
            units, _ = targets[version_id, work_id]
            interests.append(Interest(**values, evidence_ids=event_refs + [row.id for row in units]))
        profile = session.scalar(select(Profile).where(Profile.organization_id == organization_id))
        facts = []
        if profile and profile.description.strip():
            facts.append(ProfileFact(id="description", field="description", text=profile.description))
        for index, area in enumerate(profile.business_areas if profile else []):
            if area.strip():
                facts.append(ProfileFact(id=f"business-area-{index}", field="business_area", text=area))
        binding = {"event": event.evidence_revision, "event_version": event.document_version_id,
                   "event_evidence": event.evidence_json, "work": work.evidence_revision,
                   "source": source_binding, "targets": [value[1] for _, value in sorted(targets.items())]}
        comparison_note = (
            "All material changes from the complete saved comparison are supplied with exact before/after evidence. Unchanged and presentation-only passages are excluded from AI input, not from the saved audit. Saved comparison order does not establish legal effective dates."
            if comparison else
            "This dossier contains complete saved document passages, not a before/after comparison. Do not enumerate changes from a prior version.")
        return Dossier(organization_id=organization_id, event=Event(id=event.id, title=work.title, kind=work.kind,
            event_type=event.event_type, input_fingerprint=fingerprint(binding), limitations=[comparison_note,
                "No independently bound official status/date facts are supplied. Do not infer enactment, repeal or deadlines."]),
            profile_revision=profile.revision if profile else 1, profile_facts=facts,
            interests=sorted(interests, key=lambda item: item.id), evidence=sorted(evidence, key=lambda item: item.id),
            model=model, locale=locale, source_comparison=comparison)
    except ValidationError as error:
        # Pydantic errors can echo source text. Persist/display a category only.
        raise DomainError("The complete dossier exceeds its contract or contains invalid saved evidence; nothing was truncated.",
                          409, "interest_context_exceeded") from error


def current_key(session, organization_id, event_id, *, model, locale="en", instructions=None):
    """A fresh read key, never scheduling or inference. Caller handles unavailable states."""
    from .interest_assessment import SYSTEM, manifest
    dossier = assemble(session, organization_id, event_id, model=model, locale=locale)
    return dossier, fingerprint(manifest(dossier, SYSTEM if instructions is None else instructions))
