"""I/O subpackage: ENVI cube reading, MICA reference parsing, COG writing,
provenance + report emission, and the opt-in reference fetcher.

Nothing in this subpackage performs radiometric re-calibration or
reprojection; CRISM MTRDR input is treated as analysis-ready I/F and its grid
is preserved losslessly on output.
"""

from __future__ import annotations
