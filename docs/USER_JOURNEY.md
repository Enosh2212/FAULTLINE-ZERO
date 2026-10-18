# FAULTLINE ZERO — User Journey & Experience Flows

This document details the user journey across the three core experiences:
1. **Experience A: Public Discovery (Landing Page)**
2. **Experience B: Platform Operations (Dashboard Overview)**
3. **Experience C: Investigation & Proof (Workspace)**

---

## 1. Experience A: Public Discovery (Landing Page)

### 1.1 Goal
Educate engineers and engineering leaders within 15 seconds:
1. What FAULTLINE ZERO does.
2. Why green CI tests do not guarantee absence of critical bugs.
3. Why FalkorDB graph intelligence is the secret weapon.
4. How to try the live agent with zero friction.

### 1.2 Step-by-Step Flow
1. **Hero Entry**:
   - The user arrives at `http://localhost:8000/`.
   - The user immediately sees the bold statement:
     > **"Your tests passed. Your code can still break."**
   - On the right, an interactive 3D spatial network canvas displays interconnected services (`S-GATEWAY`, `S-PAYMENTS`, `S-ORDERS`, `S-INVENTORY`, `S-REFUNDS`).
   - A pulsing commit wave travels through the graph, and an uncovered invariant `INV-PAY-01` flashes with a coral badge: `BREAK DETECTED`.
2. **Problem Breakdown (The Regression Blind Spot)**:
   - Three problem cards illustrate why tests fail to catch complex regressions:
     - *Incomplete Invariant Coverage*: Test suites only test what humans write; service boundaries harbor unasserted rules.
     - *Silent Semantic Drift*: Passing unit tests with broken state transitions.
     - *Concurrency & Idempotency Leaks*: Webhook retries and race conditions that pass single-threaded test suites.
3. **The 4-Stage Engine**:
   - Interactive breakdown showing:
     - Stage 1: Git Diff & AST Extraction
     - Stage 2: FalkorDB Multi-Hop Dependency Traversal
     - Stage 3: Dynamic Counterexample Synthesis
     - Stage 4: Dual Empirical Differential Execution
4. **FalkorDB Architecture Showcase**:
   - Live Cypher query demonstration explaining why graph queries (sub-millisecond traversals) outperform relational or vector approaches for code dependencies.
5. **Interactive Evidence Deck**:
   - Tabs allow the user to preview pre-computed empirical proofs:
     - `Payment`: Webhook retry duplicate capture.
     - `Inventory`: Missing lock oversell under concurrent reservations.
     - `Refunds`: Holdout dynamic counterexample synthesized for missing idempotency key.
6. **Conversion CTA**:
   - Clicking **"Explore Live Agent"** or **"Launch Agent >"** in the floating header instantly opens the Investigation Workspace (`#investigation`).

---

## 2. Experience B: Platform Operations (Dashboard Overview)

### 2.1 Goal
Provide engineering leads with macro-level visibility into repository health, active services, invariant coverage, and live FalkorDB/Groq health.

### 2.2 Views & Tabs
- **Platform Overview (`#overview`)**:
  - Top Metrics: Connected Services (6), Tracked Invariants (18), Discovered Regressions (4), FalkorDB Graph Nodes (969+).
  - Infrastructure Health: FalkorDB connection status (In-Memory Port 6379), Groq API latency & model status (`llama-3.3-70b-versatile` / `gpt-oss-120b`).
  - Active Protected Repositories: Status of synthetic commerce repository and Git branch tracking.
- **Topology Browser (`#topology`)**:
  - Full-system graph exploration across all services and dependencies.
- **Audit Memory (`#history` / `#memory`)**:
  - Chronological table of past investigations, timestamps, execution modes (Model vs Deterministic), tool step counts, and final verdicts.
  - Search filter to instantly locate specific commits or invariant tags.
- **Diagnostics (`#settings`)**:
  - Connectivity probes for FalkorDB, Groq API, and execution sandbox.

---

## 3. Experience C: Investigation & Proof (Workspace)

### 3.1 Goal
Deliver a transparent, interactive investigation console where developers can run an investigation, watch the agent reason in real time, inspect the FalkorDB dependency graph, and copy exact CLI reproduction commands.

### 3.2 Step-by-Step Flow
1. **Persistent Command Bar**:
   - Fixed above the workspace (guaranteed visible on 1366×768 screens without scrolling).
   - Select Target Repository: `Synthetic Commerce (Local Git Tree)`.
   - Select Git Change Under Test:
     - `Payment · Webhook retry duplicate capture regression`
     - `Inventory · Missing lock oversell regression`
     - `Control · Clean PR without regression`
     - `Uncovered · Change with missing invariant coverage`
     - `Refund · Holdout dynamic counterexample discovery`
   - Select Execution Strategy: `Auto · Model when configured` or `Deterministic Fallback`.
   - Click **`RUN INVESTIGATION`**.
2. **Real-Time Agent Progression**:
   - The timeline stepper moves synchronously:
     `READY → DIFF → GRAPH → SYNTHESIS → COMPARE → VERDICT`.
   - The tool operations feed records each agent action in plain English:
     - *1. Inspected Git Diff & Symbol Boundaries*
     - *2. Traced Multi-Hop Dependencies in FalkorDB*
     - *3. Recalled Historical Investigation Memory*
     - *4. Synthesized Executable Counterexample Scenario*
     - *5. Executed Dual-Branch Differential Test*
   - Each entry contains an expandable "Inspect Technical Parameters" drawer showing exact tool arguments and outputs.
3. **Interactive Cytoscape.js Graph**:
   - The graph automatically lays out the investigated symbols and invariant paths.
   - Nodes are visually differentiated:
     - Cyan rectangle: Modified Code Symbol
     - Emerald circle: Service
     - Mint diamond: Protected Business Invariant
     - Coral diamond: Broken Business Invariant
   - Clicking any node opens a property drawer detailing its ID, type, documentation, and inbound/outbound relationships.
   - User can switch between *Evidence Subgraph* (focused on the break) and *Full Topology*.
4. **Empirical Gate Verdict & Copyable Reproduction**:
   - Verdict banner updates:
     - `REGRESSION EMPIRICALLY REPRODUCED` (Coral alert)
     - `NO REGRESSION DETECTED — GATE CLEARED` (Emerald badge)
     - `INCONCLUSIVE — MANUAL REVIEW RECOMMENDED` (Muted violet badge)
   - Dual comparison cards display:
     - **Baseline Revision**: Expected result, observed output, invariant status (Passed).
     - **Candidate Revision**: Regressed output, error trace, invariant status (Failed).
   - A single-click copy button provides the standalone CLI command to reproduce the failure locally:
     `python -m faultline.revision_runner payment candidate TC-PAY-IDEMPOTENCY`
