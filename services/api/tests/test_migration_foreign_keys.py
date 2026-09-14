"""A real SQLite batch replacement preserves children without weakening normal writes."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from helvetic_lens.migration_runtime import migration_foreign_keys


@pytest.fixture
def connection():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id) ON DELETE CASCADE)")
        connection.exec_driver_sql("INSERT INTO parent VALUES (1)")
        connection.exec_driver_sql("INSERT INTO child VALUES (2, 1)")
        connection.commit()
        yield connection
    engine.dispose()


def replace_parent(connection):
    connection.exec_driver_sql("CREATE TABLE parent_copy (id INTEGER PRIMARY KEY, added TEXT)")
    connection.exec_driver_sql("INSERT INTO parent_copy(id) SELECT id FROM parent")
    connection.exec_driver_sql("DROP TABLE parent")
    connection.exec_driver_sql("ALTER TABLE parent_copy RENAME TO parent")


def test_replacement_retains_child_and_restores_enforcement(connection):
    with migration_foreign_keys(connection):
        replace_parent(connection)
    assert connection.exec_driver_sql("SELECT * FROM child").all() == [(2, 1)]
    assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    with pytest.raises(IntegrityError):
        connection.exec_driver_sql("INSERT INTO child VALUES (3, 999)")
    connection.rollback()
    assert connection.exec_driver_sql("SELECT * FROM child").all() == [(2, 1)]


@pytest.mark.parametrize("failure", ["exception", "orphan"])
def test_failed_migration_rolls_back_schema_data_and_gate(connection, failure):
    with pytest.raises(RuntimeError):
        with migration_foreign_keys(connection):
            replace_parent(connection)
            if failure == "exception":
                raise RuntimeError("Synthetic migration failure")
            connection.exec_driver_sql("INSERT INTO child VALUES (3, 999)")
    assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert connection.exec_driver_sql("SELECT * FROM child").all() == [(2, 1)]
    assert [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(parent)")] == ["id"]


def test_pending_application_write_is_neither_committed_nor_discarded(connection):
    connection.exec_driver_sql("INSERT INTO child VALUES (3, 1)")
    with pytest.raises(RuntimeError, match="pending writes"):
        with migration_foreign_keys(connection):
            pytest.fail("Must refuse before entering migration")
    assert connection.exec_driver_sql("SELECT count(*) FROM child").scalar() == 2
    assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    connection.rollback()
    assert connection.exec_driver_sql("SELECT count(*) FROM child").scalar() == 1
