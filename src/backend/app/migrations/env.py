from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.models.task import Base


config = context.config
database_path = config.attributes.get("database_path")
if database_path is None:
    raise RuntimeError("A database path must be supplied explicitly by the migration runner.")

target_metadata = Base.metadata
connectable = create_engine(URL.create("sqlite", database=str(database_path)))

with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
