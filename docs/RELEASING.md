# Releasing

## Versioning

- **SemVer** (`MAJOR.MINOR.PATCH`). The version is derived from the **git tag**
  (`vX.Y.Z`) — there is no hand-maintained VERSION file in the monorepo.
- Commits follow **Conventional Commits**; `CHANGELOG.md` uses Keep a Changelog
  and may be auto-generated from history at release time.

## Cutting a release

```bash
git tag v1.2.3
git push origin v1.2.3
```

Pushing a `v*` tag triggers `.github/workflows/release.yml`, which:

1. Logs in to GHCR with the workflow `GITHUB_TOKEN` (`packages: write`).
2. Derives image tags from the git tag via `docker/metadata-action`
   (`X.Y.Z`, `X.Y`, `latest`, `sha-…`).
3. Builds and pushes **multi-arch** (`linux/amd64,linux/arm64`) images for
   `marsgis-engine`, `marsgis-backend`, `marsgis-frontend` with **SBOM** and
   **provenance** attestations.
4. Attests build provenance for each pushed digest.
5. Creates a GitHub Release with generated notes.

### First publish

The first push may create the GHCR packages as **private**. Set each package's
visibility to **public** and link it to the repository in the GHCR package
settings. Confirm `GHCR_OWNER` (defaults to the repository owner's login).

### Verifying a published image

```bash
docker buildx imagetools inspect ghcr.io/aaron43210/marsgis-engine:1.2.3
gh attestation verify oci://ghcr.io/aaron43210/marsgis-engine:1.2.3 --owner aaron43210
```

## Zenodo archiving

With the **GitHub–Zenodo integration** enabled for the repository, each published
GitHub Release is archived automatically and minted a DOI. After the first mint:

- Update `CITATION.cff` (`version`, `doi`) and `.zenodo.json`.
- Commit so subsequent releases carry the correct citation metadata.

### Archiving run outputs (reproducibility)

A classification **run** should be archived as a separate Zenodo deposition that
records, at minimum:

- the **engine image digest** used (`ghcr.io/aaron43210/marsgis-engine@sha256:…`),
- the **CRISM observation id** processed,
- the **MICA reference** mineral used and SAM parameters,
- the provenance JSON emitted by the engine.

This ties every result to the exact code and inputs that produced it — and keeps
the record honest that results are **candidate matches, not confirmed deposits**.

## Multi-arch build note

`arm64` images build under QEMU in CI, which is slow and can time out. If needed,
restrict `arm64` to the release workflow (PR CI builds `amd64` only) or add a
native arm64 runner. The release uses buildx GHA cache to amortize rebuilds.
