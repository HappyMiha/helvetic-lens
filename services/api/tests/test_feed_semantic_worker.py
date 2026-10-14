"""Semantic planning, full-original judgments and durable refinement recovery."""
from copy import deepcopy

import pytest
from sqlalchemy import func, select
from test_feed_worker import URL, create, downloads, finish, next_check, step
from test_feed_worker import semantic_models as semantic_models
from test_legal_profiles import signed as signed

from helvetic_lens import decision_search, feed_intelligence
from helvetic_lens.feed_models import Feed, FeedAssessment, FeedCheck, FeedUpdate
from helvetic_lens.models import Job


def planned(specification, queries):
    return {"contract": feed_intelligence.CONTRACT, "binding": specification["binding"],
        "feed_revision": specification["feed_revision"], "status": "ready",
        "understanding": "Protection of a person displaced by conflict.",
        "relevance_scope": "Include the meaning of temporary protection and residence rights for people displaced by conflict. Preserve uncertainty.",
        "concepts": ["temporary protection", "residence rights"], "synonyms": ["Schutzstatus"],
        "queries": [{"query": query, "language": language, "purpose": "Find related primary evidence"}
            for query, language in queries]}


def judgment(verdict):
    return {"verdict": verdict, "engine": "laya", "model": "test-local-laya", "confidence": .8}


def test_multilingual_directions_finish_every_cursor_preserve_broad_sources_and_reuse_plan(signed, monkeypatch):
    _, service, identity = signed
    service.settings = service.settings.model_copy(update={"web_search_provider": "searxng"})
    plans, pages = [], []
    queries = [("temporary protection residence rights", "en"), ("Schutzstatus Aufenthalt", "de")]
    values = {URL: ("text/plain", b"An explicit public original.")}
    for index in range(4):
        values[URL + f"/{index}"] = ("text/plain", f"Unique saved original {index}.".encode())
    calls = downloads(monkeypatch, values)

    async def prepare(service, specification):
        plans.append(specification)
        return planned(specification, queries)

    async def retrieve(settings, query, index, depth, product, **kwargs):
        assert settings.web_search_provider == "searxng" and kwargs["selected_catalogues"] == ["fedlex"]
        assert kwargs["complete_page"]
        q = [value[0] for value in queries].index(query)
        page = int(bool(kwargs["cursors"]))
        pages.append((query, page))
        return {"status": "partial" if q == 0 else "complete",
            "lanes": [{"name": "broad", "status": "unavailable" if q == 0 else "complete"}],
            "items": [{"url": URL, "title": "Already collected", "summary": ""},
                {"url": URL + f"/{q * 2 + page}", "title": "Original", "summary": "Publisher preview"}],
            "next_cursors": None if page else {"fedlex": "same-cursor-in-each-query"}}

    monkeypatch.setattr(feed_intelligence, "prepare", prepare)
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    identifier, job_id = create(service, identity, [URL, "fedlex"])
    finish(service, job_id)
    assert pages == [(q, p) for q, _ in queries for p in (0, 1)]
    assert len(calls) == 5 and len(set(calls)) == 5
    finish(service, next_check(service, identifier))
    assert len(plans) == 1, "An unchanged authorized semantic plan must be reusable"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 5
        assert session.scalar(select(func.count()).select_from(FeedAssessment)) == 5
        receipts = session.scalar(select(FeedCheck).where(FeedCheck.job_id == job_id)).receipts_json
        assert {row["language"] for row in receipts["coverage"] if "language" in row} == {"en", "de"}
        assert receipts["semantic_counts"] == {"relevant": 5}


@pytest.mark.parametrize("tail,reading_complete,expected", [("relevant", True, "relevant"),
    ("unrelated", True, "unrelated"), ("unrelated", False, "uncertain")])
def test_relevance_reaches_original_tail_and_exclusion_requires_complete_reading(signed, monkeypatch, tail, reading_complete, expected):
    _, service, identity = signed
    from helvetic_lens import feed_sources

    body = "A" * 4000 + "B" * 4000 + "THE RELEVANT CONCLUSION IN ANOTHER LANGUAGE"
    downloads(monkeypatch, {URL: ("text/plain", body.encode())})
    portions = []
    original = feed_sources.read

    async def read(*args, **kwargs):
        result = await original(*args, **kwargs)
        if not reading_complete:
            result["warnings"] = ["An unreadable image remains in the original"]
        return result

    async def evaluate(settings, specification, plan, item):
        portions.append(item["source_text"])
        assert 0 < len(item["source_text"]) <= feed_intelligence.GATE_CHARACTERS
        assert feed_intelligence.gate_fits(feed_intelligence.gate_state(specification, plan, item, item["source_text"]), plan)
        return judgment(tail if "THE RELEVANT" in item["source_text"] else "unrelated")
    monkeypatch.setattr(feed_sources, "read", read)
    monkeypatch.setattr(feed_intelligence, "evaluate", evaluate)
    _, job_id = create(service, identity)
    finish(service, job_id)
    with service.db.session() as session:
        retained = session.scalar(select(FeedUpdate)).source_text
        assert "".join(portions) == retained and retained.replace("\n", "") == body
        row = session.scalar(select(FeedAssessment))
        assert row.verdict == expected
        assert row.decision_json["assessed_characters"] == len(retained)
        assert row.decision_json["reading_complete"] is reading_complete
        assert len(row.decision_json["portions"]) >= 3


def test_unavailable_laya_preserves_other_sources_and_resumes_successful_prefix_next_check(signed, monkeypatch):
    _, service, identity = signed
    other = URL + "/other"
    body = "A" * 4000 + "B" * 4000 + "C" * 90
    values = {URL: ("text/plain", body.encode()), other: ("text/plain", b"Independent original")}
    downloads(monkeypatch, values)
    seen, unavailable = [], True

    async def evaluate(settings, specification, plan, item):
        nonlocal unavailable
        text = item["source_text"]
        seen.append((item["url"], text))
        if item["url"] == URL and len([v for v in seen if v[0] == URL]) == 2 and unavailable:
            unavailable = False
            return {"verdict": "unavailable", "engine": None, "error": "local_model_offline"}
        return judgment("relevant" if "C" in text or text.startswith("Independent") else "unrelated")
    monkeypatch.setattr(feed_intelligence, "evaluate", evaluate)
    identifier, job_id = create(service, identity, [URL, other])
    finish(service, job_id)
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedAssessment).order_by(FeedAssessment.created_at)))
        assert [row.verdict for row in rows] == ["unavailable", "relevant"]
        assert rows[0].decision_json["continuation"]["offset"] == len(seen[0][1])
        assert rows[0].decision_json["assessed_characters"] == len(seen[0][1])
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 2
        retained = session.scalar(select(FeedUpdate).where(FeedUpdate.url == URL)).source_text
    assert [v[0] for v in seen] == [URL, URL, other]
    # Original host failure cannot prevent reclassification of already saved bytes.
    values[URL] = OSError("Publisher temporarily offline")
    finish(service, next_check(service, identifier))
    assert [v[0] for v in seen[:3]] == [URL, URL, other] and all(v[0] == URL for v in seen[3:])
    assert seen[1] == seen[3] and seen[0][1] + "".join(v[1] for v in seen[3:]) == retained
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedAssessment).order_by(FeedAssessment.created_at)))
        assert len(rows) == 3 and rows[-1].verdict == "relevant"
        assert rows[-1].decision_json["assessed_characters"] == len(retained)
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 2


def test_refinement_replans_and_reassesses_existing_history_without_rewriting_originals(signed, monkeypatch):
    _, service, identity = signed
    values = {URL: ("text/plain", b"Version one retained evidence")}
    calls = downloads(monkeypatch, values)
    specifications = []

    async def prepare(service, specification):
        specifications.append(deepcopy(specification))
        return planned(specification, [("related public research", "en"), ("verwandte Forschung", "de")])

    async def evaluate(settings, specification, plan, item):
        return judgment("unrelated" if specification["feedback"] else "relevant")
    monkeypatch.setattr(feed_intelligence, "prepare", prepare)
    monkeypatch.setattr(feed_intelligence, "evaluate", evaluate)
    identifier, job_id = create(service, identity)
    finish(service, job_id)
    values[URL] = ("text/plain", b"Version two retained evidence")
    finish(service, next_check(service, identifier))
    with service.db.session() as session:
        original_rows = list(session.scalars(select(FeedUpdate).order_by(FeedUpdate.sequence)))
        original = [(row.id, row.source_text, deepcopy(row.snapshot_json)) for row in original_rows]
        feed = session.get(Feed, identifier)
        feed.sources_json = []  # Both versions are absent from the current discovery results.
        feed.revision += 1
        feed.config_json = {"intelligence": {"exclude": ["Previous interpretation"], "feedback": [
            {"update_id": original_rows[0].id, "verdict": "unrelated", "title": original_rows[0].title,
                "url": original_rows[0].url, "summary": "Public example unrelated to the intended problem"}]}}
        session.commit()
    finish(service, next_check(service, identifier))
    assert len(specifications) == 2 and specifications[-1]["feedback"]
    assert len(calls) == 2
    with service.db.session() as session:
        rows = list(session.scalars(select(FeedUpdate).order_by(FeedUpdate.sequence)))
        assert [(row.id, row.source_text, row.snapshot_json) for row in rows] == original
        assessments = list(session.scalars(select(FeedAssessment).order_by(FeedAssessment.created_at)))
        assert [row.verdict for row in assessments] == ["relevant", "relevant", "unrelated", "unrelated"]
        assert len({row.spec_binding for row in assessments}) == 2


def test_planning_failure_collects_originals_but_does_not_invent_semantic_relevance(signed, monkeypatch):
    _, service, identity = signed
    downloads(monkeypatch, {URL: ("text/plain", b"Public legislative changes exact repeated query words")})
    queries = []

    async def unavailable(service, specification):
        return {"status": "unavailable", "error": "semantic_plan_unavailable"}

    async def retrieve(settings, query, *args, **kwargs):
        queries.append(query)
        return {"status": "complete", "items": [], "next_cursors": None}
    monkeypatch.setattr(feed_intelligence, "prepare", unavailable)
    monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    _, job_id = create(service, identity)
    finish(service, job_id)
    assert queries == ["Public legislative changes"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedUpdate)) == 1
        assessment = session.scalar(select(FeedAssessment))
        assert assessment.verdict == "unavailable" and assessment.decision_json["assessed_characters"] == 0
        check = session.scalar(select(FeedCheck))
        assert check.status == "partial" and check.receipts_json["search_plan"]["status"] == "unavailable"


@pytest.mark.parametrize("phase", ["plan", "gate"])
def test_semantic_provider_result_cannot_commit_after_feedback_changes_feed(signed, monkeypatch, phase):
    _, service, identity = signed
    downloads(monkeypatch, {URL: ("text/plain", b"Retained public evidence")})
    identifier, job_id = create(service, identity)

    def refine():
        with service.db.session() as session:
            feed = session.get(Feed, identifier)
            feed.revision += 1
            feed.config_json = {"intelligence": {"exclude": ["Changed scope"]}}
            session.commit()

    async def prepare(service, specification):
        refine()
        return planned(specification, [("old scope query", "en"), ("old related concept", "en")])

    async def evaluate(settings, specification, plan, item):
        refine()
        return judgment("relevant")
    if phase == "plan":
        monkeypatch.setattr(feed_intelligence, "prepare", prepare)
    else:
        monkeypatch.setattr(feed_intelligence, "evaluate", evaluate)
        step(service, job_id)  # Plan
        step(service, job_id)  # Original
    assert step(service, job_id)["state"] == "cancelled"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(FeedAssessment)) == 0
        assert "cached_plan" not in session.get(Feed, identifier).config_json["intelligence"]
        assert session.get(Job, job_id).state == "cancelled"
