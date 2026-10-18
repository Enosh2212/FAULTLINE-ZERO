# FAULTLINE ZERO — FalkorDB Knowledge Graph Schema & Queries

## Overview
FAULTLINE ZERO utilizes **FalkorDB** as its persistent software knowledge graph. FalkorDB models software architecture not merely as abstract lines of code, but as an interconnected ecosystem of Git commits, AST symbols, microservices, business invariants, executable test fixtures, and historical investigation memories.

Currently verified live topology: **969 nodes and 1,392 edges**.

---

## 1. Node Labels & Entity Attributes

| Node Label | Description | Primary Key / Identifier | Key Properties |
|---|---|---|---|
| `:Repository` | Monitored source code repository | `id: "repo_synthetic_commerce"` | `name`, `url`, `default_branch` |
| `:Commit` | Git commit revision | `sha: str` | `author`, `message`, `timestamp`, `ref_type` |
| `:File` | Source code file | `path: str` | `language`, `size_bytes`, `sha` |
| `:CodeSymbol` | Functions, methods, and classes parsed via AST | `id: str` (e.g. `handle_gateway_webhook`) | `name`, `kind` (`function`, `class`, `method`), `start_line`, `end_line` |
| `:Service` | Microservice boundary | `id: str` (e.g. `S-PAYMENTS`, `S-INVENTORY`) | `name`, `tier`, `owner_team` |
| `:BusinessInvariant` | Formally declared business rule | `id: str` (e.g. `INV-PAY-01`, `INV-STOCK-01`) | `name`, `description`, `severity`, `expression` |
| `:KnownTest` | Pre-existing test suite case | `id: str` (e.g. `TC-PAY-IDEMPOTENCY`) | `name`, `file_path`, `timeout_seconds` |
| `:ScenarioSpec` | Dynamically synthesized counterexample | `id: str` (e.g. `SCENARIO-REFUND-01`) | `operations`, `invariants`, `schema_version` |
| `:Investigation` | Persistent investigation audit record | `id: str` (UUID) | `timestamp`, `verdict`, `execution_mode`, `provider` |
| `:ToolExecution` | Individual tool invocation checkpoint | `id: str` | `tool_name`, `arguments`, `status`, `duration_ms` |
| `:Finding` | Empirical proof of regression | `id: str` | `baseline_obs`, `candidate_obs`, `graph_path` |

---

## 2. Relationship Taxonomy

| Relationship Type | Source Node | Target Node | Semantics |
|---|---|---|---|
| `[:CONTAINS]` | `:Repository` | `:Commit` / `:File` | Structural hierarchy |
| `[:DEFINES]` | `:File` | `:CodeSymbol` | Code declaration |
| `[:MODIFIES]` | `:Commit` | `:CodeSymbol` | AST diff modification |
| `[:PART_OF]` | `:CodeSymbol` | `:Service` | Service ownership |
| `[:CALLS]` | `:CodeSymbol` / `:Service` | `:CodeSymbol` / `:Service` | Call hierarchy / cross-service dependency |
| `[:ENFORCES]` | `:Service` | `:BusinessInvariant` | Architectural governance |
| `[:COVERED_BY]` | `:BusinessInvariant` | `:KnownTest` | Pre-existing test coverage |
| `[:VALIDATES]` | `:ScenarioSpec` | `:BusinessInvariant` | Counterexample coverage |
| `[:INVESTIGATES]` | `:Investigation` | `:Commit` | Audit scope |
| `[:FOUND]` | `:Investigation` | `:Finding` | Empirical conclusion |
| `[:EXECUTED]` | `:Investigation` | `:ToolExecution` | Step-by-step provenance |

---

## 3. High-Performance Cypher Queries

### 3.1 Trace Multi-Hop Invariant Blast Radius
Find all business invariants impacted when a set of symbols is modified in a PR:
```cypher
MATCH (c:Commit {sha: $candidate_sha})-[:MODIFIES]->(s:CodeSymbol)
MATCH path = (s)-[:PART_OF]->(svc:Service)-[:ENFORCES]->(inv:BusinessInvariant)
OPTIONAL MATCH (inv)-[:COVERED_BY]->(t:KnownTest)
RETURN s.name AS symbol, svc.name AS service, inv.id AS invariant, inv.description AS rule, collect(t.id) AS test_ids
```

### 3.2 Discover Uncovered Invariants for Counterexample Synthesis
Locate invariants affected by modified code that lack existing test coverage:
```cypher
MATCH (c:Commit {sha: $candidate_sha})-[:MODIFIES]->(s:CodeSymbol)-[:PART_OF]->(svc:Service)-[:ENFORCES]->(inv:BusinessInvariant)
WHERE NOT (inv)-[:COVERED_BY]->(:KnownTest)
RETURN inv.id AS uncovered_invariant, inv.description AS invariant_rule, svc.name AS target_service, s.name AS entry_symbol
```

### 3.3 Historical Memory Recall
Retrieve past investigation findings for a specific symbol to detect recurrence patterns:
```cypher
MATCH (s:CodeSymbol {name: $symbol_name})<-[:MODIFIES]-(c:Commit)<-[:INVESTIGATES]-(inv:Investigation)-[:FOUND]->(f:Finding)
RETURN inv.id AS investigation_id, inv.timestamp AS timestamp, inv.verdict AS verdict, f.graph_path AS prior_path
ORDER BY inv.timestamp DESC
LIMIT 5
```
