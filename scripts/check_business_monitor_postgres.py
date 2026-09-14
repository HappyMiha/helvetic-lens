"""Rehearse business scope migration and races on an empty localhost scratch DB."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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
from helvetic_lens import business_monitor_sharing as sharing
from helvetic_lens.business_monitor_models import BusinessMonitorScopeEvent
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Base, Database
from helvetic_lens.models import Organization, OrganizationMembership, User
from test_business_monitor_sharing import create

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def change(db, domain, monitor, actor, version, responsible, *, visibility="workspace"):
    with db.session() as session:
        result = sharing.configure(session, actor, domain, monitor, expected_version=version,
            visibility=visibility, responsible_user_id=responsible, confirmed=True, now=NOW)
        session.commit()
        return result


def check(db):
    with db.session(include_all_organizations=True) as session:
        session.add_all([Organization(id="org-a", name="A", slug="a"), Organization(id="org-b", name="B", slug="b")])
        session.add_all([User(id=user, name=user, email=f"{user}@example.test", password_hash="unused") for user in ("owner", "peer")])
        session.flush()
        session.add_all([OrganizationMembership(organization_id="org-a", user_id=user, role="organization_admin") for user in ("owner", "peer")])
        session.commit()
    ids = {domain: create(db, domain) for domain in sharing.MODELS}
    # The previous schema contains genuine monitors and configuration revisions.
    # Upgrade must preserve those rows as private, without assigning a colleague.
    with db.engine.connect() as connection:
        config = Config(str(ROOT / "services/api/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "5e3b1c257dfa")
        assert "business_monitor_scope_events" not in inspect(connection).get_table_names()
        for prefix in sharing.PREFIXES.values():
            assert "visibility" not in {column["name"] for column in inspect(connection).get_columns(f"{prefix}_monitors")}
            assert connection.execute(text(f"SELECT count(*) FROM {prefix}_monitors")).scalar() == 1
        command.upgrade(config, "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, compare_to:
            name.startswith(("tender_", "trademark_", "auction_", "business_monitor_")) if kind == "table" else True})
        assert compare_metadata(context, Base.metadata) == []
        connection.commit()
    for domain, monitor in ids.items():
        with db.session() as session:
            state = sharing.read(session, "owner", domain, monitor)
            assert state["visibility"] == "private" and state["responsible"] is None
        gate = Barrier(2)
        def writer(responsible):
            gate.wait(timeout=10)
            try:
                return change(db, domain, monitor, "owner", 1, responsible)["monitor_version"]
            except DomainError as error:
                assert error.code == "business_scope_changed"
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(writer, ("owner", "peer")))
        assert sorted(map(str, results)) == ["2", "conflict"]
        with db.session() as session:
            target = getattr(BusinessMonitorScopeEvent, sharing.PREFIXES[domain] + "_monitor_id")
            assert session.scalar(select(func.count()).select_from(BusinessMonitorScopeEvent).where(target == monitor)) == 1

        # Force a peer mutation to wait on the exact monitor being made private.
        # Observing PostgreSQL's lock wait proves the race, not a scheduling guess.
        waiting = Event()
        with db.session() as winner:
            sharing.monitor_for(winner, "owner", domain, monitor, write=True)
            def peer():
                with db.session() as session:
                    session.execute(text("SET LOCAL application_name = 'business_scope_waiter'"))
                    waiting.set()
                    try:
                        sharing.configure(session, "peer", domain, monitor, expected_version=2,
                            visibility="workspace", responsible_user_id="peer", confirmed=True, now=NOW)
                        session.commit()
                        return "unexpected_write"
                    except DomainError as error:
                        return error.code
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(peer)
                assert waiting.wait(10)
                deadline = monotonic() + 10
                blocked = False
                while monotonic() < deadline:
                    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                        blocked = observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='business_scope_waiter' AND wait_event_type='Lock')")).scalar()
                    if blocked:
                        break
                    sleep(.05)
                if not blocked:
                    winner.rollback()
                    raise AssertionError("Peer never reached the monitor lock")
                sharing.configure(winner, "owner", domain, monitor, expected_version=2,
                    visibility="private", responsible_user_id=None, confirmed=True, now=NOW)
                winner.commit()
                assert pending.result(timeout=10) == "business_monitor_not_found"
        with db.session() as session:
            current = sharing.read(session, "owner", domain, monitor)
            assert current["visibility"] == "private" and len(current["history"]) == 2
    print("PostgreSQL: three-domain additive migration/downgrade, metadata parity, concurrent CAS and observed lock-wait access withdrawal passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "helvetic_business_scope_check":
        parser.error("Use only an empty localhost helvetic_business_scope_check database.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-business-scope-") as artifacts:
        db = Database(Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts)), organization_id="org-a")
        try:
            db.migrate()
            check(db)
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
