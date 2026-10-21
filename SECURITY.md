# Security policy

## Reporting a vulnerability

Please don't open a public issue for security problems. Report them privately through
GitHub's [private vulnerability reporting](https://github.com/aaron43210/MARSGIS/security/advisories/new)
or by email to aaronr43210@gmail.com.

Include the affected component (frontend, backend, engine or `mars-globe`), the version or commit,
and steps to reproduce. You should get a reply within a week.

## Supported versions

Fixes go into the latest release on `main`, and into the latest `mars-globe` release on npm.

## Deployment note

The development Docker Compose stack is unauthenticated and binds only to `127.0.0.1`. A public
deployment needs `REQUIRE_API_KEY=true`, strong values for `SECRET_KEY` and
`POSTGRES_PASSWORD`, TLS and a reverse proxy in front of the backend.
