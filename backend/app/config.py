"""Application settings (pydantic-settings).

A single ``Settings`` object, cached by :func:`get_settings`, is the only place
environment configuration is read. With no ``.env`` present every field falls
back to the zero-setup default documented in ``.env.example`` (SQLite + the
in-process worker + the in-process engine seam, fully offline).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
# repo root (contains contracts/, engine/, backend/)
REPO_ROOT = BACKEND_DIR.parent

JobBackend = Literal["inprocess", "arq"]
EngineMode = Literal["inprocess", "subprocess", "container"]
CubeSource = Literal["sample", "archive"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "dev"
    debug: bool = True
    log_level: str = "INFO"
    json_logs: bool = False
    git_sha: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./storage/marsgis.db"
    run_migrations_on_startup: bool = True
    seed_on_startup: bool = True

    # --- Storage ---
    storage_root: str = "./storage"

    # --- Job queue ---
    job_backend: JobBackend = "inprocess"
    redis_url: str = "redis://localhost:6379/0"
    job_concurrency: int = Field(default=2, ge=1, le=32)
    job_timeout_s: int = Field(default=600, ge=1)
    max_concurrent_jobs_per_client: int = Field(default=2, ge=1)
    max_jobs_per_hour_per_client: int = Field(default=20, ge=1)

    # --- Engine seam ---
    engine_mode: EngineMode = "inprocess"
    engine_image: str = "ghcr.io/OWNER/marsgis-engine:latest"
    engine_timeout_s: int = Field(default=600, ge=1)
    engine_rlimit_as_mb: int = Field(default=2048, ge=128)
    engine_rlimit_cpu_s: int = Field(default=600, ge=1)
    engine_max_pixels: int = Field(default=4_000_000, ge=1)
    engine_cube_source: CubeSource = "sample"
    sample_cube_path: str = "../engine/sample_data/sample_crism_nili.img"

    # --- Security / abuse limits ---
    require_api_key: bool = False
    api_keys: list[str] = Field(default_factory=list)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024)
    max_aoi_area_km2: float = Field(default=250_000.0, gt=0.0)
    max_mineral_classes: int = Field(default=3, ge=1)
    #: Trust the X-Forwarded-For header for per-client quota/rate keys. OFF by
    #: default (clients can spoof XFF to evade limits). Enable ONLY behind a
    #: trusted reverse proxy; prefer running uvicorn with --proxy-headers so
    #: request.client.host is set correctly and this can stay false.
    trust_forwarded_for: bool = False

    # --- Tiles ---
    tile_size: int = 256
    tile_cache_enabled: bool = False

    @field_validator("cors_origins", "api_keys", mode="before")
    @classmethod
    def _split_list(cls, v: object) -> object:
        """Accept a JSON array or a comma-separated string from the environment."""
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                return json.loads(s)
            return [part.strip() for part in s.split(",") if part.strip()]
        return v

    # --- Derived ---
    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sync_database_url(self) -> str:
        """Blocking URL for Alembic and the arq worker's bootstrap."""
        url = self.database_url
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite", 1)
        if url.startswith("postgresql+asyncpg"):
            return url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
        return url

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_root)
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        return p

    @property
    def results_path(self) -> Path:
        return self.storage_path / "results"

    @property
    def cache_path(self) -> Path:
        return self.storage_path / "tilecache"

    @property
    def sample_cube_abspath(self) -> Path:
        p = Path(self.sample_cube_path)
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        return p

    def ensure_dirs(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)
        if self.tile_cache_enabled:
            self.cache_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
