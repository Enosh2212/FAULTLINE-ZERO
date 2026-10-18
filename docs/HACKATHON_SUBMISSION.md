# FAULTLINE ZERO — Hackathon Submission Details

## Hackathon Overview
- **Hackathon**: WeMakeDevs × FalkorDB Graph Hacks 2026  
- **Official URL**: https://www.wemakedevs.org/hackathons/falkordb  
- **Primary Track**: **Track 1 — Agents That Act on Connected Data**  
- **Submission Deadline**: 18 October 2026, 11:59 PM IST  

---

## 1. Project Metadata
- **Project Name**: FAULTLINE ZERO
- **Category**: Developer Tools / AI Software Engineering / Knowledge Graphs
- **Primary Tagline**: *"Your tests passed. Your code can still break."*
- **Supporting Tagline**: *"Find the break. Prove the cause."*

---

## 2. Track 1 Alignment: Agents That Act on Connected Data

### Why FAULTLINE ZERO is the quintessential "Agent That Acts on Connected Data":
1. **Connected Data Foundation (FalkorDB)**:
   - Stores 969+ nodes and 1,392+ relationships representing Git commits, AST symbols, microservices, business invariants, and historical investigation memories.
   - Without FalkorDB's multi-hop Cypher queries (`CALLS*1..3`, `ENFORCES`, `COVERED_BY`), navigating recursive code dependencies in real-time is computationally intractable.
2. **Autonomous Graph Action**:
   - The AI agent (`ToolInvestigator`) does not simply "read" graph data to output text; it **acts** on graph relationships:
     - Detects uncovered invariants where test coverage is incomplete.
     - Synthesizes dynamic, executable `ScenarioSpec` counterexamples.
     - Dispatches differential execution against both baseline and candidate Git worktrees.
     - Checkpoints empirical evidence and tool steps back into FalkorDB.
3. **Graph-Guided Counterexample Discovery**:
   - In the benchmark holdout scenario (`refund`), where no test fixture existed in the repository, the agent used FalkorDB to discover the untested invariant (`INV-REFUND-01`) and generated a schema-validated test scenario that empirically caught the regression. Standard test suites failed with a false-positive pass.

---

## 3. Technology Stack

- **Knowledge Graph**: FalkorDB (In-Memory Graph Database with Redis Protocol)
- **AI Agent & LLM**: Groq GPT-OSS 120B (`llama-3.3-70b-versatile` / `gpt-oss-120b`) with JSON Schema Tool Calling
- **Backend**: Python 3.12 / 3.14, FastAPI, Pydantic v2, Uvicorn
- **AST & Git Analysis**: Python `ast`, Git diff parsers
- **Frontend**: Vanilla ES6+, Cytoscape.js interactive graph, HTML5 Canvas 3D spatial network, Synthora × Apple Liquid Glass CSS design system
- **Deployment & Sandbox**: Docker Compose, Read-only Linux rootfs, unprivileged user execution

---

## 4. Key Deliverables & Documentation

- [README.md](../README.md): Quick start, project overview, and architecture guide.
- [docs/PRODUCT_VISION.md](PRODUCT_VISION.md): Strategic market positioning and differentiation.
- [docs/PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md): System design, data flow, and subsystem contracts.
- [docs/USER_JOURNEY.md](USER_JOURNEY.md): Walkthrough of Landing, Overview, and Investigation experiences.
- [docs/DESIGN_SYSTEM.md](DESIGN_SYSTEM.md): Synthora × Apple Liquid Glass color tokens and typography.
- [docs/MOTION_SYSTEM.md](MOTION_SYSTEM.md): 3D Canvas spatial network and Cytoscape physics layout.
- [docs/AGENT_DESIGN.md](AGENT_DESIGN.md): Tool definitions, schemas, execution budgets, and recovery.
- [docs/GRAPH_SCHEMA.md](GRAPH_SCHEMA.md): Complete FalkorDB ontology and production Cypher queries.
- [docs/GITHUB_APP_ARCHITECTURE.md](GITHUB_APP_ARCHITECTURE.md): Webhook ingestion and GitHub Checks API integration.
- [docs/AUTHENTICATION.md](AUTHENTICATION.md): OAuth 2.0 architecture and repository permissions.
- [docs/SECURITY.md](SECURITY.md): Defense-in-depth execution boundaries and secret management.
- [docs/DEMO_SCRIPT.md](DEMO_SCRIPT.md): 5-minute hackathon judge demonstration walkthrough.
- [docs/EVALUATION.md](EVALUATION.md): Empirical benchmark matrix across all 5 test scenarios.
- [docs/BUILD_STATUS.md](BUILD_STATUS.md): 35/35 passing unit tests and Docker smoke test results.
