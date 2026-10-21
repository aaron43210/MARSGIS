<!-- MarsGIS pull request -->

## Summary

<!-- What does this change and why? Link any related issue. -->

## Checklist

- [ ] Tests pass locally (`make test`) and relevant tests were added/updated.
- [ ] Docs updated where behavior or interfaces changed.
- [ ] **No bulk data committed** — only tiny synthetic sample fixtures (the
      pre-commit large-file guard blocks files > 256 KB).
- [ ] No secrets committed (`.env` stays local; `.env.example` is the template).
- [ ] Scientific integrity: no candidate spectral match is presented as a
      confirmed mineral deposit; synthetic/sample data is labeled SYNTHETIC.
- [ ] SemVer impact noted (patch / minor / major) and commits follow
      Conventional Commits.
