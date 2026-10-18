# FAULTLINE ZERO — GitHub Webhook Security & Ingestion Reliability

## Overview
Webhooks represent an unauthenticated inbound ingress point from the public internet. To protect FAULTLINE ZERO infrastructure against tampering, unauthorized job injection, denial-of-service, and replay attacks, the webhook receiver incorporates multi-layered defense-in-depth controls.

---

## 1. Constant-Time HMAC-SHA256 Signature Verification

GitHub signs all webhook payloads with the shared secret configured during App registration, transmitting the hex digest in the `X-Hub-Signature-256` header.

### 1.1 Verification Algorithm
```python
import hmac, hashlib

def verify_webhook_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

### 1.2 Security Properties:
- **Raw Body Preservation**: The HMAC is computed strictly over raw body bytes (`await request.body()`) before any JSON decoding to prevent serialization discrepancies.
- **Timing Attack Defense**: Verification uses Python's standard `hmac.compare_digest` to prevent timing-based byte-by-byte forgery.
- **Immediate Rejection**: Any missing or mismatching signature terminates the HTTP request immediately with HTTP 401 Unauthorized before any database transaction is initiated.

---

## 2. Delivery Deduplication & Replay Prevention

GitHub webhooks include a unique UUID in the `X-GitHub-Delivery` header.

### 2.1 Deduplication Outbox Pattern
1. Upon signature verification, the server checks the `webhook_deliveries` table for `delivery_id = x_github_delivery`.
2. If the delivery ID is already recorded:
   - The server immediately responds with `HTTP 200 OK` and payload `{"status": "already_processed"}`.
   - No background jobs are duplicated.
3. If new, the delivery record is committed with status `received`, payload SHA-256 hash, and event timestamp before any background processing begins.

---

## 3. Rapid HTTP Acknowledgement

To prevent GitHub webhook delivery timeouts (GitHub enforces a 10-second response window):
- Webhook endpoints complete verification and deduplication in under 15ms.
- Jobs are enqueued into `background_jobs` and scheduled via FastAPI `BackgroundTasks`.
- The endpoint immediately returns `HTTP 202 Accepted` to GitHub.

---

## 4. Stale Commit Job Cancellation

When developers rapidly push multiple commits to an open PR:
- Each `pull_request.synchronize` event carries the new `head_sha`.
- The worker executes `JobQueue.cancel_pr_jobs(db, pr.id)`, immediately marking any pending or running jobs for previous commits as `cancelled`.
- This eliminates redundant CI compute cycles and guarantees that only the newest commit result is reported to GitHub Checks.
