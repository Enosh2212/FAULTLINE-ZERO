> Historical v0.1 notes retained for context. For the current Git workflow and verified status, use README.md, AGENT_DESIGN.md and BUILD_STATUS.md.

# Test plan and measurable acceptance criteria

## Unit and contract tests (`pytest -q`)

1. Runner actually imports and executes baseline + candidate functions.
2. Duplicate-webhook scenario is PASS/FAIL respectively.
3. Overselling scenario is PASS/FAIL respectively.
4. Control scenario is PASS/PASS and not reported as a regression.
5. Unallowlisted scenario/version rejected.
6. Dependency path traversal honours `CALLS` edges only.
7. Agent persists a report with accurate evidence IDs.
8. Empty graph plan → 0 executed tests → INCONCLUSIVE.
9. Unknown change ID → 404.
10. API contract and validation respond correctly.

## Docker integration — must execute on teammate machine

```powershell
docker compose up --build -d
python scripts/smoke_test.py
```

The smoke script verifies graph readiness, graph topology, two reproduced regressions, an unchanged control, persisted report retrieval and removal-dependency semantics via the graph plan test (unit).

## Manual browser QA

- Main cards show actual graph counts, not fixture placeholders.
- Selecting each change shows its correct description.
- Graph click displays actual node identity; evidence paths highlight connected nodes/edges.
- Result shows correct baseline/candidate statuses and agent tool trace.
- Recent report persists after refreshing browser and restarting API container (with graph volume intact).
- Small screens (375 px) maintain readable UI with vertical layout.
- API auth modal works if `FZ_API_KEY` is set.

## Anti-decoration demonstration

- Unit: `test_no_graph_evidence_means_no_execution` confirms graph dependency.
- Live: duplicate synthetic instance of graph without `VALIDATES` edges should return zero selected tests. **Do not modify production graph without a reset plan.**

## Benchmark to collect (not claimed yet)

Measure p50/p95 FalkorDB plan query latency, two-revision runner wall-clock time, graph size (nodes/edges), invalid graph path rejection, and scenario-based precision/recall against explicitly labelled fixtures. No fabricated latency, accuracy or cost metrics should be placed in README/resume.

## Definition of done

- [ ] Docker starts both services on an actual teammate development machine
- [ ] All unit tests pass
- [ ] Smoke test passes against FalkorDB
- [ ] UI demo displays live query results
- [ ] Reports remain available after application restart
- [ ] Recorded demo shows real terminal test invocation and corresponding UI result
- [ ] Security scope and AI assistant disclosure reviewed by both team members
