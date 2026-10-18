# FAULTLINE ZERO — STRIDE Threat Model & Security Posture

## Overview
This document evaluates the FAULTLINE ZERO SaaS platform using the Microsoft STRIDE threat modeling methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) along with defenses against autonomous LLM prompt injection.

---

## 1. STRIDE Analysis

| Threat Category | Potential Attack Vector | Mitigation in FAULTLINE ZERO |
|---|---|---|
| **Spoofing (Identity)** | Attacker submits fake GitHub webhook deliveries pretending to be GitHub | Mandatory `X-Hub-Signature-256` HMAC-SHA256 verification using secret known only to GitHub and the FAULTLINE server. |
| | Attacker impersonates another user or organization | Cryptographically signed Firebase session cookies with HMAC-SHA256 signature and tamper-proof user ID payload. |
| **Tampering (Data)** | Attacker modifies session cookie payload in transit | Base64 URL signature validation terminates corrupted or modified tokens with immediate 401 Unauthorized. |
| | Attacker tampers with GitHub App installation callback | Signed OAuth `state` parameter containing organization ID, user ID, expiration timestamp, and HMAC signature. |
| | Cross-Site Request Forgery (CSRF) on mutating endpoints | Mandatory `X-CSRF-Token` header validated against HMAC session token on all mutating HTTP requests. |
| **Repudiation** | User denies modifying repository sync settings or triggering jobs | Immutable `audit_events` table logs user ID, organization ID, action, resource, timestamp, and IP address. |
| **Information Disclosure** | Cross-tenant data leak (Org A reads Org B repositories) | Strict relational queries filtered by `organization_id`; FalkorDB queries scoped by `repo_id`. |
| | Subprocess leaks server API keys (`GROQ_API_KEY`, etc.) | Differential test runners receive explicitly sanitized environments stripped of all host secrets and environment variables. |
| **Denial of Service** | Replay of previous webhook payloads to exhaust worker queue | Webhook deduplication outbox checks `X-GitHub-Delivery` and ignores duplicates with HTTP 200. |
| | Infinite loop in candidate code during diff verification | Hard 8-second subprocess timeout with `SIGKILL` dispatch; external PRs undergo read-only static analysis without execution. |
| **Elevation of Privilege** | Untrusted external code escapes sandbox to gain root access | External GitHub PRs undergo **STRICTLY READ-ONLY static AST & graph analysis** with zero host code execution in Phase 1. |

---

## 2. Autonomous Agent & Prompt Injection Defense

Tool-calling LLMs analyzing untrusted pull request code or commit messages are vulnerable to **indirect prompt injection** (e.g., code comments instructing the agent to ignore regressions or declare the code clean).

### Mitigations:
1. **Tool Schema Constraints**:
   - All tool arguments are validated with rigid Pydantic models with `extra="forbid"`.
   - Arbitrary shell execution or raw Cypher queries from the model are physically rejected by the schema validator.
2. **Deterministic Invariant Oracle**:
   - The LLM **never** decides the final regression verdict.
   - The verdict is computed exclusively by the Python Differential Invariant Oracle:
     $$\text{Verdict} = (\text{baseline\_status} == \text{PASS} \land \text{candidate\_status} == \text{FAIL}) \implies \text{REPRODUCED}$$
   - Even if an attacker injects text claiming "This change is safe", the automated oracle overrides model text with observed empirical truth.
3. **Observation-Only Diff Ingestion**:
   - Diffs, commit messages, and AST symbol signatures are passed strictly as JSON tool observations, never as system behavioral instructions.
