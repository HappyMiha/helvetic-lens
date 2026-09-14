"""A held database write lock must not turn telemetry into a long reader wait."""
import time

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_brief_reuse import observed
from test_digest_briefs import artifacts, execution, ready
from test_interest_brief_reader import read as current_read

from helvetic_lens.diagnostic_storage import LOCK_WAIT_MS, diagnostic_session

__all__ = ["artifacts", "execution"]


@pytest.mark.parametrize("target", ["reuse", "integration"])
def test_locked_reuse_counter_returns_saved_answer_without_waiting_for_owner(execution, target):
    service, _, saved = ready(execution)
    assert current_read(execution)["status"] == "available"
    checked_in_timeouts = []
    diagnostic_writes, lock_failures = [], []
    tables = ("brief_reuse_observations", "integration_logs")

    def diagnostic_table(sql):
        return next((table for table in tables if (sql or "").lstrip().startswith(f"INSERT INTO {table} ")), None)

    def before_write(connection, _cursor, sql, _params, _context, _many):
        table = diagnostic_table(sql)
        if table is None:
            return
        # Inspect the actual connection at the blocked INSERT. Measuring the
        # whole reader also includes unrelated model-runtime validation and CPU
        # scheduling on the release host, so it does not measure lock waiting.
        cursor = connection.connection.driver_connection.cursor()
        try:
            if connection.dialect.name == "sqlite":
                lock = cursor.execute("PRAGMA busy_timeout").fetchone()[0]
                statement = None
            else:
                cursor.execute("SHOW lock_timeout")
                lock = cursor.fetchone()[0]
                cursor.execute("SHOW statement_timeout")
                statement = cursor.fetchone()[0]
            diagnostic_writes.append((table, lock, statement))
        finally:
            cursor.close()

    def write_error(context):
        table = diagnostic_table(context.statement)
        if table:
            error = context.original_exception
            code = getattr(error, "sqlite_errorcode", None) if context.dialect.name == "sqlite" else getattr(error, "sqlstate", None)
            lock_failures.append((table, code))

    def checkin(dbapi, _record):
        if dbapi is not None and service.db.engine.dialect.name == "sqlite":
            cursor = dbapi.cursor()
            try:
                checked_in_timeouts.append(cursor.execute("PRAGMA busy_timeout").fetchone()[0])
            finally:
                cursor.close()
    event.listen(service.db.engine, "checkin", checkin)
    event.listen(service.db.engine, "before_cursor_execute", before_write)
    event.listen(service.db.engine, "handle_error", write_error)
    try:
        with service.db.engine.connect() as owner:
            transaction = owner.begin()
            try:
                if target == "reuse":
                    owner.execute(text("UPDATE brief_reuse_observations SET projections = projections + 1 WHERE assessment_id = :identity"), {"identity": saved["id"]})
                elif owner.dialect.name == "postgresql":
                    owner.exec_driver_sql("LOCK TABLE integration_logs IN SHARE MODE")
                else:
                    owner.exec_driver_sql("UPDATE integration_logs SET duration_ms = duration_ms")
                response = current_read(execution)
                assert response["status"] == "available" and response["result"] == saved["result"]
                # Owner still holds the lock: success cannot come from its release.
                assert transaction.is_active
                sqlite = owner.dialect.name == "sqlite"
                limits = (250, None) if sqlite else ("250ms", "500ms")
                assert sorted(diagnostic_writes) == sorted((table, *limits) for table in tables)
                # Both SQLite writers conflict with its database-wide lock.
                # PostgreSQL blocks only the deliberately locked table. Verify
                # actual timeout failures and no retry loop, not just a setting.
                blocked = tables if sqlite else (tables[0 if target == "reuse" else 1],)
                assert sorted(table for table, _ in lock_failures) == sorted(blocked)
                assert all((isinstance(code, int) and code & 255 == 5) if sqlite else code == "55P03"
                    for _, code in lock_failures)
            finally:
                transaction.rollback()
    finally:
        event.remove(service.db.engine, "checkin", checkin)
        event.remove(service.db.engine, "before_cursor_execute", before_write)
        event.remove(service.db.engine, "handle_error", write_error)
    recorded = 2 if target == "integration" and service.db.engine.dialect.name == "postgresql" else 1
    assert observed(service, saved["id"])["items"][0]["projections"] == recorded
    if service.db.engine.dialect.name == "sqlite":
        assert checked_in_timeouts and set(checked_in_timeouts) == {10000}
    current_read(execution)
    assert observed(service, saved["id"])["items"][0]["projections"] == recorded + 1
    assert len(execution[4]["generated"]) == 1


@pytest.mark.parametrize("fail", [False, True])
def test_diagnostic_timeout_is_local_and_restored_after_commit_or_error(execution, fail):
    db = execution[0].db
    sqlite = db.engine.dialect.name == "sqlite"
    query = "PRAGMA busy_timeout" if sqlite else "SHOW lock_timeout"
    with db.engine.connect() as connection:
        original = connection.exec_driver_sql(query).scalar_one()
    try:
        with diagnostic_session(db) as session:
            value = session.connection().exec_driver_sql(query).scalar_one()
            assert value == (LOCK_WAIT_MS if sqlite else f"{LOCK_WAIT_MS}ms")
            if fail:
                raise ValueError("synthetic diagnostic failure")
            session.commit()
    except ValueError:
        assert fail
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql(query).scalar_one() == original


def test_postgres_slow_diagnostic_statement_is_cancelled(execution):
    db = execution[0].db
    if db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL statement timeout requires the isolated PostgreSQL suite")
    started = time.monotonic()
    with pytest.raises(DBAPIError):
        with diagnostic_session(db) as session:
            session.execute(text("SELECT pg_sleep(5)"))
    assert time.monotonic() - started < 2
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql("SHOW statement_timeout").scalar_one() == "0"


def test_integration_log_failure_does_not_echo_provider_payload(harness, caplog):
    service = harness[2]
    def fail(_conn, _cursor, sql, _params, _context, _many):
        if "INSERT INTO integration_logs" in sql:
            raise RuntimeError("synthetic-private-provider-payload")
    event.listen(service.db.engine, "before_cursor_execute", fail)
    try:
        service.integration_logger.record(provider="docker", operation="test", method="POST",
            url="http://127.0.0.1:12436/v1/chat/completions", status="success", duration_ms=1,
            response_body={"answer":"synthetic-private-provider-payload"})
    finally:
        event.remove(service.db.engine, "before_cursor_execute", fail)
    assert "Could not persist an integration log" in caplog.text
    assert "synthetic-private-provider-payload" not in caplog.text


def test_sqlite_restore_failure_discards_connection_instead_of_leaking_timeout(execution):
    db = execution[0].db
    if db.engine.dialect.name != "sqlite":
        pytest.skip("Connection-level PRAGMA restoration is SQLite-specific")
    invalidated = []
    def fail_restore(_conn, _cursor, sql, _params, _context, _many):
        if sql == "PRAGMA busy_timeout=10000":
            raise RuntimeError("synthetic restoration failure")
    def invalidate(_dbapi, _record, _error):
        invalidated.append(True)
    event.listen(db.engine, "before_cursor_execute", fail_restore)
    event.listen(db.engine, "invalidate", invalidate)
    try:
        with pytest.raises(RuntimeError, match="synthetic restoration failure"):
            with diagnostic_session(db) as session:
                session.execute(text("SELECT 1"))
    finally:
        event.remove(db.engine, "before_cursor_execute", fail_restore)
        event.remove(db.engine, "invalidate", invalidate)
    assert invalidated == [True]
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 10000
