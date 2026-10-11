"""Opt-in fetcher for additional MICA type spectra.

NOT used by the default ``run`` path and never imported by the pipeline, so the
engine stays fully offline for CI. Surfaced only via
``marsgis-engine fetch-references``. Downloads a single small ASCII ``.tab``
(and its ``.lbl`` when present) with a timeout and a size cap — this is a
single-file fetch, never a bulk archive mirror.

Verified reachable this session (HTTP 200): the PDS Geosciences typespec
archive. The ``crismtypespectra.rsl.wustl.edu`` mirror named in some docs
returned 404 for these product ids, so the PDS Geosciences host is used as the
authoritative source.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path

from ..errors import EngineError
from ..logging_utils import get_logger

_log = get_logger("fetch")

#: Authoritative, verified-reachable PDS public-domain typespec archive.
BASE_URL = "https://pds-geosciences.wustl.edu/mro/mro-m-crism-4-typespec-v1/mrocr_8001/data/"
#: Documented alternative mirror (not always serving these product ids).
ALT_BASE_URL = "https://crismtypespectra.rsl.wustl.edu/mrocr_8001/data/"

#: Hard cap on a single reference download (these files are ~30 KB).
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 30


class FetchError(EngineError):
    """A reference download failed (network / HTTP / size cap)."""

    exit_code = 4


def _download(url: str, dest: Path) -> Path:
    _log.info("fetching %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "marsgis-engine"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
            data = resp.read(MAX_BYTES + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise FetchError(f"could not download {url}: {exc}") from exc
    if len(data) > MAX_BYTES:
        raise FetchError(
            f"refusing {url}: exceeds {MAX_BYTES} byte single-file cap "
            "(this fetcher is for one small .tab, not bulk archives)"
        )
    dest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    _log.info("wrote %s (%d bytes, sha256=%s)", dest, len(data), digest)
    return dest


def fetch_reference(mica_key: str, dest_dir: str | Path) -> Path:
    """Fetch ``crism_typespec_<mica_key>.tab`` (+ .lbl) into ``dest_dir``.

    Returns the path to the downloaded ``.tab``. The companion ``.lbl`` is
    fetched best-effort and its absence is not an error.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    key = mica_key.strip().lower().removeprefix("crism_typespec_").removesuffix(".tab")
    tab_name = f"crism_typespec_{key}.tab"

    tab_path = _download(BASE_URL + tab_name, dest_dir / tab_name)

    lbl_name = f"crism_typespec_{key}.lbl"
    try:
        _download(BASE_URL + lbl_name, dest_dir / lbl_name)
    except FetchError:
        _log.info("no companion .lbl for %s (continuing)", key)

    return tab_path
