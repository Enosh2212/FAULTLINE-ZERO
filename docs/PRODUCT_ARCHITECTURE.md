# FAULTLINE ZERO — Product Architecture & System Design

```
+----------------------------------------------------------------------------------------------------+
|                                    FAULTLINE ZERO ARCHITECTURE                                      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Developer / GitHub PR Webhook ]                                                                |
|                 |                                                                                  |
|                 v                                                                                  |
|  +----------------------------------------------------------------------------------------------+  |
|  |                          FastAPI Application Gateway & Webhook Ingestion                    |  |
|  +----------------------------------------------------------------------------------------------+  |
|                 |                                                                                  |
|                 +-----------------------------------+                                              |
|                 |                                   |                                              |
|                 v                                   v                                              |
|  +-------------------------------+   +----------------------------------------------------------+  |
|  |   Git Diff & AST Extractor    |   |                FalkorDB Graph Engine                     |  |
|  |   - Parse unified diff        |   |   - 969+ Nodes / 1,392+ Relationships                    |  |
|  |   - Extract modified symbols  |   |   - Topology: Services, CodeSymbols, Invariants, Tests  |  |
|  |   - Identify syntactic scope  |   |   - Historical investigation memory & recurrence patterns   |  |
|  +-------------------------------+   +----------------------------------------------------------+  |
|                 |                                   |                                              |
|                 v                                   v                                              |
|  +----------------------------------------------------------------------------------------------+  |
|  |                           Autonomous Tool Investigator Loop                                  |  |
|  |   - Model-Driven: Groq GPT-OSS 120B (sub-second tool calling)                               |  |
|  |   - Deterministic Fallback: Graph-native invariant pathfinding                               |  |
|  |   - Available Tools:                                                                         |  |
|  |     * inspect_git_change(repo, change_id)                                                    |  |
|  |     * query_falkordb_graph(cypher_query)                                                     |  |
|  |     * recall_investigation_memory(symbol_id)                                                 |  |
|  |     * synthesize_counterexample(invariant_id, spec)                                          |  |
|  |     * execute_differential_test(scenario_spec)                                               |  |
|  |     * record_verdict(outcome, evidence)                                                      |  |
|  +----------------------------------------------------------------------------------------------+  |
|                 |                                                                                  |
|                 v                                                                                  |
|  +----------------------------------------------------------------------------------------------+  |
|  |                        Dual-Branch Empirical Execution Sandbox                               |  |
|  |   - Baseline Worktree Execution (Trusted Ref)  ===> Observation 1                             |  |
|  |   - Candidate Worktree Execution (PR Ref)      ===> Observation 2                             |  |
|  |   - Differential Invariant Evaluation Oracle   ===> Verdict Determination                    |  |
|  +----------------------------------------------------------------------------------------------+  |
|                 |                                                                                  |
|                 +-----------------------------------+                                              |
|                 |                                   |                                              |
|                 v                                   v                                              |
|  +-------------------------------+   +----------------------------------------------------------+  |
|  |     FalkorDB Persistence      |   |            Synthora x Liquid Glass Dashboard             |  |
|  |  - Store investigation memory  |   |  - Experience A: Cinematic 3D Spatial Canvas Landing     |  |
|  |  - Graph update with verdict   |   |  - Experience B: Executive Overview & Health Metrics     |  |
|  |  - Incremental edge scoring   |   |  - Experience C: Cytoscape Dependency Canvas & Timeline  |  |
|  +-------------------------------+   +----------------------------------------------------------+  |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 1. Core Subsystems

### 1.1 Git Diff & AST Symbol Indexer (`faultline.git_diff`)
- Ingests unified git diffs between `base_ref` and `candidate_ref`.
- Uses Python `ast` parsing to map line changes directly to function, class, and method definitions.
- Normalizes symbol identities into global URNs (e.g., `pkg.module.Class.method`).

### 1.2 FalkorDB Knowledge Topology (`faultline.graph_repository`)
- High-performance, in-memory graph storage with Redis protocol compatibility.
- Implements Cypher queries with parameterized caching.
- Maintains node types:
  - `:GitChange`: Branch and commit change tracking.
  - `:CodeSymbol`: Functions, classes, and handlers.
  - `:Service`: Architectural microservice boundaries (`S-PAYMENTS`, `S-INVENTORY`, `S-ORDERS`).
  - `:BusinessInvariant`: Formal requirements (`INV-PAY-01`, `INV-STOCK-01`, `INV-REFUND-01`).
  - `:KnownTest`: Pre-existing test suite fixtures (`TC-PAY-IDEMPOTENCY`, `TC-STOCK-CONCURRENCY`).
  - `:ScenarioSpec`: Discovered dynamic counterexamples.
- Edge types:
  - `[:MODIFIES]`, `[:CALLS]`, `[:BELONGS_TO]`, `[:ENFORCES]`, `[:COVERED_BY]`, `[:INVESTIGATED]`.

### 1.3 Autonomous Investigator Loop (`faultline.agent`)
- Bounded iterative tool loop (default max 6 iterations).
- Integrates Groq API (`llama-3.3-70b-versatile` / `gpt-oss-120b`) with native JSON Schema tool definitions.
- Automatic fallback: If the model provider is unavailable or fails schema validation, the deterministic graph pathfinder immediately takes over without interrupting execution.
- Emits real-time progress steps: `READY → DIFF → GRAPH → SYNTHESIS → COMPARE → VERDICT`.

### 1.4 Dual-Branch Differential Execution Engine (`faultline.revision_runner`)
- Executes scenarios in isolated sandboxes against:
  1. **Baseline Revision**: The clean main branch commit before the PR.
  2. **Candidate Revision**: The PR branch containing the modified symbols.
- Captures runtime state, return values, database records, and exception logs.
- Feeds observations into an independent invariant oracle that decides whether a behavioral deviation constitutes a true regression.

### 1.5 Web Client & Spatial Interface (`faultline.web`)
- Modern vanilla ES6+ architecture (no complex bundler bloat, zero runtime framework latency).
- High-performance HTML5 Canvas rendering for spatial background clustering and real-time pulse waves.
- Interactive Cytoscape.js canvas with force-directed layout, node selection, edge highlighting, and zoom/pan controls.
- Synthora × Liquid Glass design tokens with WCAG AAA contrast and reduced-motion support.
