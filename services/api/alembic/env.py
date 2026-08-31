from sqlalchemy import create_engine

from alembic import context
from regwatch import models  # noqa: F401
from regwatch.config import Settings
from regwatch.db import Base

config = context.config
target_metadata = Base.metadata


def run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=Settings().db_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = create_engine(Settings().db_url)
    with engine.connect() as connection:
        run(connection)
