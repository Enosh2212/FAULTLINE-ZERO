# FAULTLINE ZERO — Product Vision & Strategy

## Positioning
**Autonomous Pre-Merge Regression Intelligence Agent**

> **"Your tests passed. Your code can still break."**  
> *Find the break. Prove the cause.*

---

## 1. Executive Summary

Modern software development relies heavily on automated test suites. When pull requests are created, CI pipelines run unit and integration tests; when they turn green, teams assume the code is safe to merge.

However, in distributed microservices and interconnected domain models, regressions frequently emerge in the blind spots:
- Untested business invariants across service boundaries
- Silent semantic drifts in state transitions
- Concurrency races and idempotency violations
- Cross-module side effects that existing test fixtures never anticipated

**FAULTLINE ZERO** introduces graph-native pre-merge intelligence. Instead of executing blind static tests or relying on hallucinated LLM code analysis, FAULTLINE ZERO combines:
1. **FalkorDB Knowledge Graph**: Persistent mapping of code symbols, services, state transitions, business rules, and historical failure memories.
2. **Autonomous Tool-Calling Agent**: Powered by high-speed inference (Groq GPT-OSS 120B) or deterministic graph traversal, the agent inspects unified Git diffs, navigates multi-hop dependency paths, and detects uncovered business invariants.
3. **Graph-Guided Counterexample Discovery**: The agent constructs valid, constrained executable test scenarios (`ScenarioSpec`) targeting the exact blind spot.
4. **Dual Baseline-vs-Candidate Empirical Execution**: The synthesized scenario is executed against both the trusted baseline revision and the candidate branch.
5. **Empirical Proof Engine**: If the baseline passes and candidate fails, a regression is empirically proven with exact execution traces, copyable reproduction commands, and FalkorDB graph provenance.

---

## 2. Target Persona & Use Cases

### Primary Personas
- **Staff Software Engineers / Architects**: Require deep visibility into cross-service blast radiuses before PRs merge into trunk.
- **Platform & Release Engineers**: Want to prevent flaky or incomplete test suites from releasing silent bugs into production.
- **Security & Reliability Teams**: Need continuous verification of critical invariants (e.g., duplicate charges, ledger consistency, zero negative inventory).

### Core Use Cases
1. **GitHub Pull Request Gate**: As a GitHub App, FAULTLINE ZERO triggers on PR webhooks, analyzes the git diff, queries FalkorDB, and posts an interactive Check Run status with empirical proof.
2. **Pre-Commit / Pre-Push Local CLI**: Developers can run `faultline` locally to verify changes before opening PRs.
3. **Architectural Dependency Auditing**: Visual exploration of service topologies, business rules, and blast radiuses in the FalkorDB graph.
4. **Historical Regression Memory**: Cross-investigation memory recall ensures the agent avoids redundant paths and prioritizes previously fragile invariants.

---

## 3. Product Differentiation

| Capability | Traditional CI (Jest/Pytest) | LLM Code Reviewers (Copilot PR / Codium) | FAULTLINE ZERO |
|---|---|---|---|
| **Coverage Scope** | Only tests written by humans | Guesses bugs by reading text | Traverses connected dependency graph in FalkorDB |
| **Verification Method** | Passes if pre-existing tests pass | Generates textual comments (high hallucination rate) | **Empirically executes** baseline vs. candidate branches |
| **New Test Discovery** | None (static test suite) | Proposes markdown mock snippets | Synthesizes schema-validated, executable `ScenarioSpec` |
| **Ground Truth** | Test suite assertions | None (probabilistic text) | **Differential empirical oracle** (Dual execution comparison) |
| **Architecture Context** | Isolated repository code | Context window limited | Graph database (FalkorDB) persistent topology |

---

## 4. Why FalkorDB is Critical

Relational databases or vector databases cannot efficiently navigate the recursive, multi-hop relationship chains typical of real-world software:
`Git Diff → Modified Symbol → Caller Function → Service Boundary → Business Invariant → Test Coverage → Failure Memory`

FalkorDB enables sub-millisecond Cypher traversals across thousands of connected symbols, allowing the autonomous agent to query:
- Direct and indirect call graphs (`CALLS*1..3`)
- Uncovered invariant detection (`MATCH (b:BusinessInvariant) WHERE NOT (b)-[:COVERED_BY]->(:KnownTest)`)
- Cross-service impact analysis (`DEPENDS_ON`, `EXPOSES`)
- Investigation memory recall (`INVESTIGATED`, `REPRODUCED`)

Without FalkorDB, calculating these dependency graphs in real-time within an agent reasoning loop would cause latency spikes and memory overhead that make pre-merge checks impractical.

## Automatic project understanding — current capability

FAULTLINE complements CI and human review by connecting code changes to source-backed context and validated business rules. Its current web demo remains a trusted local commerce repository, not arbitrary GitHub onboarding. Repository AST extraction, cited documentation/test analysis, a scoped invariant registry, persistent FalkorDB context, and bounded agent retrieval are implemented. Business intent is not claimed to be fully recoverable from syntax or tests: declared rules are explicit operator policy; inferred and test-backed candidates require review.

Project Understanding shows real indexing counts, why a rule was listed, missing context, and an optional dependency explorer. See PROJECT_CONTEXT_ARCHITECTURE.md for the implemented pipeline and future GitHub App/security boundaries.
