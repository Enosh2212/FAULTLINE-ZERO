# FlyMemory — Subsystem Architecture & Graph Contracts

## 1. Subsystem Architecture Overview

FlyMemory provides associative historical incident recall for **FAULTLINE ZERO**. It bridges sparse mathematical representation learning with FalkorDB graph topology, empowering the autonomous investigation agent with historical pattern recognition during pre-merge regression triage.

```
                      ┌───────────────────────────────────────────────┐
                      │              Incoming Code Change             │
                      │        (Diff, AST Mutations, Symbols)         │
                      └───────────────────────┬───────────────────────┘
                                              │
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │           Deterministic Encoder               │
                      │     src/faultline/flymemory/feature_encoder.py │
                      │        d = 128 normalized vector              │
                      └───────────────────────┬───────────────────────┘
                                              │
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │                 FlyHash LSH                   │
                      │         src/faultline/flymemory/flyhash.py    │
                      │   Sparse Projection: m = 2560 (20x expansion) │
                      │   WTA Lateral Inhibition: k = 128 (top 5%)   │
                      └───────────────────────┬───────────────────────┘
                                              │
                                              ▼
                                   Sparse Binary Hash
                                  (128 active indices)
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
         ┌─────────────────────────────┐             ┌─────────────────────────────┐
         │       FlyMemory Store       │             │     FalkorDB Graph Store    │
         │ (In-memory Index + Cache)   │             │   (:IncidentMemory nodes    │
         │ Fast binary overlap search  │             │    topology path validation)│
         └──────────────┬──────────────┘             └──────────────┬──────────────┘
                        │                                           │
                        └─────────────────────┬─────────────────────┘
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │     Memory Retriever    │
                                 │ Topological Reranking   │
                                 │     Composite Scoring   │
                                 └────────────┬────────────┘
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │    LLM Tool Agent       │
                                 │ recall_similar_incidents│
                                 └─────────────────────────┘
```

---

## 2. Component Structure

The FlyMemory codebase is structured modularly within `src/faultline/flymemory/`:

| Module | Source File | Responsibilities |
| :--- | :--- | :--- |
| **Configuration** | `config.py` | Holds `FlyMemoryConfig` dataclass: dimensions $d=128$, expansion $\gamma=20$, $m=2560$, sparsity $\rho=0.10$, winners $k=128$, similarity thresholds, graph reranking weight $\alpha=0.35$. |
| **Feature Encoder** | `feature_encoder.py` | Extracts normalized continuous feature vectors from diffs, AST changes, and touched symbols. Strictly avoids evaluation labels to eliminate data leakage. Uses SHA-256 bucket hashing for cross-platform reproducibility. |
| **FlyHash Engine** | `flyhash.py` | Implements sparse random projection $\mathbf{W} \in \{0, 1\}^{m \times d}$, Winner-Take-All lateral inhibition with deterministic tie-breaking, and vector distance metrics (Overlap, Jaccard, Hamming). Pure Python fallback included for zero-dependency execution. |
| **Memory Store** | `store.py` | Manages `IncidentMemory` models, persistence into FalkorDB, memory index querying, repository isolation, and version consistency checks. |
| **Memory Retriever** | `retriever.py` | Coordinates two-stage retrieval: Stage 1 (FlyHash candidate filtering) and Stage 2 (FalkorDB topological path grounding and reranking). Emits structured explanations and safety caveats. |
| **Benchmark Suite** | `evaluation.py` | Implements comparative IR benchmarks evaluating Recall@K, MRR, Precision, and Latency across four distinct strategies. |

---

## 3. Data Contracts & Models

### 3.1 IncidentMemory Model
Defined in `src/faultline/flymemory/store.py`:

```python
@dataclass
class IncidentMemory:
    incident_id: str               # Unique identifier (e.g. INC-PAY-001)
    repo_id: str                   # Strict repository isolation key
    change_id: str                 # Associated change identifier
    rule_id: str                   # Associated invariant rule (e.g. INV-PAY-REFUND)
    affected_components: list[str] # List of qualified module/class/function names
    test_target: str               # Target test path that reproduced the regression
    failure_signature: str         # High-level failure exception or assertion signature
    sparse_hash: list[int]         # Sorted list of exact k active Kenyon cell indices
    created_at: str                # ISO 8601 timestamp
    verified_regression: bool      # True only if confirmed by differential execution
    projection_version: str        # Fingerprint of encoder & projection configuration
    metadata: dict[str, Any]       # Context tags, churn numbers, AST metadata
```

### 3.2 Projection Versioning
To guard against stale or incompatible hashes when configuration parameters are updated, every stored hash records a `projection_version`:
$$\text{version} = \text{MD5}(d \parallel m \parallel \rho \parallel k \parallel \text{seed})[:8]$$
Any memory with an incompatible projection version is automatically ignored during associative search until re-indexed.

---

## 4. FalkorDB Graph Schema Extensions

FlyMemory extends FAULTLINE ZERO's native FalkorDB knowledge graph with the `:IncidentMemory` label and three explicit relationship edges:

```
  (:Repository) ──[:RECORDS_MEMORY]──> (:IncidentMemory)
                                              │
                                              ├──[:AFFECTS]──> (:Component / :Function)
                                              │
                                              └──[:VIOLATES]─> (:BusinessInvariant)
```

### Node Schema: `:IncidentMemory`
- `id`: String (Primary key, e.g., `"INC-PAY-001"`)
- `repo_id`: String (Repository ID)
- `change_id`: String (Associated change ID)
- `rule_id`: String (Violated invariant)
- `failure_signature`: String (Assertion or exception type)
- `test_target`: String (Reproduction test path)
- `verified_regression`: Boolean (Ground truth flag)
- `sparse_hash`: String (JSON-encoded list of $k$ active indices)
- `projection_version`: String (Configuration version)
- `created_at`: String (Timestamp)

### Cypher Ingestion Query
```cypher
MERGE (m:IncidentMemory {id: $incident_id})
SET m.repo_id = $repo_id,
    m.change_id = $change_id,
    m.rule_id = $rule_id,
    m.failure_signature = $failure_signature,
    m.test_target = $test_target,
    m.verified_regression = $verified_regression,
    m.sparse_hash = $sparse_hash,
    m.projection_version = $projection_version,
    m.created_at = $created_at
WITH m
MATCH (r:Repository {id: $repo_id})
MERGE (r)-[:RECORDS_MEMORY]->(m)
WITH m
UNWIND $affected_components AS comp_name
MATCH (c {name: comp_name})
MERGE (m)-[:AFFECTS]->(c)
```

---

## 5. Agent Tool Integration: `recall_similar_incidents`

FlyMemory is exposed directly to the autonomous investigation agent as a typed tool in `src/faultline/tool_agent.py`:

```json
{
  "name": "recall_similar_incidents",
  "description": "Recall historically verified software regression incidents similar to the current code change using fruit-fly-inspired sparse hashing and FalkorDB graph topology.",
  "parameters": {
    "type": "object",
    "properties": {
      "change_id": {
        "type": "string",
        "description": "Identifier of the code change under investigation."
      },
      "max_results": {
        "type": "integer",
        "description": "Maximum number of similar incidents to return (default: 3)."
      }
    },
    "required": ["change_id"]
  }
}
```

### Tool Response Format
The tool returns structured metadata including:
- **Similarity Score**: FlyHash overlap similarity ($0.0 \dots 1.0$).
- **Graph Alignment Score**: FalkorDB path connectivity score.
- **Composite Confidence**: Reranked score combining associative and topological evidence.
- **Historical Target Test**: The test that proved the historical bug.
- **Historical Invariant**: The business rule that was violated.
- **Investigation Advice**: Actionable recommendation for current differential execution.
- **Safety Caveat**: Plain-English banner stating that similarity is a hypothesis, not proof.

---

## 6. Security Boundaries & Isolation

1. **Strict Repository Isolation**: Memory queries are strictly scoped to the active `repo_id`. Memories from one repository cannot leak into or influence investigations in another.
2. **Verified-Only Memory Recording**: Only investigations that conclude with a differential execution reproduction (`REPRODUCED`) are automatically written to persistent incident memory. Inconclusive or failed runs are discarded to prevent polluting the index with noise.
3. **No Credential Exposure**: Feature vectors encode only structural AST semantics and token hashes; no API keys, environment strings, or credentials can be recovered from the projection.
4. **Deterministic Reproducibility**: Given the same seed ($42$), the random projection matrix is identical across reboots, environments, and container builds.
