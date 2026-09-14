"""Observe operator receipt lock races in an explicitly empty localhost scratch DB."""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep

from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api")]

from helvetic_lens import monitoring_source_attention as attention
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.membership_locks import lock_platform_users
from helvetic_lens.models import MonitoringSourceAcknowledgement as Receipt
from helvetic_lens.models import User


def run(db, settings, mode):
    user = "operator-" + mode
    now = datetime.now(UTC)
    with db.session() as session:
        session.add(User(id=user, email=user + "@example.invalid", name="Synthetic operator",
            password_hash="unused", platform_admin=True))
        session.commit()
    with db.session() as session:
        issue = attention.read(session, settings, user, now=now)["items"][0]
    ready, pids = Event(), []

    def waiter():
        with db.session() as session:
            pids.append(session.scalar(text("SELECT pg_backend_pid()")))
            ready.set()
            try:
                value = attention.acknowledge(session, settings, user, issue["key"], issue["fingerprint"], now=now)
                session.commit()
                return value
            except DomainError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.session() as blocker:
            lock_platform_users(blocker, user)
            if mode == "duplicate":
                first = attention.acknowledge(blocker, settings, user, issue["key"], issue["fingerprint"], now=now)
            elif mode == "revoke":
                blocker.get(User, user).platform_admin = False
                blocker.flush()
            else:
                blocker.execute(delete(User).where(User.id == user))
            future = pool.submit(waiter)
            assert ready.wait(10)
            deadline, observed = monotonic() + 10, False
            while monotonic() < deadline:
                with db.engine.connect() as connection:
                    observed = connection.scalar(text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"), {"pid": pids[0]})
                if observed:
                    break
                sleep(.03)
            assert observed, "The real PostgreSQL wait was not observed"
            blocker.commit()
        result = future.result(timeout=15)
    if mode == "duplicate":
        assert result == first
    else:
        assert result == "platform_admin_required", result
    with db.session() as session:
        count = session.scalar(select(func.count()).select_from(Receipt).where(Receipt.user_id == user))
        assert count == (1 if mode == "duplicate" else 0)
    print(f"PostgreSQL {mode}: observed lock wait and exact expected outcome")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "hl_source_attention":
        parser.error("Only the named empty localhost scratch database is allowed")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing a nonempty database")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-source-attention-") as directory:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(directory))
        db = Database(settings)
        try:
            db.migrate()
            for mode in ("duplicate", "revoke", "erase"):
                run(db, settings, mode)
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
