"""Startup schema bootstrap.

- SQLite dev: ``SQLModel.metadata.create_all`` (instant, no migration step).
- PostgreSQL prod: ``alembic upgrade head`` (owns the PostGIS extension, the IAU
  104905 ``spatial_ref_sys`` row, geometry columns and GiST indexes).
"""

from __future__ import annotations

import anyio
from sqlmodel import SQLModel

from app.config import Settings, get_settings

# Importing models registers every table on SQLModel.metadata.
from app.db import models  # noqa: F401
from app.db.base import get_engine
from app.logging import get_logger

_log = get_logger("marsgis.migrate")


def _alembic_upgrade(settings: Settings) -> None:  # pragma: no cover - prod path
    from alembic import command
    from alembic.config import Config

    from app.config import BACKEND_DIR

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.sync_database_url)
    command.upgrade(cfg, "head")


async def migrate(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    engine = get_engine()

    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        _log.info("migrate.sqlite_create_all", tables=len(SQLModel.metadata.tables))
        return

    if settings.run_migrations_on_startup:
        await anyio.to_thread.run_sync(_alembic_upgrade, settings)
        _log.info("migrate.alembic_upgrade_head")
    else:
        _log.warning("migrate.skipped", reason="RUN_MIGRATIONS_ON_STARTUP=false")
