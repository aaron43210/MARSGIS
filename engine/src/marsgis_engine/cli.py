"""argparse CLI for the MarsGIS science engine.

Thin wrapper over the library — no science logic lives here. Subcommands::

    marsgis-engine run --cube CUBE (--mineral ALIAS | --reference PATH) \\
        --method SAM --threshold 0.10 --out OUTDIR [options]
    marsgis-engine info --cube CUBE
    marsgis-engine list-minerals
    marsgis-engine fetch-references (--mineral KEY | --all) --dest DIR
    marsgis-engine version

Exit codes: 0 ok, 2 usage, 3 data/parse, 4 io.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence

from . import config
from ._version import __version__
from .errors import EngineError
from .logging_utils import get_logger, setup_logging

_log = get_logger("cli")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="marsgis-engine",
        description="Spectral Angle Mapper on CRISM MTRDR cubes (candidate "
        "matches, NOT confirmed deposits).",
    )
    p.add_argument("--version", action="version", version=f"marsgis-engine {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # --- run ------------------------------------------------------------
    run = sub.add_parser("run", help="run SAM and write COG + provenance + report")
    run.add_argument("--cube", required=True, help="path to the ENVI .img/.hdr cube")
    ref_grp = run.add_mutually_exclusive_group(required=True)
    ref_grp.add_argument("--mineral", help="bundled alias (carbonate|olivine|clay|...)")
    ref_grp.add_argument("--reference", help="path to a MICA .tab / CSV reference")
    run.add_argument("--method", choices=["SAM"], default="SAM")
    run.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD_RAD)
    run.add_argument("--threshold-units", choices=["rad", "deg"], default="rad")
    run.add_argument("--wmin", type=float, default=None, help="window min (see --wavelength-units)")
    run.add_argument("--wmax", type=float, default=None, help="window max (see --wavelength-units)")
    run.add_argument("--wavelength-units", choices=["nm", "um"], default="nm")
    run.add_argument(
        "--continuum-removal",
        action=argparse.BooleanOptionalAction,
        default=config.DEFAULT_CONTINUUM_REMOVAL,
        help="convex-hull continuum removal on pixel + reference",
    )
    run.add_argument("--resample", choices=["linear", "gaussian"], default=config.DEFAULT_RESAMPLE)
    run.add_argument(
        "--mask-bad-bands",
        action=argparse.BooleanOptionalAction,
        default=config.DEFAULT_MASK_BAD_BANDS,
        help="honour the ENVI bad-band list (bbl)",
    )
    run.add_argument("--out", required=True, help="output directory")
    run.add_argument("--out-prefix", default=config.DEFAULT_OUT_PREFIX)
    run.add_argument(
        "--mars-crs", default=None, help="fallback CRS WKT or code if the header lacks one"
    )
    run.add_argument(
        "--timestamp", default=None, help="ISO-8601 or 'placeholder' for reproducible output"
    )
    run.add_argument("--block-rows", type=int, default=config.DEFAULT_BLOCK_ROWS)
    run.add_argument("--ref-wavelength-col", type=int, default=0)
    run.add_argument("--ref-value-col", type=int, default=1)
    run.add_argument("--ref-wavelength-units", choices=["nm", "um"], default=None)
    run.add_argument("--engine-image", default="", help="engine image ref to record in provenance")
    run.add_argument("--log-level", default="INFO")

    # --- info -----------------------------------------------------------
    info = sub.add_parser("info", help="print cube bands / wavelengths / CRS")
    info.add_argument("--cube", required=True)
    info.add_argument("--log-level", default="WARNING")

    # --- list-minerals --------------------------------------------------
    lm = sub.add_parser("list-minerals", help="list bundled MICA aliases")
    lm.add_argument("--log-level", default="WARNING")

    # --- fetch-references ----------------------------------------------
    fr = sub.add_parser("fetch-references", help="opt-in download of extra MICA .tab")
    fg = fr.add_mutually_exclusive_group(required=True)
    fg.add_argument("--mineral", help="mica_key to fetch (e.g. mg_carbonate)")
    fg.add_argument("--all", action="store_true", help="fetch every bundled mica_key")
    fr.add_argument("--dest", required=True, help="destination directory")
    fr.add_argument("--log-level", default="INFO")

    # --- version --------------------------------------------------------
    sub.add_parser("version", help="print the engine version")

    return p


def _window_nm(args: argparse.Namespace) -> tuple[float, float]:
    lo, hi = config.DEFAULT_WINDOW_NM
    scale = 1000.0 if args.wavelength_units == "um" else 1.0
    if args.wmin is not None:
        lo = args.wmin * scale
    if args.wmax is not None:
        hi = args.wmax * scale
    return (float(lo), float(hi))


def _threshold_rad(args: argparse.Namespace) -> float:
    if args.threshold_units == "deg":
        return math.radians(args.threshold)
    return float(args.threshold)


def _resolve_fallback_crs(spec: str | None) -> str | None:
    """Resolve a --mars-crs WKT/code to a WKT string, or None."""
    if not spec:
        return None
    if "[" in spec:  # already WKT
        return spec
    try:
        from rasterio.crs import CRS

        return CRS.from_user_input(spec).to_wkt()
    except Exception as exc:  # noqa: BLE001
        _log.warning("could not interpret --mars-crs %r (%s); ignoring", spec, exc)
        return None


def _cmd_run(args: argparse.Namespace) -> int:
    from .science.pipeline import RunParams, run_sam

    reference_or_mineral = args.mineral if args.mineral else args.reference
    params = RunParams(
        threshold_rad=_threshold_rad(args),
        threshold_units=args.threshold_units,
        window_nm=_window_nm(args),
        mask_bad_bands=args.mask_bad_bands,
        continuum_removal=args.continuum_removal,
        resample_method=args.resample,
        out_dir=args.out,
        out_prefix=args.out_prefix,
        crs_fallback_wkt=_resolve_fallback_crs(args.mars_crs),
        timestamp=args.timestamp,
        block_rows=args.block_rows,
        engine_image=args.engine_image,
        ref_wavelength_col=args.ref_wavelength_col,
        ref_value_col=args.ref_value_col,
        ref_wavelength_units=args.ref_wavelength_units,
    )
    result = run_sam(args.cube, reference_or_mineral, params)
    stats = result.stats
    print(f"angle      : {result.angle_path}")
    print(f"candidate  : {result.candidate_path}")
    print(f"provenance : {result.provenance_path}")
    print(f"report     : {result.report_path}")
    print(
        f"candidates : {stats['detected_pixel_count']} / {stats['valid_pixel_count']} valid "
        f"({stats['detected_fraction'] * 100.0:.3f}%)  "
        f"[CANDIDATE matches, NOT confirmed deposits]"
    )
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    from .io.envi_reader import load_cube

    cube = load_cube(args.cube)
    wl = cube.wavelengths_nm
    print(f"cube         : {cube.path}")
    print(f"label id     : {cube.label_id}")
    print(f"shape (r,c,b): {cube.rows} x {cube.cols} x {cube.bands}")
    print(f"wavelengths  : {wl.min():.1f} - {wl.max():.1f} nm ({cube.wavelength_units})")
    print(f"good bands   : {cube.n_good_bands} / {cube.bands}")
    print(f"ignore value : {cube.ignore_value}")
    print(f"interleave   : {cube.interleave}")
    print(f"crs fallback : {cube.crs_is_fallback}")
    print(f"transform    : {tuple(round(float(x), 4) for x in list(cube.transform)[:6])}")
    crs = cube.crs
    crs_s = crs.to_wkt() if hasattr(crs, "to_wkt") else str(crs)
    print(f"crs          : {crs_s[:100]}{'...' if len(crs_s) > 100 else ''}")
    return 0


def _cmd_list_minerals(args: argparse.Namespace) -> int:
    from .io.reference import list_minerals

    entries = list_minerals()
    print(f"{'alias(es)':34s} {'mica_key':20s} {'window_nm':14s} file")
    print("-" * 90)
    for e in entries:
        aliases = ", ".join(e.get("alias", []))
        win = e.get("diagnostic_window_nm", [])
        win_s = f"{win[0]:.0f}-{win[1]:.0f}" if len(win) == 2 else ""
        print(f"{aliases:34s} {e.get('mica_key', ''):20s} {win_s:14s} {e.get('file', '')}")
    print(
        f"\n{len(entries)} bundled reference(s). "
        "Real CRISM MICA type spectra (PDS public domain). See data/mica/NOTICE.txt."
    )
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    from .io.fetch import fetch_reference
    from .io.reference import list_minerals

    if args.all:
        keys = sorted({e.get("mica_key", "") for e in list_minerals() if e.get("mica_key")})
    else:
        keys = [args.mineral]
    for key in keys:
        path = fetch_reference(key, args.dest)
        print(f"fetched {key} -> {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    setup_logging(getattr(args, "log_level", "INFO"))

    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "info":
            return _cmd_info(args)
        if args.command == "list-minerals":
            return _cmd_list_minerals(args)
        if args.command == "fetch-references":
            return _cmd_fetch(args)
        if args.command == "version":
            print(__version__)
            return 0
    except EngineError as exc:
        _log.error("%s", exc)
        return int(getattr(exc, "exit_code", 1)) or 1
    except KeyboardInterrupt:  # pragma: no cover
        _log.error("interrupted")
        return 130
    except FileNotFoundError as exc:
        _log.error("file not found: %s", exc)
        return 3

    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
