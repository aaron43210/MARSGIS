"""Consistent logging for the library and the CLI.

Logs go to stderr so stdout stays clean for machine-readable CLI output
(e.g. printed artifact paths). The :func:`log_assumption` helper tags any
provenance-relevant assumption (fallback CRS, assumed .tab column order, …)
with an ``ASSUMED:`` prefix at WARNING level, so the distinction between
VERIFIED facts and ASSUMED ones is auditable in the run log.
"""

from __future__ import annotations

import logging
import sys

_LOGGER_NAME = "marsgis_engine"
_CONFIGURED = False


def setup_logging(level: str | int = "INFO", *, json: bool = False) -> logging.Logger:
    """Configure the package logger with a single stderr handler.

    Idempotent: repeated calls only adjust the level, they do not stack
    handlers (important when the CLI and an importing backend both call it).
    """
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)

    if not _CONFIGURED:
        handler = logging.StreamHandler(stream=sys.stderr)
        if json:
            fmt = (
                '{"ts":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
            )
        else:
            fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the ``marsgis_engine`` namespace."""
    if name is None or name == _LOGGER_NAME:
        return logging.getLogger(_LOGGER_NAME)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


def log_assumption(logger: logging.Logger, message: str) -> None:
    """Log a provenance-relevant assumption with an ``ASSUMED:`` prefix.

    Use for anything the engine inferred rather than read directly from the
    data (fallback CRS, default .tab column order, unit guesses).
    """
    logger.warning("ASSUMED: %s", message)
