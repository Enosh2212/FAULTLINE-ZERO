# FAULTLINE ZERO — Multi-Tenant SaaS Platform Architecture

## Executive Summary
FAULTLINE ZERO is an evidence-first, graph-native pre-merge regression intelligence platform. This document defines the **Phase 1 Multi-Tenant SaaS Platform Architecture**, detailing the transition from a local developer fixture to an enterprise-grade developer platform with cryptographic authentication, GitHub App onboarding, tenant data isolation, and read-only static PR blast-radius intelligence.

---

## 1. System Topology & Component Layout

```
                                      [ GitHub Ecosystem ]
                                                │
                          HTTPS Webhooks        │  OAuth 2.0 Install Flow
                      (X-Hub-Signature-256)     │  (HMAC Signed State)
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FAULTLINE ZERO SaaS Gate Platform                                                      │
│                                                                                        │
│  ┌────────────────────────┐    ┌────────────────────────┐    ┌──────────────────────┐  │
│  │ Firebase Session Auth  │    │  Webhook Ingestion &   │    │ GitHub App Manager   │  │
│  │ Cookie: HttpOnly/Lax   │    │  Deduplication Outbox  │    │ Token Exchange       │  │
│  │ CSRF: HMAC-SHA256      │    │  Event Router          │    │ Checks API Sync      │  │
│  └───────────┬────────────┘    └───────────┬────────────┘    └──────────┬───────────┘  │
│              │                             │                            │              │
│              ▼                             ▼                            ▼              │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Multi-Tenant Relational Store (PostgreSQL / SQLite via SQLAlchemy 2.0)           │  │
│  │ • users                  • organizations          • memberships                  │  │
│  │ • github_installations   • repositories           • pull_requests                │  │
│  │ • investigations         • webhook_deliveries     • background_jobs              │  │
│  │ • audit_events                                                                   │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                            │                                           │
│                                            ▼                                           │
│                      ┌───────────────────────────────────────────┐                     │
│                      │ Idempotent Background Job Queue & Worker  │                     │
│                      │ • Stale Commit Job Cancellation           │                     │
│                      │ • Per-Tenant Concurrency Throttling       │                     │
│                      └─────────────────────┬─────────────────────┘                     │
│                                            │                                           │
│                       ┌────────────────────┴───────────────────┐                       │
│                       ▼                                        ▼                       │
│       [ EXTERNAL PR INVESTIGATION ]            [ TRUSTED FIXTURE DEMO ]                │
│       • Strictly READ-ONLY static AST          • Dual-revision subprocess execution    │
│       • Cypher blast-radius path trace         • Differential Invariant Oracle         │
│       • ZERO host code execution               • Controlled synthetic sandbox          │
│                       │                                        │                       │
│                       ▼                                        ▼                       │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ FalkorDB Multi-Tenant Knowledge Graph (Scoped by repo_id and revision)           │  │
│  │ Nodes: Commit, File, Function, Service, Invariant, ScenarioSpec                  │  │
│  │ Sparse Hash: FlyMemory Bio-Inspired Associative Incident Index                   │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Tenant Relational Schema

All relational entities are strongly typed in `src/faultline/db/models.py` using SQLAlchemy 2.0.

### 2.1 Core Entities
1. **User**: Represents developer identity verified via Firebase Auth (`firebase_uid`, `email`, `display_name`, `avatar_url`, `role`).
2. **Organization**: Represents the tenant workspace (`name`, `slug`, `billing_tier`).
3. **Membership**: Join table mapping Users to Organizations with roles (`owner`, `admin`, `member`).
4. **GitHubInstallation**: Represents a GitHub App installation on an organization or user account (`id`, `account_login`, `account_type`, `permissions_json`, `is_suspended`).
5. **Repository**: Tenant-isolated code repository (`organization_id`, `installation_id`, `github_repo_id`, `full_name`, `is_private`, `default_branch`).
6. **PullRequest**: Tracked pull request on a repository (`repository_id`, `github_pr_number`, `head_sha`, `base_sha`, `title`, `author_login`, `state`).
7. **Investigation**: Record of a regression investigation for a commit (`repository_id`, `pull_request_id`, `commit_sha`, `status`, `verdict`, `confidence`, `summary`, `report_json`, `evidence_graph_json`, `check_run_id`).
8. **WebhookDelivery**: Idempotency audit log for inbound GitHub webhooks (`delivery_id`, `event_name`, `payload_hash`, `status`, `error_message`, `processed_at`).
9. **BackgroundJob**: Durable task execution queue (`organization_id`, `job_type`, `status`, `idempotency_key`, `attempts`, `payload_json`, `error_message`).
10. **AuditEvent**: Cryptographic audit log of sensitive operations (`organization_id`, `user_id`, `action`, `resource_type`, `resource_id`, `ip_address`).

---

## 3. Strict Execution Boundary (Phase 1 Security Contract)

A foundational architectural requirement of FAULTLINE ZERO is honest capability boundaries:

| Dimension | External GitHub Repositories (Phase 1) | Trusted Demo Repository (`demo-repository`) |
|---|---|---|
| **Host Code Execution** | **STRICTLY FORBIDDEN** (Zero execution) | Differential subprocess with sanitized env |
| **Analysis Method** | Read-Only Python AST + Cypher Graph Traversal | AST + Cypher + Live Baseline vs Candidate Test |
| **Blast Radius Detection** | Call-graph static reachability + Invariant matching | Static graph reachability + Dynamic counterexample |
| **Output Publishing** | GitHub Checks API + Markdown PR comments | Web dashboard UI + Saved JSON report + Graph canvas |
| **Host System Safety** | No `pip install`, no `pytest`, no subprocess | Isolated timeout-bound subprocess (`UID 1000`) |

---

## 4. Background Job Queue & Lifecycle

1. **Webhook Ingestion**:
   - `POST /api/v1/webhooks/github` receives event.
   - Validates `X-Hub-Signature-256` in constant time.
   - Rejects duplicate deliveries using `X-GitHub-Delivery`.
   - Persists `WebhookDelivery` and commits transaction.
   - Returns HTTP 202 Accepted within 15 milliseconds.
2. **Job Enqueueing**:
   - Computes deterministic `idempotency_key = f"pr:{repo.id}:{pr.id}:{head_sha}"`.
   - Inserts `BackgroundJob(status="queued")`.
   - If event is `pull_request.synchronize` (new commit pushed to existing PR), all older jobs for that PR in `queued` or `running` state are atomically updated to `status="cancelled"` (Stale Commit Cancellation).
3. **Execution & Check Update**:
   - Asynchronous worker executes `handle_investigate_pr`.
   - Performs read-only AST & graph analysis.
   - Updates GitHub Check Run to `completed` with conclusion (`success`, `failure`, `neutral`).
   - If regression discovered, posts markdown evidence comment directly to PR thread.
