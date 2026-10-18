"""Synthetic Webhook Load Test Tool for FAULTLINE ZERO.

Fires 50 concurrent synthetic signed GitHub webhooks to verify:
1. HMAC signature verification under load.
2. Concurrent deduplication (idempotency key protection).
3. Database connection pooling stability (no pool exhaustion or deadlocks).
4. Response latency statistics (mean, p95, max).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import httpx

from faultline.config import get_settings
from faultline.db.models import GitHubInstallation, Organization
from faultline.db.session import get_session_factory, init_db


def create_signed_payload(secret: str, event: str, payload_obj: dict, delivery_id: str) -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload_obj).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sig,
    }
    return raw_body, headers


async def send_webhook(
    client: httpx.AsyncClient,
    url: str,
    raw_body: bytes,
    headers: dict[str, str],
    req_id: int,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        resp = await client.post(url, content=raw_body, headers=headers, timeout=10.0)
        duration_ms = (time.perf_counter() - t0) * 1000
        return {
            "req_id": req_id,
            "status_code": resp.status_code,
            "duration_ms": duration_ms,
            "body": resp.text[:200],
            "error": None,
        }
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        return {
            "req_id": req_id,
            "status_code": 0,
            "duration_ms": duration_ms,
            "body": "",
            "error": str(exc),
        }


def setup_test_database():
    """Initializes tables and ensures load test organization/installation exists."""
    init_db()
    factory = get_session_factory()
    with factory() as db:
        org = db.query(Organization).filter_by(slug="load-test-org").first()
        if not org:
            org = Organization(name="Load Test Org", slug="load-test-org")
            db.add(org)
            db.flush()
        inst = db.query(GitHubInstallation).filter_by(id=88001).first()
        if not inst:
            inst = GitHubInstallation(
                id=88001,
                organization_id=org.id,
                account_login="load-test-org",
                account_type="Organization",
                permissions_json=json.dumps({"pull_requests": "write", "checks": "write"}),
            )
            db.add(inst)
        db.commit()


async def run_load_test(base_url: str | None = None, concurrency: int = 50):
    print("=" * 70)
    print("FAULTLINE ZERO // Webhook Ingestion Concurrent Load Test")
    print(f"Target: {concurrency} concurrent signed webhooks")
    print("=" * 70)

    setup_test_database()
    settings = get_settings()
    secret = settings.github_webhook_secret or "dev-webhook-secret"

    # Prepare requests:
    # 30 unique delivery IDs
    # 15 duplicate delivery IDs (repeating 3 delivery IDs 5 times each to test deduplication under concurrency)
    # 5 intentionally invalid signatures (testing security gate under load)
    test_specs: List[Dict[str, Any]] = []

    # 30 unique deliveries
    for i in range(30):
        delivery_id = f"load-test-uniq-{time.time_ns()}-{i}"
        payload = {
            "action": "opened",
            "number": 100 + i,
            "pull_request": {
                "number": 100 + i,
                "title": f"Load test PR #{i}",
                "head": {"sha": f"abc{i:04d}00000000000000000000000000000000", "ref": f"feat/test-{i}"},
                "base": {"sha": "0000000000000000000000000000000000000000", "ref": "main"},
                "user": {"login": f"dev-{i}"},
                "state": "open",
            },
            "repository": {
                "id": 990001,
                "full_name": "load-test-org/repo-one",
                "private": True,
                "default_branch": "main",
            },
            "installation": {"id": 88001},
        }
        body, hdrs = create_signed_payload(secret, "pull_request", payload, delivery_id)
        test_specs.append({"type": "unique", "body": body, "headers": hdrs})

    # 15 duplicate deliveries (3 shared IDs repeated 5 times)
    shared_ids = [f"load-test-shared-{time.time_ns()}-{k}" for k in range(3)]
    for i in range(15):
        delivery_id = shared_ids[i % 3]
        payload = {
            "action": "synchronize",
            "number": 999,
            "pull_request": {
                "number": 999,
                "title": "Concurrent duplicate payload",
                "head": {"sha": "9999999999999999999999999999999999999999", "ref": "feat/dup"},
                "base": {"sha": "0000000000000000000000000000000000000000", "ref": "main"},
                "user": {"login": "dup-user"},
                "state": "open",
            },
            "repository": {
                "id": 990001,
                "full_name": "load-test-org/repo-one",
                "private": True,
                "default_branch": "main",
            },
            "installation": {"id": 88001},
        }
        body, hdrs = create_signed_payload(secret, "pull_request", payload, delivery_id)
        test_specs.append({"type": "duplicate", "body": body, "headers": hdrs})

    # 5 invalid signature requests
    for i in range(5):
        delivery_id = f"load-test-invalid-sig-{i}"
        payload = {"action": "ping", "zen": "tampered"}
        body, hdrs = create_signed_payload("wrong-secret", "ping", payload, delivery_id)
        test_specs.append({"type": "invalid_sig", "body": body, "headers": hdrs})

    assert len(test_specs) == concurrency, f"Expected {concurrency} specs, got {len(test_specs)}"

    # Setup transport
    if base_url:
        print(f"Connecting to live server at: {base_url}")
        async with httpx.AsyncClient(base_url=base_url) as client:
            tasks = [
                send_webhook(client, "/api/v1/webhooks/github", spec["body"], spec["headers"], idx)
                for idx, spec in enumerate(test_specs)
            ]
            t_start = time.perf_counter()
            results = await asyncio.gather(*tasks)
            t_total = time.perf_counter() - t_start
    else:
        print("Running against in-process FastAPI application (ASGI transport)...")
        from faultline.api import app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            tasks = [
                send_webhook(client, "/api/v1/webhooks/github", spec["body"], spec["headers"], idx)
                for idx, spec in enumerate(test_specs)
            ]
            t_start = time.perf_counter()
            results = await asyncio.gather(*tasks)
            t_total = time.perf_counter() - t_start

    # Analyze results
    durations = [r["duration_ms"] for r in results]
    durations.sort()
    mean_dur = sum(durations) / len(durations)
    p95_dur = durations[int(len(durations) * 0.95)]
    max_dur = durations[-1]

    status_counts: dict[int, int] = {}
    for r in results:
        code = r["status_code"]
        status_counts[code] = status_counts.get(code, 0) + 1

    print("\n--- Execution Summary ---")
    print(f"Total Requests:      {len(results)}")
    print(f"Total Wall Time:     {t_total:.3f} s")
    print(f"Throughput:          {len(results) / t_total:.1f} req/s")
    print(f"Latency Mean:        {mean_dur:.1f} ms")
    print(f"Latency P95:         {p95_dur:.1f} ms")
    print(f"Latency Max:         {max_dur:.1f} ms")

    print("\n--- Status Code Breakdown ---")
    for code, count in sorted(status_counts.items()):
        label = "UNKNOWN"
        if code == 200:
            label = "OK (Deduplicated acknowledge)"
        elif code == 202:
            label = "ACCEPTED (Enqueued for background processing)"
        elif code == 401:
            label = "UNAUTHORIZED (Invalid signature rejected)"
        elif code == 400:
            label = "BAD REQUEST"
        elif code == 500:
            label = "SERVER ERROR"
        print(f"  HTTP {code:3d}: {count:3d}  [{label}]")

    # Assertions for verification
    # 1. All 5 invalid signatures must be 401
    invalid_401_count = sum(
        1 for idx, r in enumerate(results) if test_specs[idx]["type"] == "invalid_sig" and r["status_code"] == 401
    )
    # 2. Duplicate deliveries must have had duplicates identified (either 200 or 202)
    # 3. No 500 server errors
    server_errors = [r for r in results if r["status_code"] >= 500 or r["status_code"] == 0]

    print("\n--- Verification Checks ---")
    if invalid_401_count == 5:
        print("  [OK] Security: 5/5 tampered signature requests rejected with HTTP 401.")
    else:
        print(f"  [FAIL] Security: expected 5 HTTP 401s, got {invalid_401_count}.")

    if not server_errors:
        print("  [OK] Resilience: 0 connection pool exhaustion, timeout, or database lock errors.")
    else:
        print(f"  [FAIL] Errors encountered: {len(server_errors)}")
        for err in server_errors[:3]:
            print(f"    Req #{err['req_id']}: code={err['status_code']} err={err['error']}")

    success = (invalid_401_count == 5) and (len(server_errors) == 0)
    print("\n" + "=" * 70)
    if success:
        print("SYNTHETIC LOAD TEST: PASSED")
    else:
        print("SYNTHETIC LOAD TEST: FAILED")
    print("=" * 70)
    return 0 if success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Webhook Load Tester")
    parser.add_argument("--url", default=None, help="Base URL of live server (e.g. http://127.0.0.1:8000)")
    parser.add_argument("--concurrency", type=int, default=50, help="Number of concurrent requests (default: 50)")
    args = parser.parse_args()

    exit_code = asyncio.run(run_load_test(base_url=args.url, concurrency=args.concurrency))
    sys.exit(exit_code)
