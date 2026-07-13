from alembic import context
from sqlalchemy import engine_from_config, pool

from app.settings import settings
from app.database import Base
from app.models.schema import *  # noqa: F401 (ensure all models are loaded)

config = context.config

# Inject DB URL dynamically
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL_SYNC
)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,  # safe for future SQLite/testing
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")
else:
    run_migrations_online()
