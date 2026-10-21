# Changelog

## 1.0.0 — 2026-10-18

First stable release. The public API is unchanged from 0.1.0 and is now covered
by semver.

### Fixed
- ESM output now uses explicit `.js` import paths, so the package loads in
  plain Node, SSR frameworks, test runners (Vitest/Jest) and native browser
  `import` — not only through a bundler.
- Importing the package where `HTMLElement` is undefined (Node/SSR) no longer
  throws.
- `sideEffects` now marks the standalone entry, so bundlers don't drop the
  `<mars-globe>` auto-registration.

### Changed
- `setBasemap`, `basemapUrl` and `basemapProvider` throw a descriptive error for
  unknown basemap ids instead of a `TypeError`.
- Added the `./package.json` export and `engines.node >= 18`.

### Added
- Unit tests (`npm test`) and a headless-Chrome test of all three usage modes
  (`npm run test:browser`).
