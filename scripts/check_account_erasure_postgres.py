"""Account-erasure races on one explicitly named empty localhost scratch DB."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from helvetic_lens.account_deletion import erase, preview
from helvetic_lens.auth import AuthService
from helvetic_lens.business_monitor_handover import handover
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database, utcnow
from helvetic_lens.membership_locks import lock_organization
from helvetic_lens.models import OrganizationMembership, User
from helvetic_lens.monitoring_centre import MODELS
from test_monitoring_configuration_drafts import example

PASSWORD = "Synthetic account erasure test password"


def register(auth):
    identifier = str(uuid4())
    return auth.register(email=identifier + "@example.test", password=PASSWORD,
        name="Synthetic erasure fixture", organization_name=identifier)[0]


def join(db, auth, owner, peer):
    with db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(organization_id=owner.organization_id, user_id=peer.user_id,
            role="organization_admin"))
        session.commit()
    return auth.switch_organization(peer, owner.organization_id)


def confirmed(auth, identity):
    value = preview(auth, identity)
    assert value["can_delete"], value["blockers"]
    return {"password": PASSWORD, "confirmed": True, "confirmation_token": value["confirmation_token"],
        "erase_workspaces": [row["id"] for row in value["workspaces"] if row["disposition"] == "erase_private_workspace"]}


def delete_racer(auth, identity, body, barrier):
    barrier.wait(timeout=10)
    try:
        return erase(auth, identity, **body)["deleted"]
    except DomainError as error:
        assert error.code in {"account_deletion_changed", "authentication_required"}, error.code
        return False


def check(db, auth):
    owner, peer = register(auth), register(auth)
    peer = join(db, auth, owner, peer)
    bodies = [confirmed(auth, person) for person in (owner, peer)]
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(delete_racer, auth, person, body, barrier)
            for person, body in zip((owner, peer), bodies, strict=True)]
        assert sorted(future.result(timeout=20) for future in futures) == [False, True]
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(OrganizationMembership)
            .join(User, User.id == OrganizationMembership.user_id).where(
                OrganizationMembership.organization_id == owner.organization_id,
                OrganizationMembership.role == "organization_admin", User.active.is_(True))) == 1
    print("Two simultaneous account deletions retain the shared workspace and its last active administrator.")

    admins = [register(auth), register(auth)]
    with db.session(include_all_organizations=True) as session:
        for person in admins:
            session.get(User, person.user_id).platform_admin = True
        session.commit()
    bodies = [confirmed(auth, person) for person in admins]
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(delete_racer, auth, person, body, barrier)
            for person, body in zip(admins, bodies, strict=True)]
        assert sorted(future.result(timeout=20) for future in futures) == [False, True]
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(User).where(User.platform_admin.is_(True), User.active.is_(True))) == 1
    print("Concurrent erasure cannot delete the last active platform administrator.")

    owner, peer = register(auth), register(auth)
    peer = join(db, auth, owner, peer)
    body = confirmed(auth, owner)
    with db.session(include_all_organizations=True) as winner:
        lock_organization(winner, owner.organization_id)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(erase, auth, owner, **body)
            waiting, deadline = False, monotonic() + 10
            while monotonic() < deadline:
                with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                    waiting = observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock')")).scalar()
                if waiting:
                    break
                sleep(.05)
            if not waiting:
                winner.rollback()
                raise AssertionError("Account erase never reached the held workspace lock")
            member = winner.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == owner.organization_id,
                OrganizationMembership.user_id == owner.user_id))
            member.role = "viewer"
            winner.commit()
            try:
                pending.result(timeout=20)
                raise AssertionError("An obsolete role preview was accepted")
            except DomainError as error:
                assert error.code == "account_deletion_changed"
    print("An observed PostgreSQL workspace lock wait rechecks the changed administrator role.")

    for domain in ("tenders", "ip", "auctions"):
        owner, peer = register(auth), register(auth)
        peer = join(db, auth, owner, peer)
        identifier = str(uuid4())
        with db.session(include_all_organizations=True) as session:
            session.add(MODELS[domain](id=identifier, organization_id=owner.organization_id, owner_user_id=peer.user_id,
                request_key=identifier, request_hash="a" * 64, configuration=example(domain), visibility="workspace"))
            session.commit()
        body = confirmed(auth, owner)
        barrier = Barrier(2)

        def incoming():
            barrier.wait(timeout=10)
            try:
                with db.organization_context(owner.organization_id), db.session() as session:
                    handover(session, peer.user_id, domain, identifier, expected_version=1,
                        successor_user_id=owner.user_id, confirmed=True, now=utcnow())
                    session.commit()
                return True
            except DomainError as error:
                assert error.code == "business_handover_target_unavailable", error.code
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            deleted = executor.submit(delete_racer, auth, owner, body, barrier)
            transferred = executor.submit(incoming)
            assert sorted((deleted.result(timeout=20), transferred.result(timeout=20))) == [False, True]
        with db.session(include_all_organizations=True) as session:
            monitor = session.get(MODELS[domain], identifier)
            assert monitor is not None and session.get(User, monitor.owner_user_id) is not None
        print(f"{domain}: competing incoming ownership and account deletion retain the shared monitor.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "helvetic_lens_account_erasure_check":
        parser.error("Use only the empty localhost helvetic_lens_account_erasure_check database.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-account-erasure-") as artifacts:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts),
            app_environment="test", allow_anonymous_dev=False, session_cookie_secure=False)
        db = Database(settings)
        try:
            db.migrate()
            check(db, AuthService(db, settings))
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
