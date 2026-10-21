"""Regression tests for per-client quota identity (audit H3 + H4).

H3: an unvalidated, client-chosen X-API-Key was hashed into the quota
fingerprint, so a random key per request bypassed every per-client limit.
H4: behind the compose nginx, the backend saw only the proxy's IP, so every
visitor shared a single quota bucket.
"""

from __future__ import annotations

import uuid

import yaml

from app.config import REPO_ROOT

BODY = {"observation_id": "frt00003e12", "algorithm": "SAM", "reference_id": "mica_carbonate_mg"}


async def test_random_api_key_does_not_bypass_quota(client_factory):
    """H3: rotating an unvalidated X-API-Key must not mint fresh quota buckets."""
    async with client_factory(MAX_JOBS_PER_HOUR_PER_CLIENT="2") as client:
        codes = []
        for _ in range(3):
            r = await client.post(
                "/api/analysis-jobs", json=BODY, headers={"X-API-Key": uuid.uuid4().hex}
            )
            codes.append(r.status_code)
        assert codes == [202, 202, 429]


async def test_validated_api_keys_get_separate_buckets(client_factory):
    """With REQUIRE_API_KEY, a validated key is still a distinct client."""
    async with client_factory(
        REQUIRE_API_KEY="true",
        API_KEYS='["key-a","key-b"]',
        MAX_JOBS_PER_HOUR_PER_CLIENT="1",
    ) as client:
        a1 = await client.post("/api/analysis-jobs", json=BODY, headers={"X-API-Key": "key-a"})
        a2 = await client.post("/api/analysis-jobs", json=BODY, headers={"X-API-Key": "key-a"})
        b1 = await client.post("/api/analysis-jobs", json=BODY, headers={"X-API-Key": "key-b"})
        assert (a1.status_code, a2.status_code, b1.status_code) == (202, 429, 202)


async def test_clients_behind_proxy_get_separate_buckets(client_factory):
    """H4: with TRUST_FORWARDED_FOR, the proxy-appended (right-most) hop is the
    client, so two visitors behind one nginx no longer share a bucket, and a
    spoofed left-most hop cannot change a client's identity."""
    async with client_factory(
        TRUST_FORWARDED_FOR="true", MAX_JOBS_PER_HOUR_PER_CLIENT="1"
    ) as client:

        async def post(xff: str) -> int:
            r = await client.post("/api/analysis-jobs", json=BODY, headers={"X-Forwarded-For": xff})
            return r.status_code

        assert await post("10.0.0.1") == 202
        assert await post("10.0.0.2") == 202  # different visitor, own bucket
        # Same real client (right-most hop) with a spoofed left-most hop.
        assert await post("6.6.6.6, 10.0.0.1") == 429


def test_compose_backend_trusts_proxy_forwarded_for():
    """H4: the compose backend sits behind nginx, so it must trust XFF by default."""
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    value = str(compose["services"]["backend"]["environment"]["TRUST_FORWARDED_FOR"])
    assert value.endswith("true}") or value == "true", value
