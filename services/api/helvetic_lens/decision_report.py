"""Evidence-bound review drafts. Citation integrity is not legal entailment."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import DomainError
from .extraction import normalize

CONTRACT = "decision-draft-v1"
Number = Annotated[int, Field(ge=1)]
ActionType = Literal[
    "legal_review", "policy_review", "process_review", "deadline_check", "monitor_follow_up", "other"
]


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class ChangeExplanation(Draft):
    change_number: Number
    explanation: str = Field(min_length=1, max_length=900)
    citation_numbers: list[Number] = Field(min_length=1, max_length=4)


class Applicability(Draft):
    status: Literal["applies", "may_apply", "unlikely", "unknown"]
    explanation: str = Field(min_length=1, max_length=900)
    conditions: list[Annotated[str, Field(min_length=1, max_length=400)]] = Field(max_length=4)
    activity_numbers: list[Number] = Field(max_length=6)
    citation_numbers: list[Number] = Field(max_length=6)


class OfficialStatus(Draft):
    status: Literal["proposal", "enacted", "repealed", "mixed", "unknown"]
    explanation: str = Field(min_length=1, max_length=600)
    citation_numbers: list[Number] = Field(max_length=4)


class ActionReview(Draft):
    status: Literal["review_actions", "no_action_now", "not_reviewed"]
    explanation: str = Field(min_length=1, max_length=800)
    citation_numbers: list[Number] = Field(max_length=6)


class DecisionAction(Draft):
    action_type: ActionType
    activity_number: Number
    # Smallest exact source phrase describing the underlying obligation/topic.
    # A title paraphrase cannot create a new action for the same source anchor.
    obligation_citation: Number
    obligation_quote: str = Field(min_length=8, max_length=500)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=800)
    applicability_condition: str = Field(min_length=1, max_length=500)
    priority: Literal["high", "medium", "low"]
    citation_numbers: list[Number] = Field(min_length=1, max_length=6)


class DecisionDraft(Draft):
    summary: str = Field(min_length=1, max_length=1800)
    impact: Literal["high", "medium", "low", "unknown"]
    reason: str = Field(min_length=1, max_length=1200)
    citation_numbers: list[Number] = Field(min_length=1, max_length=10)
    changes: list[ChangeExplanation] = Field(min_length=1, max_length=8)
    applicability: Applicability
    official_status: OfficialStatus
    action_review: ActionReview
    actions: list[DecisionAction] = Field(max_length=5)
    uncertainties: list[Annotated[str, Field(min_length=1, max_length=400)]] = Field(max_length=5)

    @model_validator(mode="after")
    def consistent_review(self):
        if bool(self.actions) != (self.action_review.status == "review_actions"):
            raise ValueError(
                "review_actions requires actions; no_action_now/not_reviewed require an empty action list."
            )
        if self.action_review.status != "not_reviewed" and not self.action_review.citation_numbers:
            raise ValueError("An action review requires supporting citations.")
        if self.applicability.status != "unknown" and (
            not self.applicability.citation_numbers or not self.applicability.activity_numbers
        ):
            raise ValueError(
                "Organization applicability requires actual activity references and legal evidence."
            )
        if self.applicability.status in {"applies", "may_apply"} and not self.applicability.conditions:
            raise ValueError(
                "Explain the conditions under which the cited scope affects the supplied activities."
            )
        if self.official_status.status != "unknown" and not self.official_status.citation_numbers:
            raise ValueError(
                "A status interpretation requires source evidence; a URL or document title is insufficient."
            )
        if self.action_review.status == "no_action_now" and self.applicability.status == "unknown":
            raise ValueError("Unknown applicability cannot establish no_action_now.")
        return self


def decision_catalogs(
    citations: list[dict], evidence: list[dict], activities: list[str]
) -> tuple[list, list]:
    by_passage = {(row["version_id"], row["passage_id"]): row for row in evidence}
    grouped = {}
    for number, citation in enumerate(citations, 1):
        row = by_passage.get((citation["version_id"], citation["passage_id"]), {})
        change_id = row.get("change_id")
        if change_id:
            grouped.setdefault(change_id, []).append(number)
    changes = [
        {
            "number": number,
            "change_id": key,
            "citation_numbers": numbers,
            "citation_sides": {
                str(index): by_passage[
                    (citations[index - 1]["version_id"], citations[index - 1]["passage_id"])
                ]["side"]
                for index in numbers
            },
        }
        for number, (key, numbers) in enumerate(grouped.items(), 1)
    ]
    activity_catalog = [{"number": number, "text": text} for number, text in enumerate(activities, 1)]
    return changes, activity_catalog


def validate_draft(
    result: dict, citations: list[dict], changes: list[dict], activities: list[dict], coverage: dict
) -> dict:
    def reject(message, code="invalid_citation"):
        raise DomainError(message, 502, code)

    def check_refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "citation_numbers" and any(
                    number < 1 or number > len(citations) for number in child
                ):
                    reject("A decision claim cites evidence outside this synthesis catalog.")
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    check_refs(result)
    by_change = {item["number"]: item for item in changes}
    known_activities = {item["number"] for item in activities}
    seen = set()
    for claim in result["changes"]:
        number = claim["change_number"]
        if number not in by_change or number in seen:
            reject("Explain each supplied change at most once, using its exact change_number.")
        seen.add(number)
        if not set(claim["citation_numbers"]).issubset(by_change[number]["citation_numbers"]):
            reject("A change explanation cites another legal unit instead of that change's saved evidence.")
        sides = by_change[number]["citation_sides"]
        if set(sides.values()) == {"old", "new"} and {
            sides[str(ref)] for ref in claim["citation_numbers"]
        } != {"old", "new"}:
            reject("Cite both supplied version sides when explaining a before/after change.")
    if not set(result["applicability"]["activity_numbers"]).issubset(known_activities):
        reject("Applicability names an activity not supplied by the organization.", "invalid_model_output")
    if result["action_review"]["status"] == "no_action_now" and (
        coverage.get("limited") or seen != set(by_change)
        or len(seen) < int(coverage.get("material_items", len(changes)))
    ):
        reject(
            "Partial review cannot establish no_action_now for the comparison. Use not_reviewed and explain the remaining scope.",
            "invalid_model_output",
        )
    for action in result["actions"]:
        number = action["obligation_citation"]
        if number not in action["citation_numbers"] or not 1 <= number <= len(citations):
            reject("An action must cite its exact obligation anchor from this catalog.")
        if action["obligation_quote"] not in citations[number - 1]["quote"]:
            reject(
                "The obligation anchor must be an exact substring of its supplied citation, not a paraphrase."
            )
        if action["activity_number"] not in known_activities:
            reject(
                "An action targets an activity absent from the organization profile.", "invalid_model_output"
            )
    return result


def materialize_decision(
    draft: dict, citations: list[dict], changes: list[dict], activities: list[dict], copy: dict
) -> dict:
    """Use only already validated references; never take provider URLs or owners."""

    def selected(numbers):
        return [citations[number - 1] for number in dict.fromkeys(numbers)]

    by_change = {item["number"]: item for item in changes}
    by_activity = {item["number"]: item["text"] for item in activities}
    applicability = draft["applicability"]
    official = draft["official_status"]
    action_review = draft["action_review"]
    actions = {}
    for candidate in draft["actions"]:
        anchor = citations[candidate["obligation_citation"] - 1]
        area = by_activity[candidate["activity_number"]]
        identity = {
            "contract": CONTRACT,
            "version_id": anchor["version_id"],
            "passage_id": anchor["passage_id"],
            "obligation": normalize(candidate["obligation_quote"]),
            "activity": area,
            "action_type": candidate["action_type"],
        }
        key = (
            "act_"
            + hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[
                :20
            ]
        )
        resolved = selected(candidate["citation_numbers"])
        change_ids = [
            item["change_id"]
            for item in changes
            if set(item["citation_numbers"]) & set(candidate["citation_numbers"])
        ]
        if key in actions:
            item = actions[key]
            priority = {"low": 0, "medium": 1, "high": 2}
            item["priority"] = max((item["priority"], candidate["priority"]), key=priority.get)
            item["citations"] = list(
                {
                    (value["version_id"], value["passage_id"], value["quote"]): value
                    for value in item["citations"] + resolved
                }.values()
            )[:6]
            item["related_change_ids"] = sorted(set(item["related_change_ids"] + change_ids))[:12]
            continue
        actions[key] = {
            **{
                name: candidate[name]
                for name in (
                    "action_type",
                    "title",
                    "text",
                    "rationale",
                    "applicability_condition",
                    "priority",
                )
            },
            "action_key": key,
            "owner_role": copy["unassigned"],
            "affected_area": area,
            "due_basis": "not_reviewed",
            "due_date": None,
            "related_change_ids": change_ids[:12],
            "evidence_grade": "possible",
            "review_suggestion": True,
            "citations": resolved,
            "obligation_anchor": {"quote": candidate["obligation_quote"], "citation": anchor},
        }
    return {
        "summary": draft["summary"],
        "impact": draft["impact"],
        "reason": draft["reason"],
        "citations": selected(draft["citation_numbers"]),
        "actions": list(actions.values()),
        "business_areas": [
            by_activity[number] for number in dict.fromkeys(applicability["activity_numbers"])
        ],
        "organization_applicability": {
            "status": applicability["status"],
            "explanation": applicability["explanation"],
            "conditions": applicability["conditions"],
            "evidence_grade": "possible" if applicability["status"] != "unknown" else "needs_review",
            "citations": selected(applicability["citation_numbers"]),
        },
        "official_status": {
            **{key: official[key] for key in ("status", "explanation")},
            "basis": "model_interpretation",
            "citations": selected(official["citation_numbers"]),
        },
        "action_review": {
            **{key: action_review[key] for key in ("status", "explanation")},
            "citations": selected(action_review["citation_numbers"]),
        },
        "change_explanations": {
            by_change[item["change_number"]]["change_id"]: {
                "explanation": item["explanation"],
                "citations": selected(item["citation_numbers"]),
            }
            for item in draft["changes"]
        },
        "uncertainties": draft["uncertainties"],
        "decision_review": {
            "contract": CONTRACT,
            "basis": "model_interpretation",
            "available_changes": len(changes),
            "explained_changes": len(draft["changes"]),
            "merged_actions": len(draft["actions"]) - len(actions),
        },
    }
