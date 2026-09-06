"""Synthetic decision drafts; no legal judgment or model approval."""


def decision_draft(payload):
    change = payload["change_catalog"][0]
    numbers = change["citation_numbers"][:4]
    has_activity = bool(payload["activity_catalog"])
    result = {
        "summary": "Synthetic explanation: the retention wording changed.",
        "impact": "low",
        "reason": "Inspect the cited retention wording before updating the schedule.",
        "citation_numbers": numbers,
        "changes": [
            {
                "change_number": change["number"],
                "explanation": "The selected wording changes the retention review.",
                "citation_numbers": numbers,
            }
        ],
        "applicability": {
            "status": "may_apply" if has_activity else "unknown",
            "explanation": "Check whether the organization's records fall within this clause.",
            "conditions": ["If the organization processes the records described in the cited clause."]
            if has_activity
            else [],
            "activity_numbers": [1] if has_activity else [],
            "citation_numbers": numbers if has_activity else [],
        },
        "official_status": {
            "status": "unknown",
            "explanation": "These excerpts do not establish the official legal status.",
            "citation_numbers": [],
        },
        "action_review": {
            "status": "review_actions" if has_activity else "not_reviewed",
            "explanation": "Compare the retention schedule with the cited scope before changing a process.",
            "citation_numbers": numbers,
        },
        "actions": [],
        "uncertainties": ["The actual organizational record categories need confirmation."],
    }
    if has_activity:
        anchor = next(item for item in payload["citation_catalog"] if item["number"] == numbers[0])
        result["actions"] = [
            {
                "action_type": "policy_review",
                "activity_number": 1,
                "obligation_citation": numbers[0],
                "obligation_quote": anchor["quote"],
                "title": "Compare the retention schedule with the changed clause",
                "text": "Check the records covered by the current schedule and record any mismatch with this clause.",
                "rationale": "A difference in the covered records or retention period may require a schedule update.",
                "applicability_condition": "Only if these records fall within the cited scope.",
                "priority": "low",
                "citation_numbers": numbers,
            }
        ]
    return result
