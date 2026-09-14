"""Exercise private evidence downloads and observed revocation races on scratch PostgreSQL."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from helvetic_lens import business_monitor_sharing as sharing
from helvetic_lens import monitoring_evidence_export as exports
from helvetic_lens import trademark_sources
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.models import Organization, OrganizationMembership, User
from helvetic_lens.monitoring_centre import MODELS
from helvetic_lens.monitoring_evidence_ask import Record
from pytest import MonkeyPatch
from test_business_monitor_sharing import configure
from test_monitoring_evidence_export import (
    login,
    test_business_decisions_belong_to_selected_source_and_shared_access_is_rechecked,
)
from test_monitoring_evidence_versions import fixture

CASES = ("tenders", "ip", "auctions", "scope_race", "source_race")


def seed_people(db):
    with db.session(include_all_organizations=True) as session:
        session.add(Organization(id="org-a", name="Synthetic", slug="synthetic"))
        session.add_all(User(id=user, name=user, email=f"{user}@example.invalid", password_hash="unused")
            for user in ("owner", "peer", "viewer"))
        session.flush()
        session.add_all(OrganizationMembership(organization_id="org-a", user_id=user,
            role="viewer" if user == "viewer" else "organization_admin") for user in ("owner", "peer", "viewer"))
        session.commit()


def race(db, patch, kind):
    domain = "tenders" if kind == "scope_race" else "ip"
    data = fixture(db, patch, domain)
    monitor, item, now, permit = data
    settings = Settings(_env_file=None, tender_watch_enabled=True, trademark_watch_enabled=True)
    with db.session() as session:
        version = session.get(MODELS[domain], monitor).version
    if kind == "scope_race":
        shared = configure(db, domain, monitor, version=version, now=now)
    actor = login(db, "viewer" if kind == "scope_race" else "owner", now)
    preview = exports.prepare(db, settings, actor, Record(domain, monitor, item), now=now, locale="en-CH")
    started = Event()

    def reader():
        started.set()
        try:
            exports.download(db, settings, actor, preview["confirmation_token"], now=now)
            return "unexpected_download"
        except DomainError as error:
            return error.code

    with db.session() as operator:
        if kind == "scope_race":
            sharing.configure(operator, "owner", domain, monitor, expected_version=shared["monitor_version"],
                visibility="private", responsible_user_id=None, confirmed=True, now=now)
        else:
            trademark_sources.revoke_permission(operator, permit, now=now)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(reader)
            assert started.wait(10)
            deadline, blocked = monotonic() + 15, False
            try:
                while monotonic() < deadline:
                    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                        blocked = observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock')")).scalar()
                    if blocked:
                        break
                    if pending.done():
                        break
                    sleep(.05)
                assert blocked, "Download did not wait for the held access/source change"
            finally:
                operator.commit() if blocked else operator.rollback()
            expected = {"monitoring_evidence_not_found"} if kind == "scope_race" else {
                "monitoring_export_rule_evidence_unavailable", "trademark_source_permission_unavailable"}
            assert pending.result(timeout=15) in expected
    try:
        exports.download(db, settings, actor, preview["confirmation_token"], now=now)
    except DomainError:
        return
    raise AssertionError("Revoked access allowed a repeated download")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--case", choices=CASES, required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1"}
            or url.database != f"hl_evidence_export_{args.case}"):
        parser.error("Use only the named empty localhost scratch database for this case")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database with existing tables")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-evidence-export-") as directory, MonkeyPatch.context() as patch:
        db = Database(Settings(_env_file=None, database_url=args.database_url, data_dir=Path(directory)), organization_id="org-a")
        try:
            db.migrate()
            seed_people(db)
            if args.case in CASES[:3]:
                test_business_decisions_belong_to_selected_source_and_shared_access_is_rechecked(db, patch, args.case)
            else:
                race(db, patch, args.case)
        finally:
            db.engine.dispose()
    print(f"PostgreSQL evidence export {args.case}: passed with synthetic data; no source collection, model or email calls.")


if __name__ == "__main__":
    main()
