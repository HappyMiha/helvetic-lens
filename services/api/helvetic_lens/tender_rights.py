"""Current restrictions on retained anonymous SIMAP publication evidence.

Source availability flags are not a substitute for a durable withdrawal. This
registry can only deny public uses; it cannot authorize documents, Q&A or export
of authenticated records. Operator policy references never enter user responses.
"""

from uuid import UUID

from sqlalchemy import and_, exists, or_, select

from .config import DomainError
from .tender_models import TenderSourceRestriction


class SourceRestricted(DomainError):
    def __init__(self):
        super().__init__("This source evidence is unavailable.", 404, "tender_publication_unavailable")


def permitted(project_id, publication_id):
    return ~exists(
        select(1).where(
            or_(
                and_(
                    TenderSourceRestriction.scope == "project",
                    TenderSourceRestriction.target_id == project_id,
                ),
                and_(
                    TenderSourceRestriction.scope == "publication",
                    TenderSourceRestriction.target_id == publication_id,
                ),
            )
        )
    )


def require_permitted(session, project_id=None, publication_id=None):
    if not session.scalar(select(permitted(project_id, publication_id))):
        raise SourceRestricted()


def restrict(session, *, scope, target_id, policy_reference, now):
    """Trusted operator use only; caller commits. No public write endpoint.

    Repeated restriction is idempotent and preserves the first policy evidence.
    Lifting a restriction requires a separately reviewed policy operation.
    """
    if scope not in {"project", "publication"}:
        raise ValueError("Invalid restriction scope")
    target_id = str(UUID(target_id))
    if not isinstance(policy_reference, str) or not 1 <= len(policy_reference.strip()) <= 500:
        raise ValueError("A bounded operator policy reference is required")
    if session.get(TenderSourceRestriction, (scope, target_id)) is None:
        session.add(
            TenderSourceRestriction(
                scope=scope,
                target_id=target_id,
                policy_reference=policy_reference.strip(),
                recorded_at=now,
            )
        )
        session.flush()
