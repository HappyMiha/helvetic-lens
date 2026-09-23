"""Transaction-owned private erasure with retained-reference checks.

Foreign keys remain enforced. Selection starts with explicit account/workspace
ownership, follows cascade containment and the listed private document edges,
and refuses references from retained work instead of cascading into colleagues.
The caller owns authentication, password confirmation, locks and the commit.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import and_, delete, false, inspect, or_, select, tuple_, update

from . import business_item_models as business_item_models
from . import business_monitor_models as business_monitor_models
from . import monitoring_connector_models as monitoring_connector_models
from .account_deletion_plan import fail
from .db import Base
from .models import DigestDelivery, Job
from .monitoring_centre import MODELS

MAX_ROWS = 100000
CHUNK = 200
ORG_COLUMNS = ("organization_id", "owner_organization_id")
# Unscoped native corpus rows belong to their private work/expression, despite
# legacy restrictive foreign keys. Other workspaces' references are checked
# separately before erasure. Shared official work has no owner and is not a root.
CONTAINED = {
    ("regulatory_expressions", "work_id"), ("regulatory_identifiers", "work_id"),
    ("regulatory_document_versions", "expression_id"),
    ("connector_receipts", "work_id"), ("connector_receipts", "expression_id"),
    ("regulatory_events", "work_id"), ("regulatory_relations", "subject_work_id"),
    ("regulatory_relations", "object_work_id"), ("relation_candidates", "source_work_id"),
    ("relation_candidates", "target_work_id"), ("relation_candidates", "event_id"),
    ("digest_deliveries", "preference_id"), ("job_steps", "job_id"), ("outbox_messages", "job_id"),
}
DETACH = {
    ("administrative_audit", "actor_user_id"), ("security_events", "user_id"),
    ("action_decisions", "actor_user_id"), ("organization_relation_reviews", "actor_user_id"),
    ("connector_runs", "requested_by_organization_id"), ("connector_runs", "job_id"),
}
PERSONAL_RESTRICT = {"account_tokens", "organization_memberships", "user_sessions",
                     "digest_preferences", "digest_deliveries"}
PREFIX = {"pollen": "monitoring_subject", "air": "air_monitor", "river": "river_monitor",
          "warnings": "hazard_monitor", "traffic": "road_monitor", "commute": "commute_monitor",
          "tenders": "tender_monitor", "ip": "trademark_monitor", "auctions": "auction_monitor"}


def chunks(values):
    ordered = sorted(values)
    for start in range(0, len(ordered), CHUNK):
        yield ordered[start:start + CHUNK]


def keys_in(table, keys):
    columns = list(table.primary_key)
    if not keys:
        return false()
    if len(columns) == 1:
        return columns[0].in_([key[0] for key in keys])
    return tuple_(*columns).in_(keys)


def references(foreign_key, keys):
    parent = foreign_key.referred_table
    child = foreign_key.table
    return select(1).select_from(parent).where(keys_in(parent, keys),
        *(edge.parent == edge.column for edge in foreign_key.elements)).correlate(child).exists()


def direct_roots(table, user, organizations):
    conditions = [table.c[name].in_(organizations) for name in ORG_COLUMNS if name in table.c]
    if table.name == "organizations":
        conditions.append(table.c.id.in_(organizations))
    if table.name == "users":
        conditions.append(table.c.id == user.id)
    if "principal_key" in table.c:
        conditions.append(table.c.principal_key == f"user:{user.id}")
    for fk in table.foreign_key_constraints:
        if fk.referred_table.name != "users" or len(fk.columns) != 1:
            continue
        column = list(fk.columns)[0]
        if fk.ondelete == "CASCADE" or table.name in PERSONAL_RESTRICT:
            conditions.append(column == user.id)
    if table.name == "organization_invitations":
        conditions.extend((table.c.invited_by_user_id == user.id, table.c.email == user.email))
    if table.name == "legal_monitoring_profiles":
        conditions.append(and_(table.c.created_by_user_id == user.id, table.c.status == "draft"))
    if table.name == "interest_brief_feedback":
        conditions.append(table.c.actor_user_id == user.id)
    if table.name == "jobs":
        for domain, model in MODELS.items():
            native = model.__table__
            conditions.append(and_(table.c.target_type == PREFIX[domain], table.c.target_id.in_(
                select(native.c.id).where(native.c.owner_user_id == user.id))))
        conditions.append(and_(table.c.target_type == "digest_delivery", table.c.target_id.in_(
            select(DigestDelivery.id).where(DigestDelivery.user_id == user.id))))
    return or_(*conditions) if conditions else false()


@dataclass
class ErasureSelection:
    keys: dict
    artifacts: set

    @property
    def counts(self):
        return {name: len(keys) for name, keys in self.keys.items() if keys}


def select_private_rows(session, user, organizations):
    if not session.info.get("include_all_organizations"):
        raise ValueError("Erasure requires a complete cross-workspace session.")
    # Fail closed on a schema this executor does not know. Never pretend that a
    # partial ORM inventory proves account erasure on a newer database.
    actual = set(inspect(session.connection()).get_table_names()) - {"alembic_version"}
    if actual != set(Base.metadata.tables):
        fail("account_deletion_schema_changed", 503)
    selected, total, artifacts = {}, 0, set()
    for table in Base.metadata.sorted_tables:
        keys = set()
        conditions = [direct_roots(table, user, organizations)]
        for fk in table.foreign_key_constraints:
            if fk.referred_table is table:
                continue
            contained = fk.ondelete == "CASCADE" or any(
                (table.name, column.name) in CONTAINED for column in fk.columns)
            if not contained:
                continue
            for part in chunks(selected.get(fk.referred_table.name, set())):
                predicate = references(fk, part)
                # A cascade alone is not authority to erase a row carrying
                # another workspace's explicit ownership label.
                for name in ORG_COLUMNS:
                    if name in table.c and fk.referred_table.name != "users":
                        parent_org = fk.referred_table.c.get(name)
                        if parent_org is not None:
                            predicate = and_(predicate, table.c[name].in_(
                                select(parent_org).where(keys_in(fk.referred_table, part))))
                conditions.append(predicate)
        for condition in conditions:
            keys.update(tuple(row) for row in session.execute(
                select(*table.primary_key).where(condition).limit(MAX_ROWS + 1)))
            if total + len(keys) > MAX_ROWS:
                fail("account_deletion_inventory_too_large", 422)
        selected[table.name] = keys
        total += len(keys)
        if table.name in {"versions", "observations", "regulatory_document_versions"}:
            for part in chunks(keys):
                artifacts.update(session.scalars(select(table.c.artifact_key).where(keys_in(table, part))))
    dates = Base.metadata.tables["regulatory_dates"]
    for kind, name in (("work", "regulatory_works"), ("expression", "regulatory_expressions"),
                       ("version", "regulatory_document_versions"), ("event", "regulatory_events")):
        for part in chunks(selected.get(name, set())):
            selected[dates.name].update(tuple(row) for row in session.execute(select(*dates.primary_key).where(
                dates.c.entity_type == kind, dates.c.entity_id.in_([key[0] for key in part])).limit(MAX_ROWS + 1)))
    if sum(len(keys) for keys in selected.values()) > MAX_ROWS:
        fail("account_deletion_inventory_too_large", 422)
    artifacts.discard(None)
    artifacts.discard("")
    return ErasureSelection(selected, artifacts)


def retained_references(session, selection):
    """Return permitted detachments, refusing every other retained dependency."""
    detachments = []
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_key_constraints:
            columns = list(fk.columns)
            permitted = all(column.nullable for column in columns) and (
                fk.ondelete == "SET NULL" or all((table.name, column.name) in DETACH for column in columns))
            for part in chunks(selection.keys.get(fk.referred_table.name, set())):
                query = select(*table.primary_key).where(references(fk, part)).limit(MAX_ROWS + 1)
                retained = {tuple(row) for row in session.execute(query)} - selection.keys.get(table.name, set())
                if not retained:
                    continue
                if not permitted:
                    fail("account_deletion_retained_reference", 409)
                detachments.append((table, columns, retained))
    return detachments


def private_document_version_count(session, selection):
    """A bridged legacy/native pair represents one document version to its owner."""
    native = Base.metadata.tables["regulatory_document_versions"]
    legacy = {key[0] for key in selection.keys.get("versions", set())}
    mirrored = set()
    for part in chunks(selection.keys.get(native.name, set())):
        mirrored.update(session.scalars(select(native.c.legacy_version_id).where(keys_in(native, part))))
    return len(legacy) + len(selection.keys.get(native.name, set())) - len(legacy & mirrored)


def erase_selected(session, user, selection):
    detachments = retained_references(session, selection)
    # Remove denormalized actor labels only for this account. Free-text shared
    # decisions remain workspace records, as the preview explicitly explains.
    actions = Base.metadata.tables["action_decisions"]
    session.execute(update(actions).where(actions.c.actor_user_id == user.id).values(actor_label="Former member"))
    security = Base.metadata.tables["security_events"]
    session.execute(update(security).where(or_(security.c.user_id == user.id,
        security.c.subject_hash == hashlib.sha256(user.email.encode()).hexdigest())).values(subject_hash=None))
    for table, columns, retained in detachments:
        for part in chunks(retained):
            session.execute(update(table).where(keys_in(table, part)).values({column.name: None for column in columns}))
    # Historic email policies on transferred shared monitors are no longer this
    # person's notification consent. Their old recipient must not survive erasure.
    for table in Base.metadata.sorted_tables:
        if table.name.endswith("_email_policies") and "recipient_email" in table.c:
            session.execute(update(table).where(table.c.recipient_email == user.email).values(recipient_email=None))
    jobs = Base.metadata.tables[Job.__tablename__]
    for part in chunks(selection.keys.get("jobs", set())):
        session.execute(update(jobs).where(keys_in(jobs, part)).values(cancel_requested=True))
    for table in reversed(Base.metadata.sorted_tables):
        # Nullable self-history links between selected records can span delete
        # batches. Clear only selected rows after retained-reference validation.
        for fk in table.foreign_key_constraints:
            if fk.referred_table is table and all(column.nullable for column in fk.columns):
                for part in chunks(selection.keys.get(table.name, set())):
                    session.execute(update(table).where(keys_in(table, part)).values(
                        {column.name: None for column in fk.columns}))
        for part in chunks(selection.keys.get(table.name, set())):
            session.execute(delete(table).where(keys_in(table, part)))
