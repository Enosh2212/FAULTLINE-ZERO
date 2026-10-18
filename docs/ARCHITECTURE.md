# System Architecture & Information Flow

```mermaid
flowchart TD
    subgraph UI ["High-Density Dashboard (Vanilla JS)"]
        CB["Command Bar (1366x768 Viewport)"]
        SM["Execution State Machine"]
        EG["DAG Evidence Subgraph"]
        PC["Dual Revision Proof Card"]
    end

    subgraph INGEST ["Git & AST Ingestion Engine"]
        GIT["Local Git Demo Repo"]
        AST["Python AST Symbol Extractor"]
    end

    subgraph GRAPH ["FalkorDB Knowledge Graph"]
        CHG["Change Nodes"]
        SYM["Symbol Nodes"]
        SVC["Service Nodes"]
        INV["Business Invariants"]
        TC["Known Test Cases"]
        SCN["Discovered Scenarios"]
        MEM["Investigation Memory"]
    end

    subgraph ORCH ["Investigation Orchestrator"]
        AGENT["Tool Investigator Agent"]
        LLM["Groq openai/gpt-oss-120b (CompatibleModel)"]
        SYNTH["ScenarioSpec Synthesizer"]
    end

    subgraph EXEC ["Execution & Assertion Engine"]
        RUN["Isolated Revision Runner (Subprocess)"]
        BASE["Baseline Blob Evaluation"]
        CAND["Candidate Blob Evaluation"]
        ORACLE["Independent Business Invariant Oracles"]
    end

    CB -->|POST /git/investigations| AGENT
    AGENT <-->|Tool Calling / Backoff| LLM
    AGENT -->|Inspect Revisions| INGEST
    INGEST -->|Index AST Symbols| GRAPH
    AGENT -->|Multi-Hop Traversal| GRAPH
    GRAPH -->|Uncovered Invariants| SYNTH
    SYNTH -->|Schema-Validated Spec| RUN
    AGENT -->|Execute Authorized Tests| RUN
    RUN --> BASE
    RUN --> CAND
    BASE & CAND --> ORACLE
    ORACLE -->|Empirical Delta (Pass vs Fail)| AGENT
    AGENT -->|Persist Audit Record| MEM
    AGENT -->|Investigation Report| PC
    GRAPH -->|Evidence Subgraph| EG
```

## Core Architectural Components

### 1. FalkorDB Connected Data Model
The knowledge graph models the complete topology of dependencies:
- `(:Change {id, commit_hash})-[:TOUCHES]->(:Symbol {id, name, path})`
- `(:Symbol)-[:PART_OF]->(:Service {id, name})`
- `(:Service)-[:CALLS*0..3]->(:Service)`
- `(:Service)-[:ENFORCES]->(:Invariant {id, description, rule})`
- `(:TestCase {id, target})-[:VALIDATES]->(:Invariant)`
- `(:ScenarioSpec {id, target_invariant})-[:TARGETS]->(:Invariant)`

### 2. Graph-Guided Counterexample Synthesis (`scenario_spec.py`)
To discover regressions outside the hardcoded test suite, the agent relies on `UNCOVERED_CYPHER`:
```cypher
MATCH (c:Change {id: $change_id})-[:TOUCHES]->(s:Symbol)-[:PART_OF]->(svc:Service)
MATCH (svc)-[:ENFORCES]->(inv:Invariant)
WHERE NOT (:TestCase)-[:VALIDATES]->(inv)
RETURN inv.id AS invariant_id, inv.description AS description, svc.id AS service_id
```
When an uncovered invariant is detected:
1. The agent synthesizes an allowlisted `ScenarioSpec` specifying:
   - `target_invariant`: e.g. `INV-REFUND-01`
   - `initial_state`: e.g. `{"order_id": 100, "balance": 100.0}`
   - `ordered_actions`: `[create_order, capture_payment, process_refund, process_refund (duplicate)]`
   - `expected_properties`: `{"balance": 90.0, "refund_count": 1}`
2. The `ScenarioInterpreter` executes this specification against both baseline and candidate revisions in isolated child processes.

### 3. Dual-Revision Subprocess Runner (`revision_runner.py`)
- Independent Python interpreter subprocesses run against isolated Git revision blobs.
- Baseline must return outcome `pass` (verifying test validity and invariant correctness).
- Candidate returning `fail` proves a true regression.
- Both returning `pass` proves invariant preservation (clean control).
- Missing test coverage or missing path returns `inconclusive`.

### 4. Resilient Model Tool-Calling (`tool_agent.py`)
- Configured with `openai/gpt-oss-120b` via Groq.
- Automatically handles HTTP 429 rate limits using exponential backoff reading the `retry-after` header.
- Enforces strict iteration and token budgets.
- Persists exact execution mode (`MODEL-DRIVEN INVESTIGATION`, `DETERMINISTIC FALLBACK`, `PROVIDER UNAVAILABLE`).
