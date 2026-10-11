# Validation AOI — scientific defensibility

- Observation: `frt00003e12` — Nili Fossae
- Independent reference: Ehlmann et al. 2008 (Science 322:1828); Mustard et al. 2009 (JGR 114:E00D12)
- Expectation: olivine broad; carbonate present but localized; method discriminates
- Status: **ok**
- AOI: [489, 384, 384] (bands, lines, samples) from full [489, 828, 843]; real CRS: True
- Valid pixels: 147456 at threshold 0.1 rad

| mineral | detected fraction | best-match share | bands used |
|---|---|---|---|
| carbonate | 0.824 | 0.196 | 238 |
| olivine | 0.365 | 0.262 | 238 |
| clay | 0.746 | 0.541 | 238 |

**Defensible: True**

- ✅ carbonate_structured_not_saturated
- ✅ discriminates_best_match_not_monopoly
- ✅ olivine_broader_than_carbonate

> Detection depends on the operator threshold and on the ratioed-MICA vs. unratioed-scene caveat recorded in each run's provenance. These are spectral *candidates*, not confirmed deposits; the gate checks that the method is non-degenerate, discriminating, and consistent with the published gross mineralogy — not that any pixel is ground-truth confirmed.
