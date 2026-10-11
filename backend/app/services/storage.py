"""Result storage layout + path-traversal-safe resolution.

Everything lives under ``STORAGE_ROOT/results/<result_id>/``. ``safe_path``
resolves a requested filename inside a result directory and refuses anything that
escapes it (``..``, absolute paths, symlink traversal).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import Settings, get_settings
from app.errors import NotFoundError


def results_root(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    root = settings.results_path
    root.mkdir(parents=True, exist_ok=True)
    return root


def result_dir(result_id: str, *, create: bool = False, settings: Settings | None = None) -> Path:
    # result_id is a server-generated uuid hex; still validate it is a single segment.
    if not result_id or "/" in result_id or "\\" in result_id or result_id in (".", ".."):
        raise NotFoundError("result not found")
    d = results_root(settings) / result_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def safe_path(result_id: str, name: str, *, settings: Settings | None = None) -> Path:
    """Resolve ``name`` strictly inside the result directory, or raise NotFound."""
    base = result_dir(result_id, settings=settings).resolve()
    candidate = (base / name).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise NotFoundError("asset not found") from exc
    if not candidate.is_file():
        raise NotFoundError("asset not found")
    return candidate


def store_file(result_id: str, src: Path, name: str, *, settings: Settings | None = None) -> str:
    """Copy an engine output into the result dir; return the stored basename."""
    d = result_dir(result_id, create=True, settings=settings)
    dest = d / name
    if Path(src).resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    return name


def cleanup_result(result_id: str, *, settings: Settings | None = None) -> None:
    d = result_dir(result_id, settings=settings)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
