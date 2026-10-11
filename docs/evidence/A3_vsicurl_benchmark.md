# A3 — Remote `/vsicurl` vs. local CRISM read

- Observation: `frt00003e12`  bbox (W,S,E,N): [76.9404, 22.1347, 77.2127, 22.3863]
- AOI window: 48 px   status: **ok**
- Metadata (resolve + header): **4.967 s**
- Full cube: [489, 828, 843] (bands, lines, samples); declared bands 489
- AOI read: [489, 48, 48] in **650.102 s**
- Transferred: **105.452 MiB** over **1419** HTTP range requests (parsed from GDAL VSICURL debug; `null` = not surfaced by this GDAL build)

No download-reduction percentage is claimed except directly from the transferred-bytes figure above versus the full-cube size.
