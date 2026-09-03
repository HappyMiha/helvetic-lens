from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria
from sqlalchemy.pool import StaticPool

from alembic import command

from .config import Settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(
        self,
        settings: Settings,
        organization_id: str = "00000000-0000-0000-0000-000000000001",
    ):
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

        self.organization_id = organization_id
        self._organization_id = ContextVar(
            f"helvetic_lens_organization_{id(self)}", default=organization_id
        )
        self._session_factory = sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

        # Until authentication supplies the active organization in HL-034, each app
        # instance has one immutable tenant context. Tests can create two instances
        # over the same database to prove isolation without trusting a request header.
        @event.listens_for(self._session_factory, "after_begin")
        def remember_organization(session: Session, _transaction, _connection):
            session.info.setdefault("organization_id", self.current_organization_id)

        @event.listens_for(self._session_factory, "before_flush")
        def assign_organization(session: Session, _flush_context, _instances):
            from urllib.parse import urlsplit

            from .models import ORGANIZATION_SCOPED_MODELS, Law

            organization_id = session.info.setdefault("organization_id", self.current_organization_id)
            for record in session.new:
                if isinstance(record, ORGANIZATION_SCOPED_MODELS) and not record.organization_id:
                    record.organization_id = organization_id
                if isinstance(record, Law):
                    record.canonical_identity = record.canonical_identity or record.url.lower()
                    if record.owner_organization_id is None and (
                        urlsplit(record.url).hostname or ""
                    ).lower() not in {"fedlex.admin.ch", "fedlex.data.admin.ch"}:
                        record.owner_organization_id = organization_id

        @event.listens_for(self._session_factory, "do_orm_execute")
        def restrict_organization(execute_state):
            if (
                not execute_state.is_select
                or execute_state.execution_options.get("include_all_organizations")
                or execute_state.session.info.get("include_all_organizations")
            ):
                return
            from .models import ORGANIZATION_SCOPED_MODELS, SHARED_CORPUS_MODELS

            organization_id = execute_state.session.info.setdefault(
                "organization_id", self.current_organization_id
            )
            statement = execute_state.statement
            for model in ORGANIZATION_SCOPED_MODELS:
                statement = statement.options(
                    with_loader_criteria(
                        model,
                        model.organization_id == organization_id,
                        include_aliases=True,
                    )
                )
            for model in SHARED_CORPUS_MODELS:
                statement = statement.options(
                    with_loader_criteria(
                        model,
                        (model.owner_organization_id.is_(None))
                        | (model.owner_organization_id == organization_id),
                        include_aliases=True,
                    )
                )
            execute_state.statement = statement

    @property
    def current_organization_id(self) -> str:
        return self._organization_id.get()

    @contextmanager
    def organization_context(self, organization_id: str):
        token = self._organization_id.set(organization_id)
        try:
            yield
        finally:
            self._organization_id.reset(token)

    def session(self, *, include_all_organizations: bool = False) -> Session:
        return self._session_factory(
            info={
                "organization_id": self.current_organization_id,
                "include_all_organizations": include_all_organizations,
            }
        )

    def migrate(self):
        directory = Path(__file__).resolve().parent.parent
        config = Config(str(directory / "alembic.ini"))
        config.set_main_option("script_location", str(directory / "alembic"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
