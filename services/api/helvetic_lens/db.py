from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command

from .config import Settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, settings: Settings):
        settings.storage_path.mkdir(parents=True, exist_ok=True)
        options = {"pool_pre_ping": True}
        if settings.db_url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in settings.db_url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(settings.db_url, **options)
        if settings.db_url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=10000")

        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self):
        directory = Path(__file__).resolve().parent.parent
        config = Config(str(directory / "alembic.ini"))
        config.set_main_option("script_location", str(directory / "alembic"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
