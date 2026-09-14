"""Operator-reviewed area evidence; never infers road coordinates or source rights."""
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from .models import User
from .monitoring_subjects import _actor
from .related_contracts import PlaceBinding, fingerprint
from .related_models import RelatedPlaceBinding
from .related_repository import clock, fail


def administrator(session, user_id):
    _actor(session, user_id, write=True)
    user = session.get(User, user_id, populate_existing=True)
    if user is None or not user.active or not user.platform_admin:
        fail("platform_admin_required", 403)


class BindingStore:
    def __init__(self, boundaries):
        self.boundaries = boundaries

    def current_area(self, binding, *, now):
        if binding.place_namespace != "swisstopo:bfs_municipality":
            return False
        proof = self.boundaries.municipality_identity(binding.place_id, now=now)
        return (proof.get("state") == "verified" and proof.get("version") == binding.boundary_version
                and proof.get("sha256") == binding.boundary_hash
                and binding.valid_until <= datetime.fromisoformat(proof["expires_on"]).replace(tzinfo=UTC))

    def select(self, session, fact, *, now):
        now = clock(now)
        if fact.availability != "available":
            return None
        # More than one simultaneous live binding is ambiguous, not an arbitrary
        # first result. Operators must revoke an old review before replacing it.
        rows = list(session.scalars(select(RelatedPlaceBinding).where(
            RelatedPlaceBinding.feature_key == fingerprint(fact.source_feature.model_dump(mode="json")),
            RelatedPlaceBinding.source_revision == fact.source_revision,
            RelatedPlaceBinding.revoked_at.is_(None)).order_by(RelatedPlaceBinding.id).limit(101)))
        if len(rows) > 100:
            return None
        valid = []
        for row in rows:
            try:
                binding = PlaceBinding.model_validate_json(json.dumps(row.binding))
                if (row.fingerprint != fingerprint(row.binding) or str(binding.id) != row.id
                        or binding.source_feature != fact.source_feature or binding.source_revision != fact.source_revision):
                    return None
                if binding.revoked_at is None and binding.accepted_at <= now < binding.valid_until and self.current_area(binding, now=now):
                    valid.append(binding)
            except (ValidationError, ValueError, TypeError, KeyError):
                return None
        return valid[0] if len(valid) == 1 else None

    def publish(self, session, user_id, *, reader, reference, binding, now):
        administrator(session, user_id)
        now = clock(now)
        fact = reader.resolve(session, user_id, reference, now=now)["fact"]
        if (fact.availability != "available" or binding.source_feature != fact.source_feature
                or binding.source_revision != fact.source_revision or binding.revoked_at is not None
                or not binding.accepted_at <= now < binding.valid_until or not self.current_area(binding, now=now)):
            fail("related_binding_invalid", 422)
        digest = fingerprint(binding.model_dump(mode="json"))
        existing = session.get(RelatedPlaceBinding, str(binding.id), populate_existing=True)
        if existing is not None:
            if existing.fingerprint != digest or existing.revoked_at is not None:
                fail("related_binding_conflict")
            return {"id": existing.id}
        row = RelatedPlaceBinding(id=str(binding.id), feature_key=fingerprint(fact.source_feature.model_dump(mode="json")),
            source_revision=fact.source_revision, binding=binding.model_dump(mode="json"), fingerprint=digest,
            reviewed_by=user_id, created_at=now)
        session.add(row)
        session.flush()
        return {"id": row.id}

    def revoke(self, session, user_id, identifier, *, now):
        administrator(session, user_id)
        row = session.get(RelatedPlaceBinding, str(UUID(str(identifier))), populate_existing=True)
        if row is None:
            fail("related_binding_not_found", 404)
        if row.revoked_at is None:
            row.revoked_at = clock(now)
            session.flush()
        return {"id": row.id, "revoked": True}
