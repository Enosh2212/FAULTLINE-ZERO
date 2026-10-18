# FAULTLINE ZERO — 5-Minute Hackathon Judge Demo Script

**Theme**: Agents That Act on Connected Data (WeMakeDevs × FalkorDB Graph Hacks 2026)  
**Positioning**: "Your tests passed. Your code can still break."

---

## Act 1: The Hook (0:00 - 1:00) — Public Landing Experience

1. **Open `http://localhost:8000/`** in a clean browser window.
2. **Deliver the Hook**:
   > *"Every engineering team has experienced this nightmare: CI is completely green, all automated tests pass, the PR is merged... and 20 minutes later, production breaks. Why? Because test suites only verify what humans thought to write. The real regressions happen across connected services and untested business invariants."*
3. **Showcase the 3D Hero Spatial Canvas**:
   - Point out the floating architectural topology on the right:
     `S-GATEWAY → S-PAYMENTS → S-ORDERS → S-INVENTORY → S-REFUNDS`.
   - Point to the pulsing commit wave and the detected break on `INV-PAY-01` (`BREAK DETECTED`).
4. **Highlight FalkorDB's Role**:
   - Scroll to the **"Why FalkorDB powers FAULTLINE ZERO"** section.
   - Show the live Cypher query:
     `MATCH (c:Commit)-[:MODIFIES]->(s)-[:PART_OF]->(svc)-[:ENFORCES]->(inv)`
   - Explain: *"FalkorDB gives the AI agent sub-millisecond graph traversals across thousands of connected symbols, finding invariants that no flat vector database could ever discover."*

---

## Act 2: The Investigation Experience (1:00 - 2:30) — Live Regression Proof

1. Click **`Launch Agent >`** or **`Explore Live Agent`** to transition to `#investigation`.
2. **Demonstrate Ergonomics**:
   - Point out the **Liquid Glass Command Bar**:
     - Visible on 1366×768 screens without any scrolling.
     - Target Repo: `Synthetic Commerce (Local Git Tree)`.
     - Change: Select **`Payment · Webhook retry duplicate capture regression`**.
     - Strategy: `Auto · Model when configured`.
3. Click **`RUN INVESTIGATION`**.
4. **Watch the Autonomous Reasoning Progress**:
   - The Stepper tracks progress live: `READY → DIFF → GRAPH → SYNTHESIS → COMPARE → VERDICT`.
   - Plain-English feed updates:
     - *1. Inspected Git Diff & Symbol Boundaries*
     - *2. Traced Multi-Hop Dependencies in FalkorDB*
     - *3. Recalled Historical Investigation Memory*
     - *4. Executed Dual-Branch Differential Test*
   - Expand **"Inspect Technical Parameters"** to show actual tool inputs and execution timings.
5. **Inspect the Evidence**:
   - The Cytoscape.js dependency graph highlights the causal chain connecting `handle_gateway_webhook` to `INV-PAY-01`.
   - The **Empirical Analysis** card reveals:
     - **Baseline (`main`)**: PASSED — 1 capture recorded for 2 webhook deliveries.
     - **Candidate (`pr-branch`)**: FAILED — Duplicate capture: 2 records created for 1 event!
   - Click the **`Copy`** button on the reproduction command:
     `python -m faultline.revision_runner payment candidate TC-PAY-IDEMPOTENCY`

---

## Act 3: The Signature Capability (2:30 - 4:00) — Graph-Guided Counterexample Synthesis

1. Select **`Refunds · Holdout duplicate refund race (Dynamic Counterexample)`**.
2. **Explain the Challenge to the Judges**:
   - *"In this scenario, there is NO pre-existing test suite fixture in the repository. Standard CI passes with flying colors."*
3. Click **`RUN INVESTIGATION`**.
4. **Observe the Discovery**:
   - FalkorDB detects that modified symbol `process_refund` enforces `INV-REFUND-01`, but `INV-REFUND-01` has no `COVERED_BY` edge.
   - The agent synthesizes a new executable `ScenarioSpec` targeting the unasserted invariant.
   - The scenario is validated against a rigid schema and dispatched to both baseline and candidate worktrees.
   - **Verdict**: `COUNTEREXAMPLE SYNTHESIZED — REGRESSION EMPIRICALLY REPRODUCED`.
   - Open the **`Discovered Counterexamples`** tab to view the generated operational steps.

---

## Act 4: Platform Health & Enterprise Architecture (4:00 - 5:00)

1. Click **`Platform`** in the header (`#overview`):
   - Review live metrics: 6 Connected Services, 18 Tracked Invariants, 969+ Graph Nodes in FalkorDB.
   - Show the green status dots: `FalkorDB: In-Memory Port 6379`, `Groq 120B: Ready`.
2. Click **`Audit Memory`** (`#history`):
   - Demonstrate persistent investigation memory stored in FalkorDB.
   - Show how past investigations prevent redundant work.
3. **Conclude**:
   > *"FAULTLINE ZERO doesn't guess, doesn't hallucinate, and doesn't rely on humans to write every test. By combining FalkorDB graph intelligence with dual-branch differential execution, it proves regressions before code ever hits production."*
