"""Bounded, resumable SIMAP work planning with private per-monitor checkpoints."""

from copy import deepcopy
from datetime import timedelta

from sqlalchemy import select

from .simap_sources import (
    ZURICH,
    aware,
    parse_project_header,
    parse_publication,
    parse_publication_history,
    parse_search_page,
)
from .simap_tender_facts import facts_from_publication
from .tender_contracts import CpvAncestry, TenderProfile
from .tender_models import TenderCpvCache, TenderDossier
from .tender_observations import observe_publication
from .tender_repository import digest

LOOKBACK_DAYS = 90
CYCLE_HOURS = 6
MAX_PAGES_PER_QUERY = 100
MAX_PENDING = 2000
MAX_SEEN = 5000


def queries(configuration):
    profile = TenderProfile.model_validate(configuration)
    result = [{"cpv_codes": list(profile.cpv_codes)}] if profile.cpv_codes else []
    phrases = sorted(
        {
            phrase.strip()
            for capability in profile.capabilities
            for phrase in capability.phrases
            if len(phrase.strip()) >= 3
        }
    )
    result.extend({"query": phrase} for phrase in phrases)
    return result


def start(now):
    day = aware(now).astimezone(ZURICH).date()
    return {
        "schema": 1,
        "started_at": now.isoformat(),
        "from_day": (day - timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "until_day": day.isoformat(),
        "query": 0,
        "cursor": None,
        "pages": 0,
        "follow_cursor": None,
        "follow_complete": False,
        "pending": [],
        "seen": [],
        "withheld_until": None,
        "gaps": [],
        "truncated": False,
        "buffer": None,
        "failed_key": None,
        "failed_attempts": 0,
    }


def key(work):
    return digest(work)


def enqueue(state, work, *, front=False):
    hashed = key(work)
    if hashed in state["seen"] or any(key(item) == hashed for item in state["pending"]):
        return
    if len(state["pending"]) >= MAX_PENDING:
        state["truncated"] = True
        if not front:
            return
        state["pending"].pop()
    state["pending"].insert(0, work) if front else state["pending"].append(work)


def next_work(session, monitor, state):
    if state.get("schema") != 1:
        raise ValueError("Unsupported tender collection checkpoint")
    if state["pending"]:
        return state["pending"][0]
    if not state["follow_complete"]:
        query = select(TenderDossier.project_id).where(
            TenderDossier.monitor_id == monitor.id,
            TenderDossier.organization_id == monitor.organization_id,
            TenderDossier.following.is_(True),
        )
        if state["follow_cursor"]:
            query = query.where(TenderDossier.project_id > state["follow_cursor"])
        projects = list(session.scalars(query.distinct().order_by(TenderDossier.project_id).limit(20)))
        for project in projects:
            lots = list(
                session.scalars(
                    select(TenderDossier.lot_key)
                    .where(
                        TenderDossier.monitor_id == monitor.id,
                        TenderDossier.organization_id == monitor.organization_id,
                        TenderDossier.project_id == project,
                        TenderDossier.following.is_(True),
                    )
                    .order_by(TenderDossier.lot_key)
                )
            )
            enqueue(state, {"kind": "header", "project_id": project, "lot_ids": lots})
        state["follow_cursor"] = projects[-1] if projects else state["follow_cursor"]
        state["follow_complete"] = len(projects) < 20
        if state["pending"]:
            return state["pending"][0]
    plan = queries(monitor.configuration)
    if state["query"] < len(plan) and len(state["seen"]) < MAX_SEEN:
        return {
            "kind": "search",
            **plan[state["query"]],
            "last_item": state["cursor"],
            "newest_from": state["from_day"],
            "newest_until": state["until_day"],
        }
    if state["query"] < len(plan):
        state["truncated"] = True
    return None


def defer_publication(state, until):
    value = aware(until).isoformat()
    if state["withheld_until"] is None or value < state["withheld_until"]:
        state["withheld_until"] = value


def publication_work(project_id, publication_id, lot_ids, *, discover):
    return {
        "kind": "publication",
        "project_id": project_id,
        "publication_id": publication_id,
        "lot_ids": sorted(set(lot_ids)),
        "discover": discover,
    }


def finish_work(state, work):
    if state["pending"] and key(state["pending"][0]) == key(work):
        state["pending"].pop(0)
    hashed = key(work)
    if len(state["seen"]) < MAX_SEEN and hashed not in state["seen"]:
        state["seen"].append(hashed)
    state["failed_key"], state["failed_attempts"] = None, 0


def cache_entries(session, codes, now):
    rows = session.scalars(
        select(TenderCpvCache).where(
            TenderCpvCache.code.in_(codes),
            TenderCpvCache.verified_at >= now - timedelta(days=7),
        )
    )
    return {row.code: CpvAncestry.model_validate(row.ancestry) for row in rows}


def accept(session, monitor, state, work, raw, now, *, storage_limits=None):
    """Advance a checkpoint only after a bounded successful parse/observation."""
    kind = work["kind"]
    finish_work(state, work)
    if kind == "search":
        page = parse_search_page(raw, now=now, previous_cursor=work["last_item"])
        if page.withheld_until:
            defer_publication(state, page.withheld_until)
        for project in page.publications:
            if project["lots"]:
                # Search identifies the latest publication FOR EACH lot. Do not
                # promote every lot in an older shared publication as still open.
                grouped = {}
                for lot in project["lots"]:
                    grouped.setdefault(lot["publicationId"], []).append(lot["lotId"])
            else:
                grouped = {project["publicationId"]: [""]}
            for publication, lot_ids in grouped.items():
                enqueue(state, publication_work(project["id"], publication, lot_ids, discover=True))
        state["pages"] += 1
        if page.next_cursor and state["pages"] < MAX_PAGES_PER_QUERY:
            state["cursor"] = page.next_cursor
        else:
            state["truncated"] |= page.next_cursor is not None
            state["query"], state["cursor"], state["pages"] = state["query"] + 1, None, 0
    elif kind == "header":
        refs = parse_project_header(raw, project_id=work["project_id"], now=now)
        if refs.withheld_until:
            defer_publication(state, refs.withheld_until)
        for ref in refs.publications:
            wanted = set(work["lot_ids"]) & set(ref["lot_ids"] or [""])
            if not wanted:
                continue
            enqueue(
                state, publication_work(work["project_id"], ref["publication_id"], wanted, discover=False)
            )
            for lot in sorted(wanted):
                enqueue(
                    state,
                    {
                        "kind": "history",
                        "project_id": work["project_id"],
                        "publication_id": ref["publication_id"],
                        "lot_id": lot,
                    },
                )
    elif kind == "history":
        refs = parse_publication_history(raw, project_id=work["project_id"], now=now)
        if refs.withheld_until:
            defer_publication(state, refs.withheld_until)
        for ref in refs.publications:
            enqueue(
                state,
                publication_work(work["project_id"], ref["publication_id"], [work["lot_id"]], discover=False),
            )
    elif kind == "publication":
        record = parse_publication(
            raw, project_id=work["project_id"], publication_id=work["publication_id"], now=now
        )
        facts = facts_from_publication(record, now=now)
        codes = {
            code
            for fact in facts
            if (fact.lot_id or "") in work["lot_ids"]
            for code in (*(fact.cpv_codes or ()), *(fact.project_cpv_codes or ()))
        }
        profile = TenderProfile.model_validate(monitor.configuration)
        if not profile.cpv_include_descendants or not (profile.cpv_codes or profile.excluded_cpv_codes):
            codes = set()
        entries = cache_entries(session, codes, now)
        state["buffer"] = {"record": record, "work": deepcopy(work)}
        enqueue(
            state,
            {
                "kind": "apply",
                "publication_id": record["publication_id"],
                "work_key": key(work),
                "source_hash": record["evidence_sha256"],
            },
            front=True,
        )
        for code in sorted(codes - entries.keys(), reverse=True):
            enqueue(state, {"kind": "taxonomy", "code": code}, front=True)
    elif kind == "taxonomy":
        entry = CpvAncestry.model_validate(raw)
        if entry.code != work["code"]:
            raise ValueError("Taxonomy response identity mismatch")
        cached = session.get(TenderCpvCache, entry.code)
        if cached is None:
            session.add(
                TenderCpvCache(code=entry.code, ancestry=entry.model_dump(mode="json"), verified_at=now)
            )
        else:
            cached.ancestry, cached.verified_at = entry.model_dump(mode="json"), now
    elif kind == "apply":
        buffered = state["buffer"]
        if (
            not buffered
            or buffered["record"]["publication_id"] != work["publication_id"]
            or key(buffered["work"]) != work["work_key"]
            or buffered["record"]["evidence_sha256"] != work["source_hash"]
        ):
            raise ValueError("Publication checkpoint mismatch")
        record, original_work = buffered["record"], buffered["work"]
        facts = facts_from_publication(record, now=now)
        codes = {
            code for fact in facts for code in (*(fact.cpv_codes or ()), *(fact.project_cpv_codes or ()))
        }
        entries = cache_entries(session, codes, now)
        touched = observe_publication(
            session,
            monitor.id,
            record,
            now=now,
            cpv_ancestry=tuple(entries.values()),
            discover=original_work["discover"],
            allowed_lot_ids=set(original_work["lot_ids"]),
            **({"storage_limits": storage_limits} if storage_limits is not None else {}),
        )
        if original_work["discover"]:
            for row in session.scalars(
                select(TenderDossier).where(
                    TenderDossier.id.in_(touched), TenderDossier.organization_id == monitor.organization_id
                )
            ):
                enqueue(
                    state,
                    {
                        "kind": "history",
                        "project_id": row.project_id,
                        "publication_id": record["publication_id"],
                        "lot_id": row.lot_key,
                    },
                )
        state["buffer"] = None
        return len(touched)
    else:
        raise ValueError("Unknown tender work kind")
    return 0


def failed(state, work, reason):
    hashed = key(work)
    state["failed_attempts"] = state["failed_attempts"] + 1 if state["failed_key"] == hashed else 1
    state["failed_key"] = hashed
    if state["failed_attempts"] >= 3:
        # A broken record does not freeze every other query/followed dossier.
        # The next full overlapping cycle will reconsider the source work.
        if len(state["gaps"]) < 100:
            state["gaps"].append({"kind": work["kind"], "reason": reason, "work_hash": hashed})
        if work["kind"] == "search":
            state["query"], state["cursor"], state["pages"] = state["query"] + 1, None, 0
        if work["kind"] == "apply":
            state["buffer"] = None
        finish_work(state, work)


def next_cycle(state, now):
    next_at = max(
        now + timedelta(seconds=15), aware_from_text(state["started_at"]) + timedelta(hours=CYCLE_HOURS)
    )
    if state["withheld_until"] and aware_from_text(state["withheld_until"]) > now:
        next_at = min(next_at, aware_from_text(state["withheld_until"]))
    return next_at


def aware_from_text(value):
    from datetime import datetime

    return aware(datetime.fromisoformat(value))
