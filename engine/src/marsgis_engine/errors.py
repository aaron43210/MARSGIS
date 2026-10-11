"""Typed exception hierarchy for the MarsGIS science engine.

Every library-level failure raises an :class:`EngineError` subclass carrying a
short, operator-facing ``hint``. ``cli.py`` maps the subclass to a stable
process exit code:

====================  =========================================  ====
Exception             Meaning                                    Exit
====================  =========================================  ====
(argparse usage)      bad invocation / unknown args              2
CubeReadError         cube file missing / unreadable             3
HeaderParseError      ENVI header malformed                      3
ReferenceError        MICA .tab / alias unreadable or malformed  3
WavelengthOverlapError too few overlapping good bands            3
CRSMissingError       informational (fallback CRS attached)      0
WriteError            output raster / JSON could not be written  4
====================  =========================================  ====

The data/parse family (exit 3) all derive from :class:`DataError` so callers
can catch the whole class at once.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all marsgis_engine errors.

    Parameters
    ----------
    message:
        Human-readable description of what went wrong.
    hint:
        Optional short remediation suggestion surfaced by the CLI.
    """

    #: Default CLI exit code for this error family (overridden by subclasses).
    exit_code: int = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.hint:
            return f"{self.message} (hint: {self.hint})"
        return self.message


class DataError(EngineError):
    """A data / parsing problem with an input file (CLI exit code 3)."""

    exit_code = 3


class CubeReadError(DataError):
    """The ENVI cube (.img/.hdr) is missing or cannot be read."""


class HeaderParseError(DataError):
    """The ENVI header could not be parsed into wavelengths / metadata."""


class ReferenceError(DataError):
    """A MICA reference spectrum (.tab) or mineral alias is invalid."""


class WavelengthOverlapError(DataError):
    """Fewer than ``config.MIN_OVERLAP_BANDS`` good bands overlap.

    Raised rather than silently matching on a degenerate band set, which would
    produce meaningless spectral angles.
    """


class CRSMissingError(EngineError):
    """Informational: the input lacked a resolvable CRS.

    This is *not* fatal — the pipeline attaches the configured Mars-2000
    equirectangular fallback WKT and records ``crs_is_fallback=True`` in the
    provenance record. It exists so callers can detect the condition
    programmatically; the CLI does not abort on it.
    """

    exit_code = 0


class WriteError(EngineError):
    """An output artifact (COG / JSON / report) could not be written."""

    exit_code = 4
