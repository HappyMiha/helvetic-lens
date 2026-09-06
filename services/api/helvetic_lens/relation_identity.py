"""Identity and direction checks; these do not establish semantic entailment."""

from collections.abc import Mapping


def relation_direction(relation, source_work_id: str, target_work_id: str) -> str | None:
    if relation is None or not source_work_id or not target_work_id or source_work_id == target_work_id:
        return None

    def value(field):
        return relation.get(field) if isinstance(relation, Mapping) else getattr(relation, field, None)

    subject, object_ = value("subject_work_id"), value("object_work_id")
    if subject == source_work_id and object_ == target_work_id:
        return "outgoing"
    if subject == target_work_id and object_ == source_work_id:
        return "incoming"
    return None
