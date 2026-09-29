"""Accountable product work: assignments, dates, evidence and recorded decisions."""

import hashlib
import html
import json
from datetime import date, timedelta
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Query, Request
from fastapi.responses import HTMLResponse
from pydantic import Field, field_validator, model_validator
from sqlalchemy import case, func, or_, select

from . import legal_profiles, topic_matching
from .db import utcnow
from .interest_jobs import lock_organization
from .legal_profile_models import LegalMonitoringProfile
from .models import OrganizationMembership, RegulatoryEventState, TopicEventMatch, User
from .product_api import Product, dossier, fail, iso
from .product_models import DossierAction, DossierEntry, ProductDossier, ResearchThread

Priority = Literal["normal", "high", "urgent"]
ActionStatus = Literal["open", "in_progress", "done", "cancelled"]


def today():
    return utcnow().astimezone(ZoneInfo("Europe/Zurich")).date()


class Context(legal_profiles.Input):
    subject: str = Field(default="", max_length=240)
    reference: str = Field(default="", max_length=120)
    jurisdictions: str = Field(default="", max_length=240)
    category: str = Field(default="", max_length=120)


class WorkInput(legal_profiles.Input):
    expected_revision: int = Field(ge=1)
    context: Context
    priority: Priority = "normal"
    owner_user_id: UUID | None = None
    next_review_on: date | None = None


class ReviewInput(legal_profiles.Input):
    expected_revision: int = Field(ge=1)
    request_key: UUID
    note: str = Field(min_length=3, max_length=4000)
    next_review_on: date | None = None


class ActionFields(legal_profiles.Input):
    title: str = Field(min_length=3, max_length=240)
    detail: str = Field(default="", max_length=4000)
    priority: Priority = "normal"
    assignee_user_id: UUID | None = None
    due_on: date | None = None

    @field_validator("title")
    @classmethod
    def title_required(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Give this action a descriptive title.")
        return value.strip()


class ResearchOrigin(legal_profiles.Input):
    thread_id: UUID
    entry_id: UUID | None = None
    gap_index: int | None = Field(default=None, ge=0, le=7, strict=True)

    @model_validator(mode="after")
    def complete_gap_reference(self):
        if (self.entry_id is None) != (self.gap_index is None):
            raise ValueError("A research gap requires both its saved note and gap index.")
        return self


class ActionCreate(ActionFields):
    creation_key: UUID
    source_url: str = Field(default="", max_length=2000)
    match_id: UUID | None = None
    evaluation_fingerprint: str = Field(default="", max_length=100)
    research_origin: ResearchOrigin | None = None

    @model_validator(mode="after")
    def one_origin(self):
        if self.research_origin and self.match_id:
            raise ValueError("Choose a research question or a monitoring match as this action's origin.")
        return self

    @field_validator("source_url")
    @classmethod
    def source_required(cls, value):
        if value:
            parts = urlsplit(value)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise ValueError("Use an HTTPS source URL without credentials.")
        return value


class ActionUpdate(ActionFields):
    expected_revision: int = Field(ge=1)
    status: ActionStatus
    outcome: str = Field(default="", max_length=4000)


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def member(session, user_id, *, assigning=False):
    if not user_id:
        return None
    identifier = str(user_id)
    person = session.scalar(select(User).join(OrganizationMembership).where(
        User.id == identifier, User.active.is_(True), OrganizationMembership.role == "organization_admin"))
    if assigning:
        from .product_guest_access import guest_request
        from .product_guest_api import assignees

        guest_dossier = guest_request(session)
        if guest_dossier and not session.scalar(assignees(session, guest_dossier).where(User.id == identifier)):
            fail("Choose an administrator already shared with this dossier.")
    if not person and assigning:
        fail("Choose a current administrator from this workspace.")
    return {"id": person.id, "name": person.name or person.email} if person else None


def work_payload(session, row):
    return {"revision": row.revision, "context": Context.model_validate(row.context_json).model_dump(),
            "priority": row.priority, "owner": member(session, row.owner_user_id),
            "next_review_on": row.next_review_on.isoformat() if row.next_review_on else None,
            "last_reviewed_at": iso(row.last_reviewed_at) if row.last_reviewed_at else None,
            "review_due": bool(row.next_review_on and row.next_review_on <= today())}


def action_payload(session, row, parent=None, profile=None):
    from .product_claim_synthesis import UNAVAILABLE, action_hidden

    result = {"id": row.id, "dossier_id": row.dossier_id, "revision": row.revision,
              "title": row.title, "detail": row.detail, "status": row.status, "priority": row.priority,
              "assignee": member(session, row.assignee_user_id),
              "due_on": row.due_on.isoformat() if row.due_on else None,
              "overdue": bool(row.due_on and row.due_on < today() and row.status in ("open", "in_progress")),
              "source_url": row.source_url, "evidence": row.evidence_json, "outcome": row.outcome,
              "created_at": iso(row.created_at), "updated_at": iso(row.updated_at)}
    if action_hidden(session, row):
        result.update(title="Research follow-up unavailable", detail=UNAVAILABLE, outcome="", source_url="", evidence={})
    if parent and profile:
        result["dossier_name"] = profile.config_json.get("name", "Untitled dossier")
        result["subject"] = parent.context_json.get("subject", "")
    return result


def audit(session, parent, user, kind, title, body, data=None, key=None):
    # Resolve current display names at read time instead of retaining them in audit JSON.
    def without_names(value):
        if isinstance(value, dict):
            return {k: ({"id": v["id"]} if k in ("owner", "assignee") and isinstance(v, dict)
                        else without_names(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [without_names(item) for item in value]
        return value
    data = without_names(data or {})
    session.add(DossierEntry(dossier_id=parent.id, request_key=key or str(uuid4()), kind=kind,
        title=title, body=body, data_json=data or {}, actor_user_id=user))


def require_revision(row, expected):
    if row.revision != expected:
        fail("A colleague changed this record. Reload it before saving your changes.", 409, "product_revision_conflict")


def visible_query(product, user):
    from .product_access import visible_profile

    return select(ProductDossier, LegalMonitoringProfile).join(LegalMonitoringProfile).where(
        ProductDossier.product == product,
        visible_profile(user))


def linked_evidence(session, profile, data):
    if not data.match_id:
        return {}, data.source_url
    item = session.scalar(select(TopicEventMatch).join(RegulatoryEventState,
        (RegulatoryEventState.event_id == TopicEventMatch.event_id)
        & (RegulatoryEventState.organization_id == TopicEventMatch.organization_id))
        .where(TopicEventMatch.id == str(data.match_id), TopicEventMatch.topic_id.in_(profile.topic_ids_json)))
    if not item:
        fail("This evidence does not belong to this dossier or is no longer available.", 404)
    described = topic_matching.describe_matches(session, [item])
    if (not described or not described[0]["is_current"] or not data.evaluation_fingerprint
            or described[0]["evaluation_fingerprint"] != data.evaluation_fingerprint):
        fail("This evidence changed. Refresh the dossier and review the current source.", 409)
    evidence = described[0]
    source = evidence["evidence"].get("source_url", "")
    ActionCreate.source_required(source)
    return {"match_id": item.id, "event_id": item.event_id,
            "evaluation_fingerprint": evidence["evaluation_fingerprint"],
            "captured_at": iso(utcnow()), "title": evidence["evidence"].get("title", "")}, source


def research_action_evidence(session, parent, origin):
    thread = session.get(ResearchThread, str(origin.thread_id))
    if not thread or thread.dossier_id != parent.id:
        fail("Research question not found in this topic.", 404)
    snapshot = {"thread_id": thread.id, "question": thread.title, "captured_at": iso(utcnow())}
    if origin.entry_id:
        entry = session.get(DossierEntry, str(origin.entry_id))
        if not entry or entry.dossier_id != parent.id or entry.thread_id != thread.id or entry.kind != "research":
            fail("Research note not found in this question.", 404)
        from .product_api import entry_payload

        exposed = entry_payload(session, entry)
        if exposed["data"].get("claim_freshness", {}).get("status", "current") != "current":
            fail("This research note changed. Generate a current note before creating a follow-up.", 409)
        gaps = exposed["data"].get("unknowns", [])
        if not isinstance(gaps, list) or origin.gap_index >= len(gaps) or not isinstance(gaps[origin.gap_index], str):
            fail("This saved research gap is unavailable. Reload the question.", 409)
        snapshot.update({"entry_id": entry.id, "gap_index": origin.gap_index, "gap": gaps[origin.gap_index]})
        from .product_claim_synthesis import SCOPES

        if entry.data_json.get("evidence_scope") in SCOPES:
            snapshot["evidence_scope"] = entry.data_json["evidence_scope"]
    return snapshot


def operations(router, service, actor):
    def editor(request):
        identity = actor(request)
        from .product_access import request_grant

        if identity.role != "organization_admin" and not request_grant():
            fail("Your workspace role is read-only.", 403, "role_required")
        return identity

    @router.put("/dossiers/{identifier}/work")
    def save_work(product: Product, identifier: str, data: WorkInput, request: Request):
        identity = editor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            row, _ = dossier(session, product, identifier, identity.user_id)
            require_revision(row, data.expected_revision)
            member(session, data.owner_user_id, assigning=True)
            row.context_json = data.context.model_dump()
            row.priority = data.priority
            row.owner_user_id = str(data.owner_user_id) if data.owner_user_id else None
            row.next_review_on = data.next_review_on
            row.revision += 1
            audit(session, row, identity.user_id, "context", "Dossier context updated",
                  "Context, responsibility and review schedule saved.", work_payload(session, row))
            session.commit()
            return work_payload(session, row)

    @router.post("/dossiers/{identifier}/review")
    def record_review(product: Product, identifier: str, data: ReviewInput, request: Request):
        identity = editor(request)
        if len(data.note.strip()) < 3:
            fail("Record what you reviewed and what you decided.")
        if data.next_review_on and data.next_review_on <= today():
            fail("Choose a next review date after today, or leave it empty.")
        signature = fingerprint(data.model_dump(mode="json"))
        key = "review:" + str(data.request_key)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            row, _ = dossier(session, product, identifier, identity.user_id)
            previous = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == row.id, DossierEntry.request_key == key))
            if previous:
                if previous.data_json.get("request_fingerprint") != signature:
                    fail("This review request has already been used for a different decision.", 409)
                return work_payload(session, row)
            require_revision(row, data.expected_revision)
            row.last_reviewed_at = utcnow()
            row.next_review_on = data.next_review_on
            row.revision += 1
            audit(session, row, identity.user_id, "review", "Review recorded", data.note.strip(),
                  {"request_fingerprint": signature, "revision": row.revision,
                   "next_review_on": data.next_review_on.isoformat() if data.next_review_on else None}, key)
            session.commit()
            return work_payload(session, row)

    @router.get("/dossiers/{identifier}/actions")
    def list_actions(product: Product, identifier: str, request: Request, offset: int = Query(0, ge=0, le=100000),
                     thread_id: UUID | None = None):
        identity = actor(request)
        with service.db.session() as session:
            row, _ = dossier(session, product, identifier, identity.user_id)
            query = select(DossierAction).where(DossierAction.dossier_id == row.id)
            if thread_id:
                thread = session.get(ResearchThread, str(thread_id))
                if not thread or thread.dossier_id != row.id:
                    fail("Research question not found in this topic.", 404)
                query = query.where(DossierAction.evidence_json["research"]["thread_id"].as_string() == str(thread_id))
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            records = session.scalars(query.order_by(DossierAction.created_at.desc(), DossierAction.id).offset(offset).limit(50))
            return {"items": [action_payload(session, x) for x in records], "total": total}

    @router.post("/dossiers/{identifier}/actions", status_code=201)
    def create_action(product: Product, identifier: str, data: ActionCreate, request: Request):
        identity = editor(request)
        values = data.model_dump(mode="json", exclude={"creation_key"})
        if data.research_origin is None:
            values.pop("research_origin")  # Preserve request fingerprints from previously published clients.
        signature = fingerprint(values)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            parent, profile = dossier(session, product, identifier, identity.user_id)
            previous = session.scalar(select(DossierAction).where(
                DossierAction.dossier_id == parent.id, DossierAction.creation_key == str(data.creation_key)))
            if previous:
                if previous.creation_fingerprint != signature:
                    fail("This action request has already been used with different details.", 409)
                return action_payload(session, previous)
            if session.scalar(select(func.count()).select_from(DossierAction).where(DossierAction.dossier_id == parent.id)) >= 1000:
                fail("This dossier has reached its 1,000-action limit.")
            member(session, data.assignee_user_id, assigning=True)
            evidence, source = linked_evidence(session, profile, data)
            if data.research_origin:
                evidence["research"] = research_action_evidence(session, parent, data.research_origin)
            row = DossierAction(dossier_id=parent.id, creation_key=str(data.creation_key), creation_fingerprint=signature,
                title=data.title, detail=data.detail, priority=data.priority,
                assignee_user_id=str(data.assignee_user_id) if data.assignee_user_id else None, due_on=data.due_on,
                source_url=source, evidence_json=evidence, created_by_user_id=identity.user_id)
            session.add(row)
            session.flush()
            audit(session, parent, identity.user_id, "action", "Action created: " + row.title[:200], row.detail,
                  {"action_id": row.id, "status": row.status, "revision": row.revision})
            session.commit()
            return action_payload(session, row)

    @router.put("/dossiers/{identifier}/actions/{action_id}")
    def update_action(product: Product, identifier: str, action_id: str, data: ActionUpdate, request: Request):
        identity = editor(request)
        if data.status in ("done", "cancelled") and len(data.outcome.strip()) < 3:
            fail("Record an outcome or a reason before completing or dismissing an action.")
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            row = session.get(DossierAction, action_id)
            if not row or row.dossier_id != parent.id:
                fail("Action not found.", 404)
            require_revision(row, data.expected_revision)
            member(session, data.assignee_user_id, assigning=True)
            before = action_payload(session, row)
            for field in ("title", "detail", "priority", "due_on", "status", "outcome"):
                setattr(row, field, getattr(data, field))
            row.assignee_user_id = str(data.assignee_user_id) if data.assignee_user_id else None
            row.revision += 1
            row.updated_at = utcnow()
            after = action_payload(session, row)
            audit(session, parent, identity.user_id, "action", "Action updated: " + row.title[:200], row.outcome or row.detail,
                  {"action_id": row.id, "before": before, "after": after, "revision": row.revision})
            session.commit()
            return after

    @router.get("/workbench")
    def workbench(product: Product, request: Request, scope: Literal["all", "mine"] = "all",
                  status: Literal["open", "completed", "all"] = "open", q: str = Query("", max_length=200),
                  offset: int = Query(0, ge=0, le=100000), review_offset: int = Query(0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            parents = visible_query(product, identity.user_id)
            query = select(DossierAction, ProductDossier, LegalMonitoringProfile).join(
                ProductDossier, DossierAction.dossier_id == ProductDossier.id).join(LegalMonitoringProfile).where(
                ProductDossier.id.in_(parents.with_only_columns(ProductDossier.id)))
            reviews = parents.where(LegalMonitoringProfile.status != "draft", ProductDossier.next_review_on <= today())
            if scope == "mine":
                query = query.where(DossierAction.assignee_user_id == identity.user_id)
                reviews = reviews.where(ProductDossier.owner_user_id == identity.user_id)
            rows = query.subquery()
            current_members = select(OrganizationMembership.user_id).join(User).where(
                OrganizationMembership.role == "organization_admin", User.active.is_(True))
            open_condition = rows.c.status.in_(("open", "in_progress"))
            def count(condition):
                return session.scalar(select(func.count()).select_from(rows).where(condition))
            counts = {"open": count(open_condition), "overdue": count(open_condition & (rows.c.due_on < today())),
                      "unassigned": count(open_condition & or_(rows.c.assignee_user_id.is_(None), rows.c.assignee_user_id.not_in(current_members))),
                      "completed_week": count((rows.c.status == "done") & (rows.c.updated_at >= utcnow() - timedelta(days=7))),
                      "reviews_due": session.scalar(select(func.count()).select_from(reviews.subquery()))}
            if status != "all":
                query = query.where(DossierAction.status.in_(("open", "in_progress") if status == "open" else ("done", "cancelled")))
            if q.strip():
                query = query.where(DossierAction.title.icontains(q.strip(), autoescape=True))
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            ordering = (case((DossierAction.status.in_(("open", "in_progress")), 0), else_=1),
                        case((DossierAction.due_on < today(), 0), else_=1),
                        case((DossierAction.priority == "urgent", 0), (DossierAction.priority == "high", 1), else_=2),
                        DossierAction.due_on.asc().nulls_last(), DossierAction.created_at.desc(), DossierAction.id)
            actions = session.execute(query.order_by(*ordering).offset(offset).limit(50))
            due = session.execute(reviews.order_by(ProductDossier.next_review_on, ProductDossier.id).offset(review_offset).limit(50))
            return {"today": today().isoformat(), "scope": scope, "counts": counts,
                    "items": [action_payload(session, a, b, c) for a, b, c in actions], "total": total,
                    "reviews": [{"id": a.id, "name": b.config_json.get("name", "Untitled dossier"),
                                 "work": work_payload(session, a)} for a, b in due]}

    @router.get("/dossiers/{identifier}/brief", response_class=HTMLResponse)
    def brief(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            row, profile = dossier(session, product, identifier, identity.user_id)
            actions = session.scalars(select(DossierAction).where(DossierAction.dossier_id == row.id)
                .order_by(DossierAction.created_at.desc(), DossierAction.id).limit(100)).all()
            notes = session.scalars(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                DossierEntry.kind.in_(("review", "note"))).order_by(DossierEntry.created_at.desc(), DossierEntry.id).limit(20)).all()
            references = session.scalars(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                DossierEntry.kind == "reference").order_by(DossierEntry.created_at.desc(), DossierEntry.id).limit(100)).all()
            searches = session.scalars(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                DossierEntry.kind == "saved_search").order_by(DossierEntry.created_at.desc(), DossierEntry.id).limit(50)).all()
            def esc(value):
                return html.escape(str(value or "—"), quote=True)
            def link(url):
                return f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(url)}</a>' if urlsplit(url).scheme == "https" else "—"
            context = work_payload(session, row)
            subject_label = "Medicine / active substance" if product == "pharma" else "Client / organisation"
            fields = [(subject_label, context["context"]["subject"]), ("Reference", context["context"]["reference"]),
                      ("Markets / jurisdictions in scope", context["context"]["jurisdictions"]),
                      ("Lifecycle / practice area", context["context"]["category"]),
                      ("Owner", (context["owner"] or {}).get("name")), ("Priority", context["priority"]),
                      ("Last review", context["last_reviewed_at"]), ("Next review", context["next_review_on"])]
            from .product_domain_context import brief_fields

            domain_fields = brief_fields(row)
            if domain_fields:
                fields += [("Dossier subject", "User-provided context; not verified source facts.")] + domain_fields
            from .dossier_templates import payload as template_payload

            template = template_payload(row)
            if template["saved"]:
                chosen = template["selection"]
                fields += ([("Dossier template", f'{chosen["title"]} · version {chosen["version"]}'),
                            ("Research guidance", chosen["description"]),
                            ("Questions to investigate", "\n".join(chosen["questions"]))] if chosen else
                           [("Dossier template", "Saved format unavailable; retained in private JSON export.")])
            facts = ''.join(f'<dt>{esc(a)}</dt><dd>{esc(b)}</dd>' for a, b in fields)
            cards = []
            for action in actions:
                from .product_claim_synthesis import UNAVAILABLE, action_hidden

                if action_hidden(session, action):
                    cards.append(f'<article><h3>Research follow-up unavailable</h3><p>{esc(UNAVAILABLE)}</p></article>')
                    continue
                assigned = member(session, action.assignee_user_id)
                research = action.evidence_json.get("research")
                origin = (f'<p><b>Research question:</b> {esc(research["question"])}</p>'
                    + (f'<p><b>Gap to establish:</b> {esc(research.get("gap"))}</p>' if research.get("gap") else "")
                    + f'<p><a href="/?dossier={esc(row.id)}&amp;question={esc(research["thread_id"])}">Open research question</a></p>') if research else ""
                cards.append(f'<article><h3>{esc(action.title)}</h3><p class="meta">{esc(action.status)} · '
                    f'{esc(action.priority)} · Owner: {esc((assigned or {}).get("name"))} · Due: {esc(action.due_on)}</p>'
                    f'{origin}<p>{esc(action.detail)}</p><p><b>Outcome:</b> {esc(action.outcome)}</p><p>{link(action.source_url)}</p></article>')
            decisions = ''.join(f'<article><h3>{esc(note.title or "Note")}</h3><p class="meta">{esc(iso(note.created_at))}</p><p>{esc(note.body)}</p></article>' for note in notes)
            from .product_source_reviews import LABELS, current_reviews, review_query

            reviews = current_reviews(session, row.id)
            def review_html(review):
                if review is None:
                    return '<p>Needs review; eligible for AI research.</p>'
                reviewer = session.get(User, review.actor_user_id) if review.actor_user_id else None
                return (f'<p><b>{esc(LABELS[review.data_json["decision"]])}</b> · '
                    f'{esc(reviewer.name if reviewer else "Former member")} · {esc(iso(review.created_at))} · '
                    f'Revision {esc(review.data_json["revision"])}</p><p>{esc(review.body)}</p>')
            review_history = session.scalars(review_query(row.id).order_by(
                DossierEntry.created_at.desc(), DossierEntry.id.desc()).limit(50)).all()
            review_count = session.scalar(select(func.count()).select_from(review_query(row.id).subquery()))
            review_history_html = ''.join(f'<article>{link(review.url)}{review_html(review)}</article>' for review in review_history)
            sources = []
            for ref in references:
                provenance = ref.data_json.get("discovery")
                origin = "<p>No search provenance recorded for this reference.</p>"
                if provenance:
                    record = provenance["record"]
                    origin = (f'<p>Found in {esc(record["provider"])} for “{esc(provenance["query"])}”, '
                        f'page {esc(provenance["page_number"])}, retrieved {esc(provenance["retrieved_at"])}.</p>'
                        f'<p>Catalogue record: {esc(record["id"])}. {esc(record["title"])} '
                        f'({esc(record.get("date") or "date unavailable")}).</p>'
                        '<p>Search provenance was verified on import. Catalogue metadata only; full text and conclusions are not verified.</p>')
                    if record.get("retrieval_queries"):
                        origin += '<p>Retrieved by these exact queries:</p><ul>' + ''.join(
                            f'<li>{esc(query)}</li>' for query in record["retrieval_queries"]) + '</ul>'
                sources.append(f'<li>{esc(ref.title)} — {link(ref.url)}{origin}{review_html(reviews.get(ref.url))}</li>')
            sources = ''.join(sources)
            questions = session.scalars(select(ResearchThread).where(ResearchThread.dossier_id == row.id)
                .order_by(ResearchThread.updated_at.desc(), ResearchThread.id).limit(50)).all()
            from .product_answer_review import review_state

            discussion = []
            for question in questions:
                accepted = session.get(DossierEntry, question.accepted_entry_id) if question.accepted_entry_id else None
                answer = "<p>Still open: no working answer accepted.</p>"
                if accepted and accepted.thread_id == question.id:
                    from .product_api import entry_payload

                    exposed = entry_payload(session, accepted)
                    citations, structured = [], []
                    separated = exposed["data"].get("answer_format") == "source_analysis_v1"
                    if accepted.kind == "research":
                        snapshots = {source["id"]: source for source in exposed["data"].get("sources", [])}
                        for finding in exposed["data"].get("findings", []):
                            finding_citations = []
                            for citation in finding.get("citations", []):
                                source = snapshots.get(citation["source_id"], {})
                                finding_citations.append(f'<li>“{esc(citation["quote"])}” — {esc(source.get("title"))} '
                                                         f'({esc(source.get("kind"))}) {link(source.get("url", ""))}</li>')
                            if separated:
                                label = exposed["data"]["answer_contract"]["labels"].get(finding.get("kind"), "Unclassified AI output")
                                statement = "" if finding.get("kind") == "SOURCE_QUOTE" else f'<p>{esc(finding["claim"])}</p>'
                                structured.append(f'<section><h5>{esc(label)}</h5>{statement}<ul>{"".join(finding_citations)}</ul></section>')
                            else:
                                citations.extend(finding_citations)
                    gaps = ''.join(f'<li>{esc(gap)}</li>' for gap in exposed["data"].get("unknowns", []))
                    text = "".join(structured) if structured else f'<p>{esc(exposed["body"])}</p>'
                    answer = f'<h4>Team’s working answer</h4>{text}<p>{link(exposed["url"])}</p>'
                    if separated:
                        answer += f'<p>{esc(exposed["data"]["answer_contract"]["boundary"])}</p>'
                    answer += f'<p class="meta">Accepted / reviewed {esc(iso(question.accepted_at)) if question.accepted_at else "—"}.</p>'
                    state = review_state(session, row, profile, question, row.organization_id, accepted=accepted)
                    if state["reasons"]:
                        answer += '<p><b>Review needed:</b></p><ul>' + ''.join(
                            f'<li>{esc(reason["message"])}' + (f' Sources: {esc(", ".join(reason["source_ids"]))}.' if reason["source_ids"] else '') + '</li>'
                            for reason in state["reasons"]) + '</ul>'
                    if citations:
                        answer += f'<h4>Quoted evidence</h4><ul>{"".join(citations)}</ul>'
                    if gaps:
                        answer += f'<h4>Still to establish</h4><ul>{gaps}</ul>'
                    if exposed["data"].get("claims"):
                        from .product_claim_synthesis import editor_brief

                        answer += '<h4>Claim context supplied at generation</h4><p>Human acceptance is workflow review, not independent truth.</p>'
                        for claim in exposed["data"]["claims"]:
                            review = claim["human_review"]
                            label = "Changed — review again" if review["stale"] else review["decision"] or "Not reviewed"
                            answer += f'<p>{esc(claim["statement"])} — machine: {esc(claim["machine_status"])}; human: {esc(label)}.</p>'
                            answer += editor_brief(claim)
                            for comparison in claim["comparisons"]:
                                answer += f'<p>{esc(comparison["kind"])} ({esc(comparison["status"])}): {esc(comparison["statement"])}</p>'
                                answer += editor_brief(comparison)
                        for source in exposed["data"].get("sources", []):
                            if source["kind"] == "investigation_quote":
                                answer += f'<blockquote>{esc(source["text"])}</blockquote><p>{esc(source["id"])} · {esc(source["relation"])} · {esc(source["locator"])} · {link(source["url"])}</p>'
                    if accepted.kind == "research":
                        answer += '<p class="meta">AI research note accepted by the team; citations are saved snapshots.</p>'
                discussion.append(f'<article><h3>{esc(question.title)}</h3><p>{esc(question.body)}</p>{answer}</article>')
            title = profile.config_json.get("name", "Monitoring dossier")
            saved_searches = []
            for search in searches:
                recipe = search.data_json
                provider = {"workspace": "Team knowledge", "fedlex": "Fedlex", "europepmc": "Europe PMC"}.get(recipe.get("provider"), "Unknown source")
                mode = (" · Exact phrase" if recipe.get("match_mode") == "phrase" else " · All words") if recipe.get("provider") == "workspace" else ""
                saved_searches.append(f'<article><h3>{esc(recipe.get("query"))}</h3><p class="meta">{esc(provider + mode)} · Saved {esc(iso(search.created_at))}</p><p>{esc(search.body)}</p></article>')
            page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} — Topic brief</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#172640;max-width:900px;margin:40px auto;padding:0 24px}}h1{{font-size:32px}}h2{{margin-top:36px}}h3{{font-size:18px;margin-bottom:8px}}.meta,footer{{font-size:14px;color:#475569}}dl{{display:grid;grid-template-columns:210px 1fr;gap:8px}}dt{{font-weight:600}}dd{{margin:0}}article{{border-top:1px solid #cbd5e1;break-inside:avoid}}p{{white-space:pre-wrap}}a{{color:#174fb2;overflow-wrap:anywhere}}footer{{border-top:1px solid #cbd5e1;margin-top:36px;padding-top:16px}}@media print{{body{{max-width:none;margin:0;padding:0}}.print-tip{{display:none}}@page{{margin:18mm}}}}</style>
<p class="meta">HELVETICLENS {esc(product.upper())} · INTERNAL TOPIC BRIEF</p><h1>{esc(title)}</h1><p>{esc(profile.config_json.get("goal"))}</p>
<p class="print-tip">Use your browser's Print command to print or save this brief as PDF. Review the content before sharing it.</p>
<dl>{facts}</dl><h2>Questions and working answers</h2>{"".join(discussion) or "<p>No research questions recorded.</p>"}
<h2>Actions and outcomes</h2>{''.join(cards) or '<p>No actions recorded.</p>'}
<h2>Review decisions and notes</h2>{decisions or '<p>No review decisions recorded.</p>'}
<h2>Original-source references</h2><ul>{sources or '<li>No additional references saved.</li>'}</ul>
<h2>Source review history</h2><p class="meta">Latest {len(review_history)} of {review_count} reviews. Decisions apply to the exact URL in this dossier's new AI research. Unreviewed sources remain eligible. Existing answers, page watches and notifications are retained.</p>{review_history_html or '<p>No source reviews recorded.</p>'}
<h2>Saved searches</h2><p class="meta">Reusable search queries, not scheduled monitors or records of retrieved results. Review each query before searching again.</p>{''.join(saved_searches) or '<p>No searches saved.</p>'}
<footer>Generated {esc(iso(utcnow()))}. Snapshot of this workspace's recorded work: latest 50 questions, 100 actions, 20 notes/reviews, 100 saved references and 50 saved searches. Attachments are not included. This brief records team decisions; it does not establish complete source coverage or professional validation. Monitoring remains {esc(profile.status)}. Dates use Europe/Zurich for the work queue.</footer></html>'''
            return HTMLResponse(page, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer"})
