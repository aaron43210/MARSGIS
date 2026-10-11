"""The single seam between the backend and the science engine.

``ENGINE_MODE`` selects the implementation:

- ``inprocess`` (dev/CI default): ``import marsgis_engine`` and call ``run_sam``.
- ``subprocess``: shell out to the ``marsgis-engine`` CLI with CPU/memory rlimits
  and a wall-clock timeout (a hard process boundary for untrusted workloads).
- ``container``: ``docker run`` the pinned ``ghcr.io/<owner>/marsgis-engine`` image.

All three return a uniform :class:`EngineResult`. The exact engine signatures
live only here, so a change to the engine API touches one file.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.config import Settings, get_settings
from app.core.constants import MARS2000_EQUIRECT_WKT
from app.errors import EngineError
from app.logging import get_logger

_log = get_logger("marsgis.engine")

ProgressCb = Callable[[float, str], None]

# MineralClass -> engine mineral alias (engine data/minerals.json keys).
_CLASS_TO_ALIAS = {
    "carbonate": "carbonate",
    "olivine": "olivine",
    "phyllosilicate": "clay",
}

ANGLE_SUFFIX = "_SAM_angle.tif"
CANDIDATE_SUFFIX = "_SAM_candidate.tif"
PROVENANCE_SUFFIX = "_provenance.json"


@dataclass
class EngineRequest:
    job_id: str
    result_id: str
    observation_id: str
    reference_id: str
    mineral_name: str
    mineral_class: str
    cube_path: Path
    threshold_rad: float
    continuum_removed: bool
    wavelength_subset_nm: tuple[float, float] | None
    out_dir: Path
    is_synthetic: bool
    timestamp: str | None = None

    @property
    def reference_spec(self) -> str:
        alias = _CLASS_TO_ALIAS.get(self.mineral_class)
        if alias is None:
            raise EngineError(
                f"No engine reference for mineral class '{self.mineral_class}'",
                detail="Supported classes: carbonate, olivine, phyllosilicate.",
            )
        return alias


@dataclass
class EngineResult:
    angle_path: Path
    mask_path: Path
    score_path: Path | None
    provenance: dict[str, Any]
    stats: dict[str, Any]
    engine_version: str
    engine_image: str
    is_synthetic: bool
    software: list[dict[str, str]] = field(default_factory=list)


class EngineAdapter(Protocol):
    def version(self) -> str: ...
    def analyze(self, request: EngineRequest, progress_cb: ProgressCb) -> EngineResult: ...


def _read_provenance(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _build_run_params(request: EngineRequest):
    """Construct the engine RunParams, tolerant of field drift."""
    try:
        from marsgis_engine import RunParams  # type: ignore
    except Exception:  # pragma: no cover - depends on engine install
        from marsgis_engine.science.pipeline import RunParams  # type: ignore

    window = request.wavelength_subset_nm or (1000.0, 2600.0)
    candidate_kwargs: dict[str, Any] = {
        "threshold_rad": request.threshold_rad,
        "threshold_units": "rad",
        "window_nm": tuple(window),
        "mask_bad_bands": True,
        "continuum_removal": request.continuum_removed,
        "resample_method": "linear",
        "out_dir": str(request.out_dir),
        "out_prefix": request.result_id,
        "crs_fallback_wkt": MARS2000_EQUIRECT_WKT,
        "timestamp": request.timestamp,
    }
    valid = {f.name for f in dataclasses.fields(RunParams)}
    kwargs = {k: v for k, v in candidate_kwargs.items() if k in valid}
    return RunParams(**kwargs)


class InProcessEngine:
    """Default dev/CI adapter: import marsgis_engine and call run_sam."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def version(self) -> str:
        try:
            import marsgis_engine  # type: ignore

            return getattr(marsgis_engine, "__version__", "unknown")
        except Exception:
            return "unavailable"

    def analyze(self, request: EngineRequest, progress_cb: ProgressCb) -> EngineResult:
        try:
            import marsgis_engine  # type: ignore
            from marsgis_engine import run_sam  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on engine install
            raise EngineError(
                "marsgis_engine is not importable (ENGINE_MODE=inprocess)",
                detail=str(exc),
            ) from exc

        request.out_dir.mkdir(parents=True, exist_ok=True)
        params = _build_run_params(request)
        progress_cb(0.15, "running SAM (in-process engine)")
        try:
            sam = run_sam(str(request.cube_path), request.reference_spec, params)
        except Exception as exc:
            raise EngineError("engine run_sam failed", detail=str(exc)) from exc
        progress_cb(0.85, "engine finished; collecting outputs")

        angle = Path(sam.angle_path)
        mask = Path(sam.candidate_path)
        prov_path = getattr(sam, "provenance_path", None)
        provenance = _read_provenance(Path(prov_path)) if prov_path else {}
        stats = dict(getattr(sam, "stats", {}) or {})
        return EngineResult(
            angle_path=angle,
            mask_path=mask,
            score_path=None,
            provenance=provenance,
            stats=stats,
            engine_version=getattr(marsgis_engine, "__version__", "unknown"),
            engine_image=self._settings.engine_image,
            is_synthetic=request.is_synthetic,
        )


def _rlimit_preexec(settings: Settings):  # pragma: no cover - POSIX only
    if os.name != "posix":
        return None
    import resource

    def _apply() -> None:
        cpu = settings.engine_rlimit_cpu_s
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
        mem = settings.engine_rlimit_as_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

    return _apply


class _CliEngine:
    """Shared subprocess/container runner over the marsgis-engine CLI."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _argv(self, request: EngineRequest) -> list[str]:
        raise NotImplementedError

    def version(self) -> str:
        try:
            out = subprocess.run(
                self._base_cmd() + ["version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return (out.stdout or out.stderr).strip() or "unknown"
        except Exception:
            return "unavailable"

    def _base_cmd(self) -> list[str]:
        raise NotImplementedError

    def analyze(self, request: EngineRequest, progress_cb: ProgressCb) -> EngineResult:
        request.out_dir.mkdir(parents=True, exist_ok=True)
        argv = self._argv(request)
        progress_cb(0.15, f"running SAM ({self._settings.engine_mode} engine)")
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self._settings.engine_timeout_s,
                preexec_fn=_rlimit_preexec(self._settings) if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineError("engine timed out", detail=str(exc)) from exc
        except OSError as exc:
            raise EngineError("could not launch engine", detail=str(exc)) from exc

        if proc.returncode != 0:
            raise EngineError(
                "engine exited non-zero",
                detail=(proc.stderr or proc.stdout or "")[-2000:],
            )
        progress_cb(0.85, "engine finished; collecting outputs")

        prefix = request.result_id
        out = request.out_dir
        angle = out / f"{prefix}{ANGLE_SUFFIX}"
        mask = out / f"{prefix}{CANDIDATE_SUFFIX}"
        prov = out / f"{prefix}{PROVENANCE_SUFFIX}"
        if not angle.is_file() or not mask.is_file():
            raise EngineError(
                "engine did not produce expected outputs",
                detail=f"missing {angle.name} / {mask.name} in {out}",
            )
        provenance = _read_provenance(prov)
        return EngineResult(
            angle_path=angle,
            mask_path=mask,
            score_path=None,
            provenance=provenance,
            stats=dict(provenance.get("results", {})),
            engine_version=str(provenance.get("software", {}).get("version", "unknown"))
            if isinstance(provenance.get("software"), dict)
            else "unknown",
            engine_image=self._settings.engine_image,
            is_synthetic=request.is_synthetic,
        )


class SubprocessEngine(_CliEngine):
    def _base_cmd(self) -> list[str]:
        return [sys.executable, "-m", "marsgis_engine"]

    def _argv(self, request: EngineRequest) -> list[str]:
        argv = self._base_cmd() + [
            "run",
            "--cube",
            str(request.cube_path),
            "--mineral",
            request.reference_spec,
            "--method",
            "SAM",
            "--threshold",
            str(request.threshold_rad),
            "--threshold-units",
            "rad",
            "--out",
            str(request.out_dir),
            "--out-prefix",
            request.result_id,
        ]
        if request.timestamp:
            argv += ["--timestamp", request.timestamp]
        return argv


class ContainerEngine(_CliEngine):
    def _base_cmd(self) -> list[str]:
        return ["docker", "run", "--rm", "--network", "none", self._settings.engine_image]

    def _argv(self, request: EngineRequest) -> list[str]:
        cube = request.cube_path.resolve()
        out = request.out_dir.resolve()
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            f"{self._settings.engine_rlimit_as_mb}m",
            "-v",
            f"{cube.parent}:/in:ro",
            "-v",
            f"{out}:/out",
            self._settings.engine_image,
            "run",
            "--cube",
            f"/in/{cube.name}",
            "--mineral",
            request.reference_spec,
            "--method",
            "SAM",
            "--threshold",
            str(request.threshold_rad),
            "--threshold-units",
            "rad",
            "--out",
            "/out",
            "--out-prefix",
            request.result_id,
        ]


def build_engine_adapter(settings: Settings | None = None) -> EngineAdapter:
    settings = settings or get_settings()
    mode = settings.engine_mode
    if mode == "subprocess":
        return SubprocessEngine(settings)
    if mode == "container":
        return ContainerEngine(settings)
    return InProcessEngine(settings)
