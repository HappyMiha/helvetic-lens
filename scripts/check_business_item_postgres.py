"""Rehearse item assignment/decision migrations and lock races on scratch PostgreSQL."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from time import monotonic, sleep

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from helvetic_lens import business_item_work as work
from helvetic_lens import business_monitor_sharing as sharing
from helvetic_lens.business_item_models import BusinessItemWorkEvent as WorkEvent
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Base, Database
from helvetic_lens.models import Organization, OrganizationMembership, User
from test_business_item_work import seed


def check(db):
    with db.session(include_all_organizations=True) as session:
        session.add(Organization(id="org-a", name="Synthetic", slug="synthetic"))
        session.add_all([User(id=user, name=user, email=f"{user}@example.invalid", password_hash="unused") for user in ("owner", "peer")])
        session.flush()
        session.add_all([OrganizationMembership(organization_id="org-a", user_id=user, role="organization_admin") for user in ("owner", "peer")])
        session.commit()
    targets = {domain: seed(db, domain) for domain in work.TARGETS}
    tables = ("tender_dossiers", "trademark_candidates", "auction_items")
    with db.engine.connect() as connection:
        config = Config(str(ROOT / "services/api/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "6f4c2d368eab")
        assert "business_item_work_events" not in inspect(connection).get_table_names()
        for table in tables:
            assert "assigned_user_id" not in {c["name"] for c in inspect(connection).get_columns(table)}
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 1
        command.upgrade(config, "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, compare_to:
            name.startswith(("tender_", "trademark_", "auction_", "business_")) if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        connection.commit()
    for domain, (monitor, item, now, _) in targets.items():
        with db.session() as session:
            initial = work.read(session, "owner", domain, monitor, item, now=now)
        assert initial["assigned"] is None and initial["history"] == []
        decision = {"tenders": "bid", "ip": "counsel", "auctions": "inspect"}[domain]
        gate = Barrier(2)
        def writer(actor):
            gate.wait(timeout=10)
            with db.session() as session:
                try:
                    value = work.act(session, actor, domain, monitor, item, now=now,
                        expected_version=initial["version"], expected_binding=initial["binding"],
                        assigned_user_id=actor, comment=f"Concurrent {actor}", decision=decision)
                    session.commit()
                    return value["version"]
                except DomainError as error:
                    assert error.code == "business_item_changed"
                    return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(writer, ("owner", "peer")))
        assert sorted(map(str, results)) == sorted([str(initial["version"] + 1), "conflict"])
        with db.session() as session:
            current = work.read(session, "owner", domain, monitor, item, now=now)
            assert len(current["history"]) == 1
            assert current["history"][0]["assigned"] == current["history"][0]["actor"]
            assert current["history"][0]["binding"] == initial["binding"]
            column = getattr(WorkEvent, work.TARGETS[domain])
            assert session.scalar(select(func.count()).select_from(WorkEvent).where(column == item)) == 1
        waiting = Event()
        with db.session() as winner:
            parent = sharing.monitor_for(winner, "owner", domain, monitor, write=True)
            def peer():
                with db.session() as session:
                    session.execute(text("SET LOCAL application_name = 'business_item_waiter'"))
                    waiting.set()
                    try:
                        work.act(session, "peer", domain, monitor, item, now=now,
                            expected_version=current["version"], expected_binding=current["binding"],
                            assigned_user_id="peer", comment="Must not survive withdrawal")
                        session.commit()
                        return "unexpected_write"
                    except DomainError as error:
                        return error.code
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(peer)
                assert waiting.wait(10)
                deadline, blocked = monotonic() + 10, False
                while monotonic() < deadline:
                    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                        blocked = observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='business_item_waiter' AND wait_event_type='Lock')")).scalar()
                    if blocked:
                        break
                    sleep(.05)
                if not blocked:
                    winner.rollback()
                    raise AssertionError("Peer never reached item scope lock")
                sharing.configure(winner, "owner", domain, monitor, expected_version=parent.version,
                    visibility="private", responsible_user_id=None, confirmed=True, now=now)
                winner.commit()
                assert pending.result(timeout=10) == "business_monitor_not_found"
        with db.session() as session:
            assert work.read(session, "owner", domain, monitor, item, now=now)["history"] == current["history"]
    # A public restriction can be inserted when no deny row previously existed.
    # Start its transaction first, observe the decision blocked on the source
    # advisory lock, then commit the restriction: no new owner/comment may persist.
    from helvetic_lens import tender_rights
    from helvetic_lens.tender_models import TenderDossierVersion
    monitor, item, now, _ = targets["tenders"]
    with db.session() as session:
        before = work.read(session, "owner", "tenders", monitor, item, now=now)
        publication = session.get(TenderDossierVersion, before["binding"]["revision_id"]).publication_id
    with db.session() as operator:
        tender_rights.restrict(operator, scope="publication", target_id=publication,
            policy_reference="synthetic concurrent source withdrawal", now=now)
        started = Event()
        def blocked_decision():
            with db.session() as session:
                session.execute(text("SET LOCAL application_name = 'business_item_source_waiter'"))
                started.set()
                try:
                    work.act(session, "owner", "tenders", monitor, item, now=now,
                        expected_version=before["version"], expected_binding=before["binding"],
                        assigned_user_id="owner", comment="Forbidden after source withdrawal", decision="no_bid")
                    session.commit()
                    return "unexpected_write"
                except DomainError as error:
                    return error.code
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(blocked_decision)
            assert started.wait(10)
            deadline, blocked = monotonic() + 10, False
            while monotonic() < deadline:
                with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                    blocked = observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='business_item_source_waiter' AND wait_event_type='Lock')")).scalar()
                if blocked:
                    break
                sleep(.05)
            if not blocked:
                operator.rollback()
                raise AssertionError("Decision did not wait for source restriction")
            operator.commit()
            assert pending.result(timeout=10) == "tender_publication_unavailable"
    with db.session() as session:
        after = work.read(session, "owner", "tenders", monitor, item, now=now)
        assert after["version"] == before["version"] and after["state"] == "unavailable"
        assert after["assigned"] is None and after["history"] == []
        assert session.scalar(select(func.count()).select_from(WorkEvent).where(WorkEvent.tender_dossier_id == item)) == 1
    print("PostgreSQL: populated migration/metadata, simultaneous three-domain decision CAS, append-only audit and observed scope/source withdrawal lock races passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "helvetic_business_item_check":
        parser.error("Use only an empty localhost helvetic_business_item_check database.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-item-work-") as artifacts:
        db = Database(Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts)), organization_id="org-a")
        try:
            db.migrate()
            check(db)
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
