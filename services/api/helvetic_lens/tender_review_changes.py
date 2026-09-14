"""Bounded chronological review window; never a net semantic interpretation."""

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select

from .config import DomainError
from .simap_sources import aware
from .tender_models import TenderDossierVersion
from .tender_repository import limit_value, owned_dossier, source_readable


def review_changes(session, user_id, dossier_id, *, through_sequence, reviewed_sequence,
                   limit=20, after_sequence=None, now=None):
    """Pin pagination to the reader's decision/evidence boundary.

    Denied intermediate evidence occupies an unavailable slot rather than silently
    disappearing. Operational/integrity failures propagate. Exact originals and
    document comparisons remain separate current-rights reads.
    """
    dossier = owned_dossier(session, user_id, dossier_id)
    limit_value(limit)
    if (type(through_sequence) is not int or through_sequence < 1
            or type(reviewed_sequence) is not int or reviewed_sequence < 0):
        raise DomainError("Invalid review window.", 422, "tender_review_window_invalid")
    if (through_sequence != dossier.latest_sequence
            or reviewed_sequence != (dossier.reviewed_sequence or 0)):
        raise DomainError("The tender or decision changed. Refresh its current evidence.",
                          409, "tender_version_conflict")
    if after_sequence is None:
        after_sequence = reviewed_sequence
    if type(after_sequence) is not int or not reviewed_sequence <= after_sequence <= through_sequence:
        raise DomainError("Invalid review cursor.", 422, "tender_review_window_invalid")
    now = aware(now or datetime.now(UTC))
    query = select(TenderDossierVersion).where(
        TenderDossierVersion.organization_id == dossier.organization_id,
        TenderDossierVersion.dossier_id == dossier.id,
        TenderDossierVersion.sequence > after_sequence,
        TenderDossierVersion.sequence <= through_sequence,
    ).order_by(TenderDossierVersion.sequence).limit(limit + 1)
    rows = list(session.scalars(query))
    items = []
    for row in rows[:limit]:
        item = {"id": row.id, "sequence": row.sequence, "available": False}
        try:
            source_readable(row, now, user_id=user_id)
        except DomainError as error:
            if error.status != 404:
                raise
        else:
            item.update(available=True, kind=row.kind, changes=deepcopy(row.changes),
                        document_observation_id=row.document_observation_id,
                        profile_revision=row.profile_revision)
        items.append(item)
    return {"reviewed_sequence": dossier.reviewed_sequence, "through_sequence": through_sequence,
            "items": items, "next_cursor": rows[limit - 1].sequence if len(rows) > limit else None}
