"""Private intermediate proposals, never accepted evidence or a displayed answer."""
from copy import deepcopy

from .product_operations import fingerprint
from .research_reference_metadata import POLICY as SOURCE_USE_POLICY

KEY = "synthesis_checkpoint"
CONTRACT = "final-synthesis-resume/v2"
EXHAUSTED_REVIEW = "exhausted_review"
DEFERRED_ARCHIVE = "deferred_review_checkpoint"
PROVIDER_INTERRUPTION = {"model_rate_limited", "model_temporarily_unavailable", "model_upstream_timeout",
    "model_timeout", "model_unreachable", "model_transport_error"}


def exhausted_review(state):
    """Only a terminal, exact-input final review with spent native retries qualifies."""
    saved = state.get(EXHAUSTED_REVIEW)
    if isinstance(saved, dict) and saved.get("input_fingerprint") and saved.get("reason") in PROVIDER_INTERRUPTION:
        return deepcopy(saved)
    checkpoint = state.get(KEY, {})
    steps = state.get("steps", [])
    if checkpoint.get("stage") != "finalizing" or not steps or steps[-1].get("status") != "unavailable":
        return None
    execution = steps[-1].get("execution", {})
    binding = execution.get("evidence_transport", {}).get("input_fingerprint")
    if not binding or state.get("provider_retries", {}).get(binding, 0) < 3:
        return None
    reason = next((step.get("error_code") for step in reversed(steps)
        if step.get("phase") == "brief" and step.get("execution", {}).get("evidence_transport", {}).get("input_fingerprint") == binding
        and step.get("error_code") in PROVIDER_INTERRUPTION), None)
    if reason:
        return {"input_fingerprint": binding, "checkpoint_binding": checkpoint.get("binding"), "reason": reason}
    return None


def deferred_verification(checkpoint):
    """Safe public workflow status; private assertions never enter this projection."""
    from .research_final_review import DEFERRED_NOTICE

    deferred = (checkpoint or {}).get("parts", {}).get("deferred_final_review", {})
    pending = deferred.get("pending_checks", [])
    if deferred.get("status") != "qualified_delivery" or not pending:
        return None
    reasons = sorted({item.get("reason") for item in pending
        if isinstance(item, dict) and item.get("reason") in PROVIDER_INTERRUPTION | {"step_deadline", "not_completed", "model_incomplete"}})
    return {"status": "partial", "pending_checks": len(pending), "reasons": reasons,
        "basis": DEFERRED_NOTICE}


def completed_work(checkpoint):
    """Only retained validated proposals/checks count toward another work step."""
    parts = (checkpoint or {}).get("parts", {})
    progress = {field + ":" + key: value[field]
        for key, value in parts.items() if isinstance(value, dict)
        for field in ("selected", "proposal") if field in value}
    progress.update({"review:" + key: value for key, value in parts.get("final_reviews", {}).items()
        if key.startswith("clauses:")})
    progress.update({"point_decision:" + key: value for key, value in parts.get("point_decisions", {}).items()
        if isinstance(value, dict) and value.get("choice") in {"supported", "contradicted", "not_established"}
        and value.get("input_fingerprint") and value.get("policy_fingerprint")})
    progress.update({"request_coverage:" + key: value for key, value in parts.get("delivered_coverage", {}).items()
        if isinstance(value, dict) and value.get("choice") in {"covered", "missing"}
        and value.get("input_fingerprint") and value.get("policy_fingerprint")})
    selections = {
        "evidence_selection:": parts.get("evidence_selection", {}),
        "review_evidence_selection:": parts.get("final_reviews", {}).get("original_selection", {}).get("evidence_selection", {}),
    }
    for prefix, nodes in selections.items():
        # Learning a faster lookup identity is cache bookkeeping, not new work.
        progress.update({prefix + key: {field: item for field, item in value.items() if field != 'envelope_fingerprint'}
            for key, value in nodes.items()
            if isinstance(value, dict) and value.get("status") == "complete"
            and value.get("input_fingerprint") and value.get("policy_fingerprint")
            and isinstance(value.get("selected"), list)
            and all(type(ref) is int and ref > 0 for ref in value["selected"])
            and len(value["selected"]) == len(set(value["selected"]))})
    return deepcopy(progress)


def made_progress(previous, current):
    """Removing stale work or changing accounting cannot renew retries."""
    return any(key not in previous or value != previous[key] for key, value in current.items())


class DraftCheckpoint:
    def __init__(self, work, settings, system, review_system, schema, content, options, *, preparation_policy=None):
        from .research_answer_parts import POLICY
        from .research_final_review import POLICY as FINAL_POLICY
        self.work = work
        self.binding = fingerprint({"contract": CONTRACT, "system": system,
            "part_policy": POLICY, "final_policy": FINAL_POLICY,
            "review_system": review_system, "schema": schema, "content": content,
            "preparation_policy": preparation_policy,
            "source_use_policy": SOURCE_USE_POLICY,
            "provider": settings.apertus_provider, "endpoint": settings.apertus_base_url,
            "model": settings.apertus_model, "options": options,
            "generation": {key: getattr(settings, key) for key in (
                "apertus_temperature", "apertus_top_p", "apertus_presence_penalty",
                "apertus_reasoning_effort", "apertus_json_mode", "apertus_product_id")}})
        self.request_binding = fingerprint({"schema": schema, "content": content})
        saved = work.pop(KEY, None)
        self.value = deepcopy(saved) if (isinstance(saved, dict) and saved.get("binding") == self.binding
            and saved.get("stage") in {"preparing", "draft", "reviewed", "finalizing"}
            and isinstance(saved.get("raw", ""), str)
            and (saved.get("stage") == "preparing" or isinstance(saved.get("raw"), str))
            and saved.get("fingerprint") == fingerprint({k: v for k, v in saved.items() if k != "fingerprint"})) else None
        if self.value:
            self.request_binding = self.value.get("request_binding", self.request_binding)
            work[KEY] = self.value
        self.parts = deepcopy(self.value.get("parts", {})) if self.value else {}

    def bind_request(self, schema, content, *, system=None):
        """A saved answer belongs to the exact selected evidence shown to its author."""
        self.request_binding = fingerprint({"schema": schema, "content": content,
            **({"system": system} if system is not None else {})})
        if (self.value and self.value["stage"] != "preparing"
                and self.value.get("request_binding") != self.request_binding):
            # Keep reusable selection work, never checks of a different draft.
            self.parts = {key: value for key, value in self.parts.items() if key == "evidence_selection"}
            self.value = None
            self.work.pop(KEY, None)

    def save(self, stage, raw, hints, review):
        value = {"contract": CONTRACT, "binding": self.binding, "stage": stage,
            "request_binding": self.request_binding,
            "raw": raw, "hints": deepcopy(hints), "review": deepcopy(review), "parts": deepcopy(self.parts)}
        self.value = {**value, "fingerprint": fingerprint(value)}
        self.work[KEY] = self.value
