"""A whole fictional mission; no paid/live providers or production records."""
import hashlib
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from pdf_fixture import make_pdf
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import GRANT, RECIPIENT
from test_product_research_following import finished
from test_product_web_research import setup

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.db import utcnow
from helvetic_lens.product_contribution_extract import parse
from helvetic_lens.product_document_reading import valid
from helvetic_lens.product_investigation_models import Investigation
from helvetic_lens.product_research_materiality import delivery, project

LATE = "The fictional Registry of Switzerland revised the Alpine grant record in version 2; the amount remains disputed."


def test_incremental_reader_reaches_late_pdf_evidence_and_keeps_original_identity():
    body = make_pdf([f"Fictional appendix {n}" for n in range(24)] + [LATE])
    cursor, portions = {"page": 0, "offset": 0}, []
    while cursor is not None:
        value = parse(body, "appendix.pdf", "application/pdf", cursor=cursor)
        portions.append(value)
        cursor = value["reading"]["next_cursor"]
    assert len(portions) == 7
    assert portions[-1]["excerpts"][0]["text"] == LATE
    assert portions[-1]["excerpts"][0]["passage"].startswith("page-25-")
    assert portions[-1]["reading"]["complete"]
    again = parse(body, "appendix.pdf", "application/pdf", cursor={"page": 24, "offset": 0})
    assert again == portions[-1]
    result = {**again, "sha256": hashlib.sha256(body).hexdigest()}
    assert valid({"document_cursor": again["reading"]["cursor"], "document_sha256": result["sha256"]}, result)
    assert not valid({"document_cursor": again["reading"]["cursor"], "document_sha256": "f" * 64}, result)


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_question_autonomously_deepens_reads_late_document_and_returns_cited_conflict(signed, monkeypatch, product):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    base_model, base_search, base_read = model.complete, decision_search.federated_retrieve, decision_sources.safe_inspect
    page_count = 420 if product == "legal" else 25
    reference = "The governing exception appears on physical PDF page " + str(page_count) + "."
    body = make_pdf([reference] + [f"Appendix introduction {n}. " + "Fictional background context for the document review. " * 5 for n in range(page_count - 2)] + [LATE])
    reads, checkpoints, section_inputs, document_reviews = [], [], [], []

    async def search(settings, query, *args, **kwargs):
        if "revised original appendix" in query:
            return {"items": [{"id": "b" * 32, "title": "Alpine Foundation revised original appendix",
                "url": "https://example.org/revision.pdf", "summary": "Fictional original record"}],
                "lanes": [{"status": "complete", "name": "Fictional primary registry"}]}
        return await base_search(settings, query, *args, **kwargs)

    async def read(settings, query, item, mode, **kwargs):
        if item["url"].endswith("revision.pdf"):
            cursor = kwargs["document_cursor"]
            reads.append(cursor)
            from helvetic_lens.product_document_storage import retain
            original = retain(kwargs["retain_original"]["folder"], kwargs["retain_original"]["prefix"], body,
                {"title": "source.pdf", "content_type": "application/pdf", "url": item["url"], "fetched_at": utcnow().isoformat()})
            return {**parse(body, "revision.pdf", "application/pdf", cursor=cursor),
                "url": item["url"], "sha256": hashlib.sha256(body).hexdigest(), "_retained_document": original}
        return await base_read(settings, query, item, mode, **kwargs)

    async def complete_model(system, user, **kwargs):
        data = json.loads(user)
        phase = kwargs["response_schema"]["title"]
        if data.get("document_section"):
            section_inputs.append(data)
            source = data["source"]
            late = next((p for p in source["excerpts"] if p["text"] == LATE), None)
            referring = next((p for p in source["excerpts"] if p["text"] == reference), None)
            return json.dumps({"claims": [] if not late else [{"statement": "The revised record still describes a disputed amount.",
                "relation": "SUPPORTS", "quote": LATE, "locator": late["passage"]}], "entities": [], "relationships": [],
                "professional_facts": [] if not late else [{"source_id": source["id"], "domain": "legal", "dimension": "version",
                    "value": "version 2", "quote": LATE, "locator": late["passage"]}],
                "section_review": {"coverage_fingerprint": data["document_section"]["coverage_fingerprint"],
                    "summary": "This section provides background and must be compared with the later exception.",
                    "observations": [] if not late else [{"statement": "The revised record still describes a disputed amount.",
                        "role": "counterevidence", "quote": LATE, "locator": late["passage"]}],
                    "cross_references": [] if not referring else [{"target": "governing exception", "target_pages": [page_count],
                        "quote": reference, "locator": referring["passage"]}], "limitations": []}})
        if phase == "DocumentReview":
            document_reviews.append(data)
            checks = []
            for ref in data["cross_references"]:
                target = next(p for p in ref["target_passages"] if p["text"] == LATE)
                checks.append({"id": ref["id"], "status": "verified", "explanation": "The later page records the unresolved exception.",
                    "evidence": {"source_id": target["source_id"], "locator": target["passage"], "quote": LATE,
                        "statement": "The revised record still describes a disputed amount.", "role": "counterevidence"}})
            return json.dumps({"coverage_fingerprint": data["coverage_fingerprint"], "findings": [],
                "cross_reference_checks": checks, "limitations": ["The source leaves the amount unresolved."]})
        if phase == "Briefing":
            sources = data["sources"]
            def cite(text, role):
                source, passage = next((s, p) for s in sources for p in s["excerpts"] if p["text"] == text)
                return {"source_id": source["id"], "quote": text, "locator": passage["passage"], "role": role}
            round_number = data["research_mission"]["round"]
            checkpoints.append(round_number)
            found_late = any(p["text"] == LATE for s in sources for p in s["excerpts"])
            evidence = [cite(GRANT, "support"), cite(RECIPIENT, "counterevidence")]
            points = [{"statement": "The foundation and recipient disclose different amounts for the same grant.", "evidence": evidence}]
            if found_late:
                points.append({"statement": "The revised original still records a dispute.", "evidence": [cite(LATE, "support")]})
            gap = {**cite(GRANT, "context"), "question": "Does a revised original resolve the conflicting amount?",
                "query": "Alpine Foundation revised original appendix", "purpose": "Read the later original before accepting either amount.",
                "priority": 5, "kind": "contradiction"}
            gap.pop("role")
            return json.dumps({"understanding": "The user may be asking who received the foundation's funds.",
                "findings": [{k: v for k, v in {**cite(GRANT, "support"), "statement": GRANT, "basis": "direct"}.items() if k != "role"}],
                "uncertainties": ["The intended foundation and reason for the discrepancy remain unresolved."],
                "clarification": "", "directions": [], "mission_checkpoint": {
                    "answer": {"status": "conflicting", "points": points, "limitations": ["The sources do not explain why the amounts differ."]},
                    "action": "finish" if found_late else "continue", "reason": "Read the revised original to test the conflict." if not found_late else "The original was read; the conflict remains unresolved.",
                    "next_checks": [] if found_late else [gap]}})
        return await base_model(system, user, **kwargs)

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", complete_model)
    root, run, _ = start(client, product)
    # New worker invocation/transaction each step, preserving real stored cursors.
    for _ in range(240):
        with service.db.session() as session:
            status = session.get(Investigation, run["id"]).status
        if status not in {"queued", "running"}:
            break
        tick(service, run["id"])
    result = client.get(root + "/investigations/" + run["id"]).json()
    assert result["status"] == "completed", result["stop_reason"]
    mission = result["exploration"]["mission"]
    assert checkpoints == [1, 2], result
    assert reads == [{"page": 0, "offset": 0}]  # One original fetch; subsequent reads are local.
    assert len(document_reviews) == 1
    assert sum(len(d["source"]["excerpts"]) for d in section_inputs) == page_count
    assert mission["documents"][-1]["pages_read"] == page_count
    assert mission["documents"][-1]["analysis_complete"]
    assert mission["documents"][-1]["reconciliation"]["cross_reference_checks"][0]["status"] == "verified"
    assert result["research"]["execution_policy"] == "completion_based"
    assert mission["answer"]["status"] == "conflicting" and len(mission["answer"]["points"]) == 2
    assert mission["answer"]["limitations"] == ["The sources do not explain why the amounts differ."]
    assert mission["knowledge"]["professional_context"]["facts"][0]["value"] == "version 2"
    assert mission["documents"][-1]["complete"]
    assert mission["stop"] == "available_checks_complete"
    # Opening the dossier needs saved conclusions, not raw captures, receipt
    # trees or another cross-run ledger reconstruction. It performs no work.
    from helvetic_lens import product_current_knowledge as knowledge

    def forbidden(*args, **kwargs):
        raise AssertionError("Opening saved reading must not rebuild knowledge or call a provider")

    with monkeypatch.context() as read_only:
        read_only.setattr(knowledge, "project", forbidden)
        read_only.setattr(model, "complete", forbidden)
        read_only.setattr(decision_search, "federated_retrieve", forbidden)
        read_only.setattr(decision_sources, "safe_inspect", forbidden)
        response = client.get(root + "/investigations/" + run["id"] + "/reading")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    compact = response.json()
    assert compact["view"] == "reading"
    assert compact["revision"] == result["revision"] and compact["event_sequence"] == result["event_sequence"]
    assert compact["retry"] == result["retry"]
    assert not {"sources", "plans", "claims", "evidence", "activity", "research"}.intersection(compact)
    reading = compact["exploration"]["mission"]
    assert reading["answer"] == mission["answer"]
    assert reading["knowledge"] is None and reading["knowledge_deferred"]
    assert reading["checkpoints"] == [{k: v for k, v in check.items() if k != "answer"} for check in mission["checkpoints"]]
    assert compact["exploration"]["sources"] == result["exploration"]["sources"]
    for doc, original in zip(reading["documents"], mission["documents"], strict=True):
        assert doc == {key: original[key] for key in doc}
        assert doc["complete"] == original["complete"]
        assert "reconciliation" not in doc and "section_reviews" not in doc
    assert compact["coverage_manifest"] == {k: v for k, v in result["coverage_manifest"].items() if k != "executions"}
    assert len(response.content) < len(json.dumps(result).encode())
    # Reader references must never escape the current allowed source namespace.
    ids = {s["id"] for s in result["sources"]}
    assert all(e["source_id"] in ids for point in mission["answer"]["points"] for e in point["evidence"])
    from helvetic_lens import product_exploration as exploration
    from helvetic_lens.product_investigation_models import InvestigationSource
    from helvetic_lens.product_iterative_research import projection as budget_projection

    with service.db.session() as session:
        current = session.get(Investigation, run["id"])
        assert "mission" not in budget_projection(current)
        source = session.get(InvestigationSource, mission["answer"]["points"][0]["evidence"][0]["source_id"])
        source.sha256 = "e" * 64
        session.flush()
        withdrawn = exploration.projection(session, current)
        assert withdrawn["mission"]["answer"] is None
        assert withdrawn["mission"]["checkpoints"] == []
        compact_withdrawn = exploration.projection(session, current, reading=True)
        assert compact_withdrawn["mission"]["answer"] is None
        assert compact_withdrawn["mission"]["checkpoints"] == []



def test_delivery_distinguishes_material_change_findings_quiet_and_failed_coverage():
    now = utcnow()
    findings = project({"state": "completed", "findings": [{"id": "finding"}]})
    assert delivery("immediate", findings, now, now=now) == "immediate"
    assert delivery("digest", findings, now - timedelta(days=1), now=now) == "digest"
    gap = project({"state": "failed", "limitations": ["The original was unavailable."]})
    assert delivery("immediate", gap, now, now=now) == "immediate"
    assert delivery("silent", gap, now, now=now) == "silent"
    repeated = project({"state": "completed", "comparisons": [{"kind": "UPDATES", "source_relationship": {"content_hash_match": True}}]})
    assert repeated["category"] == "quiet"


def test_personal_mode_change_does_not_acknowledge_unread_evidence(signed):
    client, service, _, _ = signed
    doc, root = setup(client)
    state = post(client, root + "/follow", {"expected_revision": 0, "following": True}).json()
    finished(service, doc)
    before = client.get(root + "/follow").json()
    assert before["unread"]
    quiet = post(client, root + "/follow", {"expected_revision": state["revision"], "following": True, "delivery_mode": "silent"}).json()
    assert quiet["delivery_mode"] == "silent" and not quiet["unread"]
    restored = post(client, root + "/follow", {"expected_revision": quiet["revision"], "following": True, "delivery_mode": "immediate"}).json()
    assert restored["unread"] and restored["research"]["unseen"] == before["research"]["unseen"]


def test_current_knowledge_groups_exact_identities_without_overriding_human_decisions(signed):
    from sqlalchemy import select
    from test_product_entity_identity import proposal, review_body, seed

    from helvetic_lens.product_current_knowledge import project as knowledge
    from helvetic_lens.product_investigation_models import (
        ClaimChange,
        ClaimEvidence,
        DossierClaim,
        InvestigationSource,
    )
    from helvetic_lens.product_investigations import Extraction, apply_extraction, scope

    client, service, _, root, _, source_ids, run_ids, _ = seed(signed)
    claims = []
    with service.db.session() as session:
        for source_id in source_ids:
            source = session.get(InvestigationSource, source_id)
            source.kind = "public_source"
            run = session.get(Investigation, source.investigation_id)
            quote = source.snapshot["excerpts"][0]["text"]
            apply_extraction(session, run, source, Extraction.model_validate({"claims": [{
                "statement": quote, "quote": quote, "locator": "p1", "relation": "SUPPORTS"}]}))
            session.flush()
            claims.append(session.scalar(select(DossierClaim).where(DossierClaim.investigation_id == run.id)))
        old, new = claims
        older = session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == old.id))
        newer = session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == new.id))
        change = ClaimChange(**scope(run), claim_id=new.id, evidence_id=newer.id,
            previous_claim_id=old.id, previous_investigation_id=old.investigation_id,
            previous_evidence_id=older.id, previous_revision=old.revision, previous_status=old.status,
            kind="UPDATES", explanation="Fixture proposed update, not an accepted replacement.")
        session.add(change)
        session.flush()
        view = knowledge(session, run)
        assert len(view["identities"]) == 1 and len(view["identities"][0]["mentions"]) == 2
        assert view["document_origins"][0]["independence"] == "same_document"
        assert next(c for c in view["claims"] if c["id"] == old.id)["reading_state"] == "update_needs_review"
        assert old.status == "SUPPORTED"  # Canonical reading never rewrites original claims.
        old.revision += 1
        session.flush()
        assert next(c for c in knowledge(session, run)["claims"] if c["id"] == old.id)["reading_state"] == "current"
        session.commit()
    value = proposal(client, root)
    rejected = post(client, root + "/entity-identities/review", review_body(value, decision="different"))
    assert rejected.status_code == 200, rejected.text
    with service.db.session() as session:
        run = session.get(Investigation, run_ids[-1])
        assert len(knowledge(session, run)["identities"]) == 2
        # A now-private source cannot leak back through the cross-run context.
        source = session.get(InvestigationSource, source_ids[0])
        source.kind = "uploaded_file"
        session.flush()
        visible = knowledge(session, run)
        assert all(m["source"]["id"] != source.id for g in visible["identities"] for m in g["mentions"])
        assert all(e["source_id"] != source.id for c in visible["claims"] for e in c["evidence"])


def test_failed_whole_document_review_never_finishes_and_retry_keeps_read_sections(signed, monkeypatch):
    from test_product_contributions import TEXT, create, model_output, upload
    from test_product_dossiers import ROOT
    from test_product_investigations import complete

    client, service, _, model = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    calls = model_output(monkeypatch, model)
    original = model.complete
    fail_once = [True]

    async def temporary_failure(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "DocumentReview" and fail_once[0]:
            fail_once[0] = False
            raise RuntimeError("Fictional review service temporarily unavailable")
        return await original(system, user, **kwargs)

    monkeypatch.setattr(model, "complete", temporary_failure)
    entry = upload(client, route).json()
    root = route + "/investigations"
    failed = complete(client, service, root, entry["analysis"])
    assert failed["status"] == "failed" and "incomplete" in failed["stop_reason"]
    assert len(calls) == 1
    source_ids = [s["id"] for s in failed["sources"]]
    retried = post(client, root + "/" + failed["id"] + "/control",
        {"action": "retry", "expected_revision": failed["revision"]})
    assert retried.status_code == 200, retried.text
    result = complete(client, service, root, retried.json())
    assert result["status"] == "completed"
    assert [s["id"] for s in result["sources"]] == source_ids
    assert len(calls) == 2 and "sections" in calls[-1]
    assert client.get(route + "/files/" + entry["id"]).content == TEXT.encode()


def test_empty_final_answer_keeps_unresolved_work_in_native_status_and_coverage(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    base = model.complete
    gap = 'The captured originals did not establish the recipient.'

    async def complete_model(system, user, **options):
        if options['response_schema']['title'] == 'Briefing':
            value = json.loads(await base(system, user, **options))
            value.update(findings=[], mission_checkpoint={'answer': {'status': 'not_found', 'points': [], 'limitations': [gap]},
                'action': 'finish', 'reason': 'No supported answer could be established.'})
            return json.dumps(value)
        return await base(system, user, **options)

    monkeypatch.setattr(model, 'complete', complete_model)
    root, run, _ = start(client)
    identifier = run['id']
    route = root + '/investigations/' + identifier
    for _ in range(50):
        tick(service, identifier)
        state = client.get(route).json()
        if state['status'] not in {'queued', 'running'}:
            break
    assert state['exploration']['mission']['answer']['points'] == []
    assert 'did not produce a validated answer' in state['stop_reason']
    assert '0 questions remain' not in state['stop_reason']
    assert state['coverage_manifest']['summary']['open_questions'] >= 1
    assert any(q['question'] == gap for q in state['coverage_manifest']['open_questions'])

    # Adaptive input can remain current while a final checkpoint's own evidence
    # dependency is stale. Its answer and derived gaps must both disappear.
    with service.db.session() as session:
        saved = session.get(Investigation, identifier)
        from copy import deepcopy
        data = deepcopy(saved.research_state)
        data['mission']['checkpoints'][-1]['source_dependencies'][0]['sha256'] = 'f' * 64
        saved.research_state = data
        session.commit()
    changed = client.get(route).json()
    assert changed['exploration']['mission']['answer'] is None
    assert gap not in json.dumps(changed['coverage_manifest']['open_questions'])


@pytest.mark.parametrize('withdraw_before_apply', [False, True])
def test_private_reading_continuation_preserves_checked_answer_and_current_source_fences(signed, withdraw_before_apply):
    from helvetic_lens import product_exploration as exploration
    from helvetic_lens import product_iterative_steps as steps
    from helvetic_lens import product_research_mission as mission
    from helvetic_lens.config import DomainError
    from helvetic_lens.product_investigation_models import (
        InvestigationBranch,
        InvestigationEvent,
        InvestigationSource,
    )
    from helvetic_lens.product_investigations import rows, scope

    client, service, _, _ = signed
    _, started, _ = start(client)
    private = 'Unreviewed intermediate claim cannot become a public finding.'
    with service.db.session() as session:
        run = session.get(Investigation, started['id'])
        run.status = 'running'
        for branch in rows(session, InvestigationBranch, run):
            branch.status = 'completed'
        old = InvestigationSource(**scope(run), source_key='a' * 64, kind='public_source',
            title='Earlier checked original', url='https://example.org/earlier', sha256='a' * 64,
            snapshot={'excerpts': [{'passage': 'p1', 'text': GRANT}]})
        session.add(old)
        session.flush()

        def supplied():
            return {**exploration.prepare(session, run), 'research_mission': mission.context(session, run)}

        evidence = {'source_id': old.id, 'locator': 'p1', 'quote': GRANT}
        checked = mission.schema(exploration.Briefing).model_validate({
            'understanding': 'An earlier checked answer remains available while research continues.',
            'findings': [{**evidence, 'statement': GRANT, 'basis': 'direct'}],
            'uncertainties': [], 'clarification': '', 'directions': [], 'mission_checkpoint': {
                'answer': {'status': 'possible_answer', 'points': [{'statement': GRANT,
                    'evidence': [{**evidence, 'role': 'support'}]}], 'limitations': []},
                'action': 'finish', 'reason': 'The earlier source provides the checked observation.'}})
        exploration.apply(session, run, supplied(), checked)
        mission.apply(session, run, supplied(), checked)
        previous = deepcopy(mission.project(session, run)['answer'])
        briefing = deepcopy(exploration.projection(session, run)['briefing'])
        assert previous is not None and briefing is not None
        mission.update(run, stop=None, stage='synthesizing')
        newer = InvestigationSource(**scope(run), source_key='b' * 64, kind='public_source',
            title='New source with an original lead', url='https://example.org/newer', sha256='b' * 64,
            snapshot={'excerpts': [{'passage': 'p1', 'text': LATE}]})
        session.add(newer)
        branch = InvestigationBranch(**scope(run), query='Evaluate newly read evidence', phase='brief',
            status='running', reason='Decide the useful next reading.', checkpoint={'research_control': True})
        session.add(branch)
        session.flush()
        evidence = {'source_id': newer.id, 'locator': 'p1', 'quote': LATE}
        proposed = checked.model_copy(deep=True)
        proposed.findings[0].statement = private
        proposed.mission_checkpoint.answer.points[0].statement = private
        proposed.mission_checkpoint.reason = private
        proposed.mission_checkpoint.action = 'continue'
        from helvetic_lens.product_iterative_research import Gap
        proposed.mission_checkpoint.next_checks = [Gap(**evidence, question='Does the linked original resolve the revised amount?',
            query='https://example.org/unread-original', purpose='Read the source-linked original.',
            priority=5, kind='independent_verification', catalogues=[])]
        work = {'phase': 'brief', 'token': 'private-reading-step', 'input': supplied(),
            'mission_continuation': mission.continuation_context(session, run)}
        assert mission.route_continuation(work, proposed.mission_checkpoint)
        before_questions = deepcopy(run.research_state['questions'])
        if withdraw_before_apply:
            newer.sha256 = 'c' * 64
            session.flush()
            with pytest.raises(DomainError):
                steps.apply(session, run, branch, {}, work, proposed)
            assert run.research_state['questions'] == before_questions
        else:
            steps.apply(session, run, branch, {}, work, proposed)
            session.flush()
            public = exploration.projection(session, run)
            assert public['mission']['answer'] == previous and public['briefing'] == briefing
            assert len(public['mission']['checkpoints']) == 1
            assert any(q['query'] == 'https://example.org/unread-original' and q['branch_id']
                for q in run.research_state['questions'])
            assert public['mission']['stage'] == 'deepening'
            assert private not in json.dumps(public)
            assert private not in json.dumps([event.detail for event in rows(session, InvestigationEvent, run)])
            assert private not in json.dumps(public['mission']['knowledge'])
            old.sha256 = 'd' * 64
            session.flush()
            assert exploration.projection(session, run)['mission']['answer'] is None


@pytest.mark.parametrize('selection', ['new', 'existing', 'frontier'])
def test_mission_selection_releases_only_chosen_work_across_later_scheduling(signed, selection):
    from helvetic_lens import product_exploration as exploration
    from helvetic_lens import product_iterative_research as research
    from helvetic_lens import product_research_mission as mission
    from helvetic_lens.product_investigation_models import InvestigationBranch, InvestigationSource
    from helvetic_lens.product_investigations import citation, rows, scope

    client, service, _, _ = signed
    _, started, _ = start(client)
    with service.db.session() as session:
        run = session.get(Investigation, started['id'])
        run.status = 'running'
        for branch in rows(session, InvestigationBranch, run):
            branch.status = 'completed'
        source = InvestigationSource(**scope(run), source_key='a' * 64, kind='public_source',
            title='Current original', url='https://example.org/current', sha256='a' * 64,
            snapshot={'excerpts': [{'passage': 'p1', 'text': GRANT}]})
        session.add(source)
        session.flush()
        initial_id = research.add_question(session, run, research.BranchDraft(question='What do the primary records establish?',
            query='primary registry records', purpose='Read the initial originals.', priority=2))
        research.schedule_questions(session, run)
        initial_question = next(q for q in run.research_state['questions'] if q['id'] == initial_id)
        assert initial_question['branch_id'], 'Initial planning remains unrestricted before a mission selection'
        initial_branch = session.get(InvestigationBranch, initial_question['branch_id'])
        initial_branch.status = 'completed'
        initial_branch.checkpoint = {**initial_branch.checkpoint, 'next_discovery_cursors': {'broad': {'page': 2}}}
        research.finish_question(session, run, initial_branch)

        optional_id = research.add_question(session, run, research.BranchDraft(question='What is every historical ranking?',
            query='all historical registry rankings', purpose='Optional exhaustive background.', priority=5))
        optional_before = deepcopy(next(q for q in run.research_state['questions'] if q['id'] == optional_id))
        draft = research.Gap(source_id=source.id, locator='p1', quote=GRANT,
            question='Does the current original resolve the requested discrepancy?', query='current original discrepancy',
            purpose='Resolve the requested distinction.', priority=1, kind='contradiction')
        pin = citation(source, draft)
        existing_id = research.add_question(session, run, draft, trigger={**pin, 'sha256': 'b' * 64}) if selection == 'existing' else None
        supplied = {**exploration.prepare(session, run), 'research_mission': mission.context(session, run)}
        if existing_id:
            from helvetic_lens import product_exploration_followups as followups
            from helvetic_lens import product_informed_research as informed
            informed.remember(session, run, supplied)
            followups.remember_open_context(run, supplied, existing_id)
            old_context = deepcopy(next(q for q in run.research_state['questions'] if q['id'] == existing_id)['open_check_context'])
        checkpoint = mission.Checkpoint(answer={'status': 'partial', 'points': [], 'limitations': ['The discrepancy remains unresolved.']},
            action='continue', reason='Read only the selected material distinction.',
            next_checks=[] if selection == 'frontier' else [draft],
            deepen_branches=[initial_branch.id] if selection == 'frontier' else [])
        work = {'input': supplied, 'mission_continuation': mission.continuation_context(session, run)}
        assert mission.route_continuation(work, checkpoint)
        gaps, deeper = mission.next_work(session, run, supplied, checkpoint)
        assert mission.schedule_next(session, run, supplied, gaps, deeper)
        current_questions = run.research_state['questions']
        assert next(q for q in current_questions if q['id'] == optional_id) == optional_before
        selected_ids = run.research_state['mission']['selected_question_ids']
        if selection == 'frontier':
            assert selected_ids == [] and initial_branch.status == 'running'
        else:
            selected = next(q for q in current_questions if q['query'] == draft.query)
            assert selected['branch_id'] and selected['status'] == 'investigating'
            assert selected['trigger'] == pin
            assert selected_ids == [selected['id']]
            if existing_id:
                from helvetic_lens.product_observed_queries import origin_current
                assert selected['id'] == existing_id
                assert sum(q['query'] == draft.query for q in current_questions) == 1
                assert selected['open_check_context']['fingerprint'] != old_context['fingerprint']
                assert followups.open_context_current(session, run, selected,
                    run.research_state['exploration']['adaptive_dependencies'])
                assert origin_current(session, run, selected), 'The explicitly selected search must retain a current query-journal origin'
        assert 'selected_question_ids' not in mission.project(session, run)
        session.commit()

    with service.db.session() as session:
        run = session.get(Investigation, started['id'])
        before_branches = {branch.id for branch in rows(session, InvestigationBranch, run)}
        # Reflection saves new proposals and invokes this same default scheduler.
        # Neither fresh proposals nor earlier higher-priority optional work may
        # bypass the durable mission decision after another worker transaction.
        later_id = research.add_question(session, run, research.BranchDraft(question='What related statistics could also be collected?',
            query='related statistics background', purpose='A new unselected reflection proposal.', priority=5))
        research.schedule_questions(session, run)
        assert {branch.id for branch in rows(session, InvestigationBranch, run)} == before_branches
        assert next(q for q in run.research_state['questions'] if q['id'] == optional_id) == optional_before
        later = next(q for q in run.research_state['questions'] if q['id'] == later_id)
        assert later['status'] == 'open' and later['branch_id'] is None
        empty = mission.Checkpoint(answer={'status': 'partial', 'points': [], 'limitations': ['The question remains unresolved.']},
            action='continue', reason='Unselected open questions cannot authorize work.')
        work = {'input': {'sources': [], 'research_mission': {}},
            'mission_continuation': mission.continuation_context(session, run)}
        assert not mission.route_continuation(work, empty) and empty.action == 'finish'
