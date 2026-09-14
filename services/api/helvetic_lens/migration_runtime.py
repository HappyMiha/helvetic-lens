"""Keep SQLite batch table replacement from cascading into retained records."""

from contextlib import contextmanager


@contextmanager
def migration_foreign_keys(connection):
    if connection.dialect.name != "sqlite":
        yield
        return
    raw = connection.connection.driver_connection
    enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    if not enabled:
        # Preserve the contract of a caller that already manages its own gate.
        yield
        return
    if raw.in_transaction:
        # SQLite ignores a foreign_keys switch inside a physical transaction.
        # Never commit or discard a caller's pending application writes to fix it.
        raise RuntimeError("SQLite schema migration requires a connection without pending writes; commit or roll back the caller's transaction first.")
    raw.execute("PRAGMA foreign_keys=OFF")
    try:
        # The physical savepoint owns only migration work. Its release commits
        # that work before enforcement is restored; failure rolls all of it back.
        with connection.begin_nested():
            yield
            if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("SQLite migration left a foreign-key violation; schema changes were rolled back.")
    except BaseException:
        # ROLLBACK TO SAVEPOINT alone leaves SQLite in a physical transaction.
        raw.rollback()
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")
        if raw.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            connection.invalidate()
            raise RuntimeError("SQLite foreign-key enforcement could not be restored; the connection was discarded.")
