# FAULTLINE ZERO — Multi-Tenant Isolation & Scoping Architecture

## Overview
In a multi-tenant developer platform, preventing cross-tenant data leaks and unauthorized state modification is critical. This document details how FAULTLINE ZERO enforces multi-tenant boundaries across relational storage, knowledge graphs, and execution engines.

---

## 1. Relational Database Isolation (PostgreSQL / SQLite)

Every query executed against tenant-owned resources strictly enforces tenancy filters at the database engine level.

### 1.1 Foreign Key Cascade Hierarchies
```
Organization
├── Membership (user_id, organization_id)
├── GitHubInstallation (organization_id)
├── Repository (organization_id)
│   ├── PullRequest (repository_id)
│   └── Investigation (repository_id, pull_request_id)
├── BackgroundJob (organization_id)
└── AuditEvent (organization_id)
```

### 1.2 Declarative FastAPI Scoping Dependencies
Tenant authorization is enforced declaratively using FastAPI dependencies:
- `get_authorized_org`: Checks that `request.user` has an active record in `memberships` for `organization_id`. Header spoofing (`X-Organization-Id`) from unauthorized users is blocked with HTTP 403.
- `get_authorized_repo`: Queries `Repository` by `id` and verifies that the repository's `organization_id` matches an organization where the authenticated user is an active member. Cross-tenant repository access attempts are rejected with HTTP 403 or 404.

---

## 2. Knowledge Graph (FalkorDB) Namespace Isolation

In FalkorDB, nodes and edges representing code structure, AST symbols, commits, and invariant relationships are partitioned by repository and commit SHA.

### 2.1 Graph Query Parameterization
All Cypher queries are strictly parameterized:
```cypher
MATCH (r:Repository {id: $repo_id})-[:CONTAINS]->(f:File)-[:DEFINES]->(fn:Function)
WHERE fn.name = $symbol_name
RETURN fn
```
Tenants cannot observe nodes outside their `repo_id` namespace. No string interpolation is ever permitted in Cypher construction.

---

## 3. FlyMemory Incident Index Scoping

Historical incident fingerprints stored in FlyMemory's fruit-fly sparse hash table are indexed per repository identifier (`repo_id`). Queries executed against FlyMemory require `repo_id` to be explicitly provided:
```python
retriever.retrieve(repo_id="org-acme/payment-service", context=context, ...)
```
Incidents from Organization A are never returned to or matched against code modifications submitted by Organization B.

---

## 4. GitHub Checks & API Isolation

GitHub App installation tokens are requested on a per-installation basis (`POST /app/installations/{installation_id}/access_tokens`).
- Tokens are scoped strictly to the repositories authorized by the organization admin during GitHub App installation.
- A tenant cannot publish Check Runs, post PR comments, or read code from any repository outside their authorized installation scope.
