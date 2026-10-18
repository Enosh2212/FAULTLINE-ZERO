# FAULTLINE ZERO — GitHub App Architecture & CI/CD Integration

## Overview
FAULTLINE ZERO is engineered to function natively as a **GitHub App**, acting as an automated, intelligent pre-merge gate. When pull requests are created or updated, FAULTLINE ZERO intercepts webhook events, executes graph-guided differential analysis, and reports results directly inside GitHub Checks and PR discussion comments.

---

## 1. Webhook Lifecycle & Ingestion

```
[ Developer Pushes Branch ] ──> [ Pull Request Opened/Synchronized ]
                                                 │
                                                 ▼ (HTTPS Webhook)
                                [ FAULTLINE ZERO Ingestion Endpoint ]
                                                 │
                                                 ├── 1. Validate HMAC SHA256 Signature
                                                 ├── 2. Extract Base SHA & Head SHA
                                                 ├── 3. Create Pending GitHub Check Run
                                                 ▼
                                [ Background Worker: ToolInvestigator ]
                                                 │
                                                 ├── Git Diff & AST Extraction
                                                 ├── FalkorDB Multi-Hop Cypher Traversal
                                                 ├── Counterexample Discovery & Synthesis
                                                 ├── Dual Baseline vs Candidate Execution
                                                 ▼
                                [ Update GitHub Check Run & Comment ]
                                                 │
                                                 ├── Success (Clean Gate): Checks Green
                                                 └── Failure (Regression): Checks Red + Empirical Proof
```

### Supported Webhook Events
- `pull_request.opened`
- `pull_request.synchronize`
- `pull_request.reopened`
- `check_suite.rerequested`

### Webhook Security & Signature Verification
All incoming webhooks must include the `X-Hub-Signature-256` header. The payload is verified using constant-time HMAC SHA256 comparison against `GITHUB_WEBHOOK_SECRET`:
```python
import hmac, hashlib

def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

---

## 2. GitHub Checks API & Interactive Reports

### Check Run Lifecycle
1. **Queued / In Progress**:
   - As soon as the webhook is validated, FAULTLINE ZERO creates a Check Run with status `in_progress` and title `"FAULTLINE ZERO: Tracing dependency blast radius in FalkorDB..."`.
2. **Completed**:
   - If **Regression Reproduced**:
     - Conclusion: `failure`
     - Title: `Pre-Merge Regression Empirically Reproduced`
     - Summary: Plain-English explanation of the broken invariant, affected services, and observed baseline vs. candidate outputs.
     - Text: Full Markdown breakdown including FalkorDB Cypher traversal path and copyable reproduction CLI command.
   - If **Clean Gate**:
     - Conclusion: `success`
     - Title: `Pre-Merge Verification Passed — No Invariant Regressions`
   - If **Inconclusive**:
     - Conclusion: `neutral`
     - Title: `Inconclusive — Untested Scope Detected`

### Pull Request Comment Template
When a regression is discovered, FAULTLINE ZERO posts a rich comment to the PR:
```markdown
### FAULTLINE ZERO // Regression Gate Alert

> **Invariant Violation Detected:** `INV-PAY-01` (Exactly one capture per payment event)  
> **Affected Service:** `S-PAYMENTS` via `handle_gateway_webhook`

#### Empirical Proof (Dual-Branch Execution)
| Revision | Status | Observed Output |
|---|---|---|
| **Baseline (`main`)** | PASSED | 1 charge record created for 2 webhook deliveries |
| **Candidate (`pr-42`)** | FAILED | 2 charge records created (Duplicate Capture) |

#### FalkorDB Provenance Path
`Commit 9a8f2 -> handle_gateway_webhook -> S-PAYMENTS -> INV-PAY-01`

#### Reproduce Locally
```bash
python -m faultline.revision_runner payment candidate TC-PAY-IDEMPOTENCY
```
```

---

## 3. GitHub Permissions & Least Privilege Scopes

To operate with minimal security exposure, the FAULTLINE ZERO GitHub App requires only:
- **Repository Metadata**: Read-only (access commit trees).
- **Pull Requests**: Read & Write (read PR diffs and post review comments).
- **Checks**: Read & Write (create and update Check Runs and annotations).
- **Contents**: Read-only (clone repository files for AST analysis).
- **Administration / Secrets / Settings**: **No access**.
