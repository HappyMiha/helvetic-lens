"""Private intermediate proposals, never accepted evidence or a displayed answer."""
from copy import deepcopy

from .product_operations import fingerprint

KEY = "synthesis_checkpoint"
CONTRACT = "final-synthesis-resume/v1"


def completed_work(checkpoint):
    """Only retained validated proposals/checks count toward another work step."""
    parts = (checkpoint or {}).get("parts", {})
    progress = {field + ":" + key: value[field]
        for key, value in parts.items() if isinstance(value, dict)
        for field in ("selected", "proposal") if field in value}
    progress.update({"review:" + key: value for key, value in parts.get("final_reviews", {}).items()
        if key.startswith("clauses:")})
    return deepcopy(progress)


def made_progress(previous, current):
    """Removing stale work or changing accounting cannot renew retries."""
    return any(key not in previous or value != previous[key] for key, value in current.items())


class DraftCheckpoint:
    def __init__(self, work, settings, system, review_system, schema, content, options):
        from .research_answer_parts import POLICY
        from .research_final_review import POLICY as FINAL_POLICY
        self.work = work
        self.binding = fingerprint({"contract": CONTRACT, "system": system,
            "part_policy": POLICY, "final_policy": FINAL_POLICY,
            "review_system": review_system, "schema": schema, "content": content,
            "provider": settings.apertus_provider, "endpoint": settings.apertus_base_url,
            "model": settings.apertus_model, "options": options,
            "generation": {key: getattr(settings, key) for key in (
                "apertus_temperature", "apertus_top_p", "apertus_presence_penalty",
                "apertus_reasoning_effort", "apertus_json_mode", "apertus_product_id")}})
        saved = work.pop(KEY, None)
        self.value = deepcopy(saved) if (isinstance(saved, dict) and saved.get("binding") == self.binding
            and saved.get("stage") in {"draft", "reviewed"} and isinstance(saved.get("raw"), str)
            and saved.get("fingerprint") == fingerprint({k: v for k, v in saved.items() if k != "fingerprint"})) else None
        if self.value:
            work[KEY] = self.value
        self.parts = deepcopy(self.value.get("parts", {})) if self.value else {}

    def save(self, stage, raw, hints, review):
        value = {"contract": CONTRACT, "binding": self.binding, "stage": stage,
            "raw": raw, "hints": deepcopy(hints), "review": deepcopy(review), "parts": deepcopy(self.parts)}
        self.value = {**value, "fingerprint": fingerprint(value)}
        self.work[KEY] = self.value
