# Architectural Decision Records (ADRs)

## ADR-001: Graph is the Source of Truth for Test Selection
- **Decision:** The agent requires a successful FalkorDB traversal (`PLAN_CYPHER` or `UNCOVERED_CYPHER`). No implicit local fallback.
- **Reason:** For Track 01 ("Agents That Act on Connected Data"), the graph must perform real dependency resolution, not serve as cosmetic metadata.
- **Trade-off:** A graph outage halts investigation with HTTP 503 rather than running uninformed tests.

## ADR-002: Deterministic Findings over LLM Speculation
- **Decision:** A reproduced regression requires an empirical differential: `baseline.outcome == "pass"` and `candidate.outcome == "fail"`.
- **Reason:** Model claims without isolated execution proof cannot be trusted for deployment gating.
- **Trade-off:** Verifiable regressions must be backed by executable assertion code.

## ADR-003: Explicit Independent Invariants
- **Decision:** Business rules and invariants are defined independently of the candidate code implementation.
- **Reason:** Generating tests purely by reading candidate code risks hallucinating or cementing new bugs as intended behaviour.
- **Trade-off:** Invariants must be formally registered in the knowledge graph.

## ADR-004: Curated Python Fixtures and Real Git Commits
- **Decision:** Execute verified Git tree blobs in child subprocesses rather than pulling arbitrary remote repos.
- **Reason:** Security in containerized environments requires preventing untrusted arbitrary execution.
- **Trade-off:** Ingestion is bounded to allowlisted commerce demo components.

## ADR-005: One Service with Explicit Layers
- **Decision:** FastAPI serves the API and static zero-build browser client directly.
- **Reason:** Minimizes build toolchain overhead, eliminates npm supply-chain dependencies, and ensures high hackathon evaluation reliability.
- **Trade-off:** Single deployable container instead of microservices.

## ADR-006: Bounded AI with Honest Labeling
- **Decision:** Persist and display the exact execution mode (`MODEL-DRIVEN INVESTIGATION`, `DETERMINISTIC FALLBACK`, `PROVIDER UNAVAILABLE`).
- **Reason:** Never mislead users by calling deterministic code an autonomous LLM.
- **Trade-off:** Requires robust error detection and backoff in model client adapters.

## ADR-007: Inconclusive is a Valid First-Class Result
- **Decision:** Incomplete paths, missing tests, or unverified changes report `INCONCLUSIVE` rather than guessing `PASS` or `FAIL`.
- **Reason:** Prevents false sense of security in continuous delivery gates.

## ADR-008: Safe Constrained Test Generation (`ScenarioSpec`)
- **Decision:** Restrict dynamic counterexample generation to a schema-validated specification executed by a deterministic interpreter (`scenario_spec.py`).
- **Reason:** Generating and executing arbitrary raw Python code from an LLM is a major remote code execution (RCE) security vulnerability.
- **Trade-off:** Generative actions must be defined within the allowed action vocabulary.

## ADR-009: Graph-Guided Counterexample Discovery for Uncovered Invariants
- **Decision:** When FalkorDB traversal finds that an affected business invariant has no known test case (`UNCOVERED_CYPHER`), dynamically hypothesize a failure sequence and synthesize a `ScenarioSpec`.
- **Reason:** Signature capability for finding regressions that no human engineer has written a test case for.
- **Trade-off:** Requires validating invariant state before and after subprocess execution.

## ADR-010: High-Density Developer Information Architecture
- **Decision:** Replaced the marketing hero section and oversized metrics cards with a compact Command Bar (visible without scrolling on 1366×768) and a two-column workspace (Evidence Subgraph on left, Execution Stepper & Proof on right).
- **Reason:** Developer tooling must maximize information density and prioritize immediate action execution over promotional text.
