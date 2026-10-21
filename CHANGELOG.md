# Changelog

All notable changes to MarsGIS are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Entries follow [Conventional Commits](https://www.conventionalcommits.org/) and
may be auto-generated from the commit history at release time. The version is
derived from the git tag (`vX.Y.Z`); there is no hand-maintained VERSION file.

## [Unreleased]

### Added
- Monorepo scaffold: `frontend/`, `backend/`, `engine/`, `contracts/`, `docker/`, `docs/`.
- Containerization: multi-stage, non-root (uid 10001) images for engine, backend
  and frontend; `docker compose` stack (PostGIS + backend + frontend by default;
  engine / worker / redis / titiler behind profiles); localhost-only port binds.
- `Makefile` task entrypoint, `.env.example`, pre-commit hygiene, hadolint config.
- CI (`ci.yml`) and tag-driven multi-arch release (`release.yml`) workflows.
- Scientific-integrity disclaimer surfaced throughout: a candidate spectral match
  is never presented as a confirmed mineral deposit.

[Unreleased]: https://github.com/aaron43210/MARSGIS/commits/main
