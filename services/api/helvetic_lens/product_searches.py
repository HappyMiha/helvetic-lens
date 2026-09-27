"""Private, reusable search recipes; saving never performs or schedules a search."""
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, model_validator
from sqlalchemy import func, select

from . import legal_profiles
from .interest_jobs import lock_organization
from .product_api import Product, dossier, entry_payload, fail
from .product_models import DossierEntry


class SavedSearchInput(legal_profiles.Input):
    request_key: UUID
    query: str = Field(min_length=2, max_length=300)
    provider: Literal["workspace", "fedlex", "europepmc"]
    match_mode: Literal["all", "phrase"] | None = None
    purpose: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def valid_search(self):
        if self.provider == "workspace":
            self.match_mode = self.match_mode or "all"
            if self.match_mode == "all" and len(set(self.query.lower().split())) > 12:
                raise ValueError("Use up to 12 distinct search words, or choose Exact phrase.")
        elif self.match_mode is not None:
            raise ValueError("Workspace match modes do not apply to public source searches.")
        return self


def search_query(identifier):
    return select(DossierEntry).where(DossierEntry.dossier_id == identifier, DossierEntry.kind == "saved_search")


def search_routes(router, service, actor):
    @router.get("/dossiers/{identifier}/searches")
    def listing(product: Product, identifier: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            row, _ = dossier(session, product, identifier, identity.user_id)
            query = search_query(row.id)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            items = session.scalars(query.order_by(DossierEntry.created_at.desc(), DossierEntry.id).offset(offset).limit(50))
            return {"items": [entry_payload(session, entry) for entry in items], "total": total}

    @router.post("/dossiers/{identifier}/searches", status_code=201)
    def save(product: Product, identifier: str, data: SavedSearchInput, request: Request):
        identity = actor(request)
        if identity.role != "organization_admin":
            fail("Your workspace role is read-only.", 403)
        recipe = {"query": data.query, "provider": data.provider, "match_mode": data.match_mode}
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            row, _ = dossier(session, product, identifier, identity.user_id)
            previous = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                DossierEntry.request_key == str(data.request_key)))
            if previous:
                if (previous.kind, previous.body, previous.data_json) != ("saved_search", data.purpose, recipe):
                    fail("This request key belongs to a different saved entry.", 409)
                return entry_payload(session, previous)
            entry = DossierEntry(dossier_id=row.id, request_key=str(data.request_key), kind="saved_search",
                title=data.query[:240], body=data.purpose, data_json=recipe, actor_user_id=identity.user_id)
            session.add(entry)
            session.commit()
            return entry_payload(session, entry)
