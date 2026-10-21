# Contributing

Thanks for your interest in MarsGIS. Bug reports, fixes and documentation improvements are all
welcome.

## Getting set up

```bash
cp .env.example .env
make up            # full stack in Docker
make precommit     # install the pre-commit hooks
```

For working without Docker (Python 3.12, Node 24), see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Before opening a pull request

```bash
make test          # engine + backend (pytest) and frontend (vitest)
make lint          # ruff + eslint
make typecheck     # mypy + tsc
```

For `packages/mars-globe`, also run `npm test` and `npm run test:browser` inside that directory.

- Keep each pull request to one change, and add or update tests with it.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`fix(backend): …`,
  `feat(frontend): …`).
- If you change an API shape, regenerate the contract with `python contracts/gen_openapi.py` and
  update the TypeScript types in `frontend/src/types/`.

## Data and scientific claims

- Don't commit archive data. Only small synthetic fixtures belong in the repo; the pre-commit
  hook rejects files over 256 KB.
- Results are candidate spectral matches. Don't word anything in the UI, docs or outputs as a
  confirmed mineral detection, and keep synthetic data labelled as synthetic.

## Reporting bugs

Open an issue with steps to reproduce, what you expected and what happened. For security
problems, follow [SECURITY.md](SECURITY.md) instead.
