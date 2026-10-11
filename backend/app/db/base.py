"""Async engine + sessionmaker shared by the API and the in-process worker.

A single async engine keeps request handlers and the in-process worker on one
event loop; the worker offloads only the CPU-bound engine call to a thread and
keeps every DB write on the loop, so no cross-thread session sharing occurs.
SQLite gets WAL + a busy timeout + foreign keys so the API and worker can write
concurrently without 'database is locked'.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _configure_sqlite(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # pragma: no cover - driver callback
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create the process-wide async engine (idempotent)."""
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine
    settings = settings or get_settings()
    settings.ensure_dirs()

    connect_args: dict = {}
    if settings.is_sqlite:
        connect_args["timeout"] = 30

    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if settings.is_sqlite:
        _configure_sqlite(_engine)

    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        return init_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
