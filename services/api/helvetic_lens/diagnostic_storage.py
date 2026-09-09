"""Short lock waits for optional telemetry, without changing domain transactions."""
from contextlib import contextmanager

LOCK_WAIT_MS = 250
STATEMENT_MS = 500


@contextmanager
def diagnostic_session(db):
    # Keep the physical connection checked out until SQLite's connection-level
    # timeout has been restored. Session.commit() must not release it early.
    # Pool acquisition still follows the application's configured pool timeout.
    with db.engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        previous = None
        if sqlite:
            previous = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
            connection.rollback()
        try:
            with connection.begin():
                if sqlite:
                    connection.exec_driver_sql(f"PRAGMA busy_timeout={LOCK_WAIT_MS}")
                elif connection.dialect.name == "postgresql":
                    connection.exec_driver_sql(f"SET LOCAL lock_timeout = '{LOCK_WAIT_MS}ms'")
                    connection.exec_driver_sql(f"SET LOCAL statement_timeout = '{STATEMENT_MS}ms'")
                with db.session() as session:
                    session.bind = connection
                    yield session
                    session.flush()
                # The external transaction commits while the short wait applies.
        finally:
            if sqlite and previous is not None:
                try:
                    connection.exec_driver_sql(f"PRAGMA busy_timeout={int(previous)}")
                    connection.rollback()
                except Exception:
                    # Never return a connection with leaked diagnostic settings.
                    connection.invalidate()
                    raise
