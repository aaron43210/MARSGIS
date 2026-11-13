"""TLS trust for outbound calls to NASA services.

A host-level ``SSL_CERT_FILE`` (e.g. an old macOS ``/etc/ssl/cert.pem``) can lack
newer roots such as *SSL.com TLS RSA Root CA 2022*, which the PDS ODE/Geosciences
servers chain to. httpx honours that variable and then rejects valid NASA
certificates. We always trust the maintained ``certifi`` bundle, plus whatever the
host bundle adds, so a stale host file can only add trust, never remove it.
"""

from __future__ import annotations

import os
import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    import certifi

    ctx = ssl.create_default_context(cafile=certifi.where())
    for extra in (os.environ.get("SSL_CERT_FILE"), os.environ.get("REQUESTS_CA_BUNDLE")):
        if extra and os.path.isfile(extra):
            try:
                ctx.load_verify_locations(cafile=extra)
            except (OSError, ssl.SSLError):
                pass
    return ctx


def ca_bundle_path() -> str:
    """CA file for libcurl inside GDAL (/vsicurl)."""
    import certifi

    return certifi.where()
