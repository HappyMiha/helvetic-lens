"""Owner-private decision search, explicit disclosure and human evaluation."""
import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select

from . import decision_search, legal_profiles
from .db import utcnow
from .decision_engines import DecisionUnavailable
from .membership_locks import lock_organization
from .product_api import Product, fail, iso
from .product_models import DecisionSearchRun
from .product_operations import fingerprint
from .product_provenance import prepare, principal
from .product_search_budget import reserve


class SearchInput(legal_profiles.Input):
    request_key: UUID
    query: str = Field(min_length=2, max_length=300)
    mode: Literal["auto", "jev", "laya", "compare"] = "auto"
    depth: Literal["quick", "balanced", "deep"] = "balanced"
    alternatives: list[Annotated[str, Field(min_length=2, max_length=300)]] = Field(default_factory=list, max_length=2)
    public_query_confirmed: Literal[True]

    @field_validator("public_query_confirmed", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Confirm this public search explicitly.")
        return value

    @model_validator(mode="after")
    def unique_queries(self):
        values = [self.query.casefold(), *(v.casefold() for v in self.alternatives)]
        if len(set(values)) != len(values):
            raise ValueError("Each alternative should use different search terms.")
        return self


class LabelInput(legal_profiles.Input):
    expected_revision: int = Field(ge=1)
    source_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    relevant: bool | None = Field(strict=True)


class InspectInput(legal_profiles.Input):
    source_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    public_fetch_confirmed: Literal[True]

    @field_validator("public_fetch_confirmed", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Confirm this public source inspection explicitly.")
        return value


def visible(identity, product):
    return select(DecisionSearchRun).where(DecisionSearchRun.organization_id == identity.organization_id,
        DecisionSearchRun.owner_user_id == identity.user_id, DecisionSearchRun.product == product)


def current(session, identity, product, identifier):
    row = session.scalar(visible(identity, product).where(DecisionSearchRun.id == identifier))
    if not row:
        fail("Search not found in your current workspace.", 404)
    return row


def evaluate(scores, labels):
    pairs = [(scores[key]["relevance"], label) for key, label in labels.items() if key in scores]
    return {"labelled_count": len(pairs), "candidate_count": len(scores),
            "accuracy": sum((prob >= 0.5) == label for prob, label in pairs) / len(pairs) if pairs else None,
            "brier_score": sum((prob - int(label)) ** 2 for prob, label in pairs) / len(pairs) if pairs else None,
            "basis": "Your relevance labels on this search; 0.5 decision threshold. Not a general accuracy benchmark."}


def payload(session, identity, product, row):
    now = utcnow()
    data = deepcopy(row.result_json)
    data.update(id=row.id, query=row.query, mode=row.mode, status=row.status, revision=row.revision,
                labels=row.labels_json, created_at=iso(row.created_at), checked_at=iso(row.created_at))
    if row.status == "running" and row.created_at.replace(tzinfo=UTC) < now - timedelta(minutes=2):
        data["status"] = "interrupted"
        data["error"] = "This search was interrupted. Submit a new search to retry. No completed result is claimed."
    data.setdefault("items", [])
    data.setdefault("queries", [row.query])
    for inspected in data.get("inspections", {}).values():
        if inspected.get("status") == "running" and datetime.fromisoformat(inspected["started_at"]) < now - timedelta(minutes=2):
            inspected.update(status="interrupted", error="This inspection was interrupted. Open the original source, or inspect it in a new search.")
    for engine in data.get("engines", []):
        engine["evaluation"] = evaluate(engine.get("scores", {}), row.labels_json)
    if data["items"]:
        prepare(session, identity, product, "web", row.query,
                {"items": data["items"], "page_number": 1}, now, retrieved_at=row.created_at.replace(tzinfo=UTC))
    return data


def decision_search_routes(router, service, actor):
    @router.post("/discover/runs/{identifier}/inspect")
    async def inspect(product: Product, identifier: str, data: InspectInput, request: Request):
        from .decision_sources import safe_inspect

        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), write=True)
            row = current(session, identity, product, identifier)
            result = deepcopy(row.result_json)
            item = next((v for v in result.get("items", []) if v["id"] == data.source_id), None)
            if not item or row.status != "complete":
                fail("Choose a source from a completed search.", 409)
            inspections = result.setdefault("inspections", {})
            if data.source_id in inspections:
                return payload(session, identity, product, row)
            if len(inspections) >= 3:
                fail("Three sources have already been inspected for this search. Open their links or start a new search.", 429)
            inspections[data.source_id] = {"status": "running", "url": item["url"], "started_at": iso(utcnow())}
            row.result_json = result
            session.commit()
            query, mode = row.query, row.mode
        inspected = await safe_inspect(service.settings, query, item, mode)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), write=True)
            row = current(session, identity, product, identifier)
            result = deepcopy(row.result_json)
            result.setdefault("inspections", {})[data.source_id] = inspected
            row.result_json = result
            session.commit()
            return payload(session, identity, product, row)

    @router.get("/discover/engines")
    def readiness(product: Product, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
        s = service.settings
        return {"jev_configured": bool(s.typesafe_api_key.get_secret_value()),
                "laya_configured": bool(s.laya_base_url and s.laya_api_key.get_secret_value()),
                "search_configured": bool(s.search1api_api_key.get_secret_value()),
                "daily_limit": s.decision_search_daily_limit,
                "budget_unit": "Each reviewed query counts once; a bundle uses one to three units.",
                "configuration_scope": "Operator-managed credentials. Configured does not guarantee provider availability.",
                "privacy": "The main question and every reviewed alternative go to Search1API. Jev receives the main question and result snippets in Auto, Jev and Compare modes. "
                    "Laya decisions remain on this server; Laya mode still uses remote web retrieval. No private dossier material is added.",
                "retention": "Your last 50 searches in this product/workspace. Account deletion removes them. Colleagues cannot read them."}

    @router.get("/discover/runs")
    def history(product: Product, request: Request, offset: int = Query(default=0, ge=0, le=50)):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            rows = session.scalars(visible(identity, product).order_by(DecisionSearchRun.created_at.desc(), DecisionSearchRun.id).offset(offset).limit(20))
            return {"items": [{"id": row.id, "query": row.query, "mode": row.mode, "status": row.status,
                "created_at": iso(row.created_at)} for row in rows], "offset": offset, "page_size": 20}

    @router.get("/discover/runs/{identifier}")
    def read(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            return payload(session, identity, product, current(session, identity, product, identifier))

    @router.post("/discover/runs/{identifier}/labels")
    def label(product: Product, identifier: str, data: LabelInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), write=True)
            row = current(session, identity, product, identifier)
            if row.status != "complete" or data.source_id not in {v["id"] for v in row.result_json.get("items", [])}:
                fail("Choose a source from this completed search.", 409)
            labels = dict(row.labels_json)
            if row.revision != data.expected_revision:
                fail("Your labels changed. Reopen the saved search before reviewing again.", 409)
            if data.relevant is None:
                labels.pop(data.source_id, None)
            else:
                labels[data.source_id] = data.relevant
            if labels != row.labels_json:
                row.labels_json = labels
                row.revision += 1
            session.commit()
            return payload(session, identity, product, row)

    @router.post("/discover/decision")
    async def search(product: Product, data: SearchInput, request: Request):
        identity = actor(request)
        query = data.query.strip()
        if len(query) < 2:
            fail("Enter at least two search characters.")
        marked = {"query": query, "mode": data.mode, "depth": data.depth, "consent": data.public_query_confirmed}
        if data.alternatives:
            marked["alternatives"] = data.alternatives
        # Preserve existing single-query retry fingerprints across this release.
        mark = fingerprint(marked)
        units = 1 + len(data.alternatives)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), write=True)
            previous = session.scalar(visible(identity, product).where(DecisionSearchRun.request_key == str(data.request_key)))
            if previous:
                if previous.fingerprint != mark:
                    fail("This request key belongs to different search text or mode.", 409)
                return payload(session, identity, product, previous)
            now = utcnow()
            base = select(func.count()).select_from(DecisionSearchRun).execution_options(include_all_organizations=True)
            reserve(session, service.settings, units)
            active = session.scalar(base.where(DecisionSearchRun.status == "running", DecisionSearchRun.created_at >= now - timedelta(minutes=2)))
            if active >= 3:
                fail("Search is busy. Please retry shortly.", 429)
            # Retain same-day receipts so deleting older history cannot reset quotas.
            old = list(session.scalars(visible(identity, product).order_by(DecisionSearchRun.created_at.desc()).offset(49)))
            for entry in old:
                if entry.created_at.replace(tzinfo=UTC) < now.replace(hour=0, minute=0, second=0, microsecond=0):
                    session.delete(entry)
            if session.scalar(select(func.count()).select_from(visible(identity, product).subquery())) >= 50:
                fail("This workspace search history is full for today. Continue tomorrow.", 429)
            row = DecisionSearchRun(product=product, owner_user_id=identity.user_id, request_key=str(data.request_key),
                fingerprint=mark, query=query, mode=data.mode, created_at=now,
                result_json={"queries": [query, *data.alternatives]})
            session.add(row)
            session.commit()
            identifier = row.id
        try:
            async with asyncio.timeout(100):
                result = await decision_search.execute(service.settings, query, data.mode, data.depth, product, data.alternatives)
        except (DecisionUnavailable, TimeoutError) as exc:
            result = {"items": [], "error": "Search could not complete. Check provider setup or credits, then submit a new search.",
                      "error_code": exc.code if isinstance(exc, DecisionUnavailable) else "timeout"}
        result["queries"] = [query, *data.alternatives]
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), write=True)
            row = current(session, identity, product, identifier)
            row.result_json = result
            row.status = "failed" if result.get("error") and not result.get("items") else "complete"
            session.commit()
            return payload(session, identity, product, row)
