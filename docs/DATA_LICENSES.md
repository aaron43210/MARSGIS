# Data provenance, licensing & scientific-integrity disclaimer

## Scientific-integrity disclaimer (mandatory)

A candidate Spectral Angle Mapper (SAM) spectral match produced by MarsGIS is
**never** presented as a confirmed mineral deposit. SAM reports the spectral
angle between an observed pixel spectrum and a laboratory/type reference; a small
angle is a **candidate** similarity that requires independent corroboration
(geologic context, additional instruments, peer review) before any mineralogical
claim. The continuous angle raster is always retained alongside any thresholded
candidate mask, and the candidate caveat is a required field on every result.

The bundled offline sample (`engine/sample_data/`) is **synthetic** and exists
only for deterministic, network-free testing and CI. It is labeled SYNTHETIC
throughout and must never be presented as a real detection.

## Source data (fetched via services — NOT redistributed)

MarsGIS honors a strict **no-bulk-download** constraint: NASA/USGS source data is
fetched from public services on demand and cached locally; archives are never
mirrored into this repository.

| Source | Access | Attribution |
| ------ | ------ | ----------- |
| CRISM MTRDR discovery — PDS ODE REST API | live proxy + cache | NASA/JPL-Caltech/JHUAPL (MRO/CRISM) |
| CRISM MTRDR cubes — PDS Geosciences archive | stream one observation on demand | NASA/JPL-Caltech/JHUAPL |
| CRISM MICA type spectra (`.tab`) | tiny public-domain subset bundled in `engine/src/marsgis_engine/data/mica/` | NASA/JPL-Caltech/JHUAPL |
| MOLA (ClrShade, DEM) basemaps | NASA Mars Trek WMTS (direct browser fetch) | NASA/GSFC |
| Viking MDIM21 color mosaic | NASA Mars Trek WMTS | USGS/NASA |
| THEMIS Day IR mosaic | NASA Mars Trek WMTS | NASA/JPL-Caltech/ASU |
| USGS SIM 3292 geologic map | USGS pygeoapi OGC API-Features | USGS/NASA |

PDS/ODE usage should cite the relevant PDS dataset DOIs and the ODE REST service
per their citation guidance.

## Licensing

| Artifact | License |
| -------- | ------- |
| Source code | **MIT** (see `LICENSE`) |
| Bundled **synthetic** sample data (`engine/sample_data/`) | **CC0-1.0** |
| Documentation (`docs/`, `README.md`) | **CC-BY-4.0** |
| NASA/USGS source data | Public domain / U.S. Government work; fetched via services, not redistributed. Attribution as above. |

The bundled MICA `.tab` type spectra are U.S. public-domain PDS products included
as small reference package data; see `engine/src/marsgis_engine/data/mica/NOTICE.txt`.
