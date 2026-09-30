"""Bounded renewal selection and coexistence with a selected continuation answer."""

import json
from types import SimpleNamespace

from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_episode_progress import extra_source
from test_product_exploration import adapters
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_question_assessment import assessment_adapters
from test_product_question_renewal import configured
from test_product_saved_check import command, url

from helvetic_lens import product_branch_assessment as assessment
from helvetic_lens import product_question_renewal as renewal
from helvetic_lens.product_investigation_models import Investigation


def test_selection_prefers_outdated_then_priority_and_bounds_context(monkeypatch):
    monkeypatch.setattr(renewal, "enabled", lambda run: True)
    monkeypatch.setattr(renewal.exploration, "sources", lambda session, run: {"s": None, "later": None})
    monkeypatch.setattr(
        assessment,
        "receipt_current",
        lambda session, run, q, **kwargs: kwargs.get("allow_public_progress") or not q.get("outdated"),
    )
    monkeypatch.setattr(assessment, "target", lambda run, branch: {"question_id": branch.id})
    session = SimpleNamespace(get=lambda model, identifier: SimpleNamespace(id=identifier))

    def q(identifier, priority, *, outdated=False, status="partial", supplied=None):
        return {
            "id": identifier,
            "branch_id": identifier,
            "priority": priority,
            "created_at": identifier,
            "completed_at": "saved",
            "outdated": outdated,
            "branch_assessment": {"supplied_source_ids": supplied or ["s"], "assessment": {"status": status}},
        }

    run = SimpleNamespace(
        research_state={
            "questions": [
                q("low", 1),
                q("high", 9),
                q("outdated", 0, outdated=True),
                q("middle", 5),
                q("resolved", 99, status="possible_answer"),
                q("no-new-source", 100, supplied=["s", "later"]),
            ]
        }
    )
    chosen = renewal.targets(session, run)
    assert [v["question_id"] for v in chosen] == ["outdated", "high", "middle"]
    assert len(chosen) == 3


def test_selected_answer_and_current_branch_renewal_have_distinct_targets(signed, monkeypatch):
    client, service, _, model = signed
    root, run, trace, _, _ = configured(signed, monkeypatch)
    parent = complete(client, service, root + "/investigations", run)
    trace = adapters(monkeypatch, service, model)
    assessment_adapters(monkeypatch, model, trace, parent, "partial")
    base = model.complete
    observed = []

    async def respond(system, user, **kwargs):
        raw = json.loads(await base(system, user, **kwargs))
        data = json.loads(user)
        target = data.get("branch_assessment_question")
        if kwargs["response_schema"]["title"] == "Reflection" and target:
            s = data["sources"][0]
            raw["assessment"] = {
                "question_id": target["question_id"],
                "status": "partial",
                "points": [
                    {
                        "statement": "The current read leaves the exact question open.",
                        "evidence": [
                            {
                                "source_id": s["id"],
                                "quote": s["excerpts"][0]["text"],
                                "locator": "p1",
                                "role": "context",
                            }
                        ],
                    }
                ],
                "limitations": ["Additional context remains to be assessed."],
            }
        if kwargs["response_schema"]["title"] == "Briefing" and data.get("question_renewal_targets"):
            observed.append(data)
            s = data["sources"][0]
            raw["question_renewals"] = [
                {
                    "question_id": data["question_renewal_targets"][0]["question_id"],
                    "status": "partial",
                    "points": [
                        {
                            "statement": "The read sources still leave the selected issue uncertain.",
                            "evidence": [
                                {
                                    "source_id": s["id"],
                                    "quote": s["excerpts"][0]["text"],
                                    "locator": "p1",
                                    "role": "context",
                                }
                            ],
                        }
                    ],
                    "limitations": ["No conclusive reconciliation in the retained passages."],
                }
            ]
        return json.dumps(raw)

    monkeypatch.setattr(model, "complete", respond)
    child = post(client, url(root, parent), command(parent)).json()
    tick(service, child["id"])
    with service.db.session() as session:
        extra_source(session, session.get(Investigation, child["id"]))
        session.commit()
    final = complete(client, service, root + "/investigations", child)
    assert observed and final["exploration"]["status"] == "ready", final["stop_reason"]
    selected = final["exploration"]["briefing"]["assessment"]["question_id"]
    current = final["exploration"]["question_assessments"]["assessments"][0]
    assert selected == parent["exploration"]["next_check"]["question_id"]
    assert current["question_id"] != selected and current["stage"] == "final_briefing"
    assert current["earlier"] and current["status"] == "partial"
