#!/usr/bin/env python3
"""Generate the committed A2 fixture: a small REAL CRISM MTRDR subset.

Streams a tiny AOI of a real MTRDR cube from the PDS archive via the backend's
``fetch_subset_cube`` and writes it under ``engine/tests/fixtures/`` so the A2
end-to-end test can run offline. Network + minutes; run once.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "engine" / "src"))

OBS = "frt00003e12"
BBOX = (76.9404, 22.1347, 77.2127, 22.3863)
OUT = ROOT / "engine" / "tests" / "fixtures" / "real_mtrdr_subset"


def main() -> int:
    from app.config import Settings
    from app.services.cube_fetch import fetch_subset_cube

    OUT.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    settings.archive_subset_px = 24  # keep the committed fixture small (~2 MB)

    print(f"streaming {OBS} AOI {BBOX} px={settings.archive_subset_px} ...", flush=True)
    try:
        path = fetch_subset_cube(settings, OBS, BBOX, OUT)
    except Exception:
        traceback.print_exc()
        return 1
    if not path:
        print("FAILED: fetch_subset_cube returned None (ODE/network/url resolution)", flush=True)
        return 1
    print(f"WROTE {path} ({path.stat().st_size} bytes)", flush=True)
    hdr = path.with_suffix(".hdr")
    print(f"WROTE {hdr} ({hdr.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
