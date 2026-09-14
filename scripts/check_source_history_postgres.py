"""Observe source-history retry concurrency in an empty named localhost database."""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep

from sqlalchemy import create_engine, delete, event, inspect, select, text
from sqlalchemy.engine import make_url

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "services/api")]

from helvetic_lens.config import Settings
from helvetic_lens.db import Database
from helvetic_lens.models import MonitoringOperationalSample as Sample
from helvetic_lens.monitoring_source_history import capture


def verify(db, settings):
    now = datetime.now(UTC)
    assert capture(db, settings, now=now)["sampled"] == 10
    with db.session() as session:
        original = [{"channel": r.channel, "bucket_at": r.bucket_at, "recorded_at": r.recorded_at,
            "values": r.values} for r in session.scalars(select(Sample))]
        session.execute(delete(Sample))
        session.commit()
    pids, ready = [], Event()
    def insert_wait(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO monitoring_operational_samples"):
            pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
            ready.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.engine.begin() as blocker:
            blocker.execute(Sample.__table__.insert(), original)
            event.listen(db.engine, "before_cursor_execute", insert_wait)
            try:
                future = pool.submit(capture, db, settings, now=now)
                assert ready.wait(10)
                deadline, observed = monotonic() + 10, False
                while monotonic() < deadline:
                    with db.engine.connect() as connection:
                        observed = connection.scalar(text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"), {"pid": pids[0]})
                    if observed:
                        break
                    sleep(.03)
                assert observed, "Expected actual PostgreSQL unique-key wait"
            finally:
                event.remove(db.engine, "before_cursor_execute", insert_wait)
        result = future.result(timeout=15)
    assert result["sampled"] == 0
    with db.session() as session:
        actual = [{"channel": r.channel, "bucket_at": r.bucket_at, "recorded_at": r.recorded_at,
            "values": r.values} for r in session.scalars(select(Sample))]
    assert sorted(actual, key=lambda r: r["channel"]) == sorted(original, key=lambda r: r["channel"])
    print("Observed PostgreSQL unique-key wait: ten immutable samples, duplicate retry inserts zero, original metadata preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "hl_source_history":
        parser.error("Only the named empty localhost scratch database is permitted")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing nonempty database")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-source-history-") as directory:
        settings = Settings(_env_file=None, database_url=args.database_url, data_dir=Path(directory))
        db = Database(settings)
        try:
            db.migrate()
            verify(db, settings)
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
