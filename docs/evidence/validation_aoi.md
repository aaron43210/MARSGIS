# Validation AOI — scientific defensibility

- Observation: `frt00003e12` — Nili Fossae
- Independent reference: Ehlmann et al. 2008 (Science 322:1828); Mustard et al. 2009 (JGR 114:E00D12)
- Expectation: olivine broad; carbonate present but localized; method discriminates
- Status: **ok**
- Method: band-depth SAM; source: PDS strip of 384 rows
- AOI: [489, 384, 384] (bands, lines, samples) from full [489, 384, 843]; real CRS: True
- Valid pixels: 147456 at threshold 0.3 rad

| mineral | detected fraction | best-match share | bands used |
|---|---|---|---|
| carbonate | 0.000 | 0.001 | 60 |
| olivine | 0.828 | 0.999 | 117 |
| clay | 0.000 | 0.001 | 83 |

**Defensible: False**

- ✅ carbonate_structured_not_saturated
- ❌ discriminates_best_match_not_monopoly
- ✅ olivine_broader_than_carbonate

> Detection depends on the operator threshold and on the ratioed-MICA vs. unratioed-scene caveat recorded in each run's provenance. These are spectral *candidates*, not confirmed deposits; the gate checks that the method is non-degenerate, discriminating, and consistent with the published gross mineralogy — not that any pixel is ground-truth confirmed.

## Reading this result (band-depth SAM, 2026-11-14)

- **Carbonate is localized and spatially coherent.** Of the 1% most carbonate-like
  pixels, 93% touch another one (random scatter would give ~8%), and 2.1% of the
  AOI is within 0.50 rad. That fits localized Mg-carbonate units at Nili Fossae.
- **Olivine is broad:** 83% of pixels within 0.30 rad (97% within 0.40 rad).
- **Why the "best match" check fails:** each mineral is matched in its own
  diagnostic window (olivine 117 bands, clay 83, carbonate 60). Angles from
  windows of different width are not directly comparable, and the wide, smooth
  olivine window gives the smallest angles almost everywhere. Picking the argmin
  across minerals is therefore biased; the app reports each mineral separately
  and never makes that cross-mineral comparison.
- **Threshold:** 0.30 rad separates planted carbonate/olivine from background on
  the synthetic cube. On real data carbonate signals are weaker (mixtures), so
  0.30 rad is strict for carbonate. A carbonate-specific threshold was NOT tuned
  on this scene, to avoid fitting the test.
- The previous whole-spectrum SAM record (0.10 rad) flagged carbonate on 82% of
  this AOI, i.e. it could not discriminate. Band depth is the better method.
