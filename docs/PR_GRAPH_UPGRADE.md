# PR intelligence and evidence graph upgrade

## Implemented experience

FAULTLINE remains a general graph-native change investigation tool. The landing page has five sections and a Payment / Inventory / Refund selector. It only displays observations from saved executed reports; missing results are explicitly unavailable. Product messaging describes software dependencies and business rules.

The investigation defaults to Simple mode: local PR-check preview, plain-language finding, four-row context, balanced original/modified evidence, scoped recommendation, and a timeline assembled only from tools actually returned. The local check is explicitly advisory and unpublished. Technical mode opens the evidence graph, Git diff, tool traces and reproduction details. The user-requested investigation terminal remains available as a collapsed execution log with a controlled re-run action and copy support. There is no arbitrary shell input.

Reports use actual execution mode and revision identifiers. Duplicate runs and selection changes are disabled during execution. The pending timer reports real elapsed time, not invented agent progress. Previous proof is cleared when a run starts or the selection changes. A saved verdict is automatically displayed only when both revision IDs match the currently loaded change. Opening history uses the original diff captured in the report's get_git_diff tool result.

## Graph implementation

- Cytoscape.js **3.33.1**, MIT.
- elkjs **0.11.0**, Eclipse Public License 2.0.
- Both are pinned, vendored, licensed, and included in Python package data. No runtime CDN dependency.
- ELK's layered RIGHT layout calculates coordinates; Cytoscape's preset layout renders them directly. An adapter plugin is unnecessary for this contract.
- If ELK fails, a disclosed built-in horizontal semantic layout keeps the graph usable. If Cytoscape fails, the report, textual relationships and keyboard entity inspector remain available.
- Focused evidence starts with the existing evidence-subgraph response. No database relationship is invented or reversed. VALIDATES is reversed only in the layout constraint to position the test after the rule; its rendered arrow retains Test → Invariant.
- Observed pass/fail results are separate execution annotations, not fabricated database nodes or edges.
- Nodes use readable names and semantic type subtitles. Edges translate authentic relationship names. Node and edge inspectors explain provenance and avoid treating a dependency as proof of causation.
- Fit, pan, zoom, reset, selected-node focus, verified-path focus, typed neighbor expansion and collapse are supported. Keyboard entity selection and textual relationship buttons provide an alternative to canvas interaction.
- The knowledge explorer starts with service entities and their actual service relationships, adding at most 12 direct neighbors per expansion. Collapse preserves the initial entities.

## Files changed in this upgrade

| File | Purpose |
|---|---|
| src/faultline/web/index.html | Summary-first report shell, disclosures, explorer, generic landing and demo selector, future integration note |
| src/faultline/web/app.js | API orchestration, honest states, report selection, run lifecycle, saved evidence and navigation |
| src/faultline/web/report.js | Reusable local PR-check presentation, fact/evidence report, real activity timeline and reproduction formatting |
| src/faultline/web/evidence_graph.js | ELK layout integration, two graph experiences, inspectors, expansion, controls, accessibility and fallback |
| src/faultline/web/product.css | Responsive presentation and graph layout surfaces |
| src/faultline/web/vendor/cytoscape.min.js | Pinned Cytoscape build |
| src/faultline/web/vendor/elk.bundled.js | Pinned ELK build |
| src/faultline/web/vendor/CYTOSCAPE-LICENSE | Cytoscape license |
| src/faultline/web/vendor/ELK-LICENSE.md | ELK license |
| src/faultline/web/vendor/README.md | Version and integration provenance |
| pyproject.toml | Include vendored graph assets in installed package |
| scripts/verify_ui.cjs | End-to-end browser acceptance and resilience checks |
| docs/PR_GRAPH_UPGRADE.md | Implementation, future integration, validation and known limitations |
| README.md | Updated interface description and validation link |

Backend source, API contracts, evidence policy, database persistence, controlled scenario runner, Groq tool architecture and Compose configuration were retained.

## Verification

Baseline: **35 passed in 45.07s**.

After implementation: **35 passed in 41.91s** (`python -m pytest -q`).

The browser acceptance runner writes exact results to `output/ui-verification.json`. It exercises every supported Git scenario through the UI, duplicate-submission guards, clearing stale evidence, five-node graph readability, node/edge inspection, camera controls, expansion/collapse, Simple/Technical mode, recorded landing examples, and 1440×900 / 1366×768 / 390×844 layouts. It also injects provider, graph, ELK and Cytoscape failures to verify graceful degradation. Injected failures are test-only and are not advertised as real provider outages.

Docker was rebuilt and the live smoke suite checks FalkorDB readiness, legacy workflows, trusted Git diffs, persisted reports, and all five expected outcomes:

| Scenario | Expected result |
|---|---|
| Payment | reproduced, original PASS / modified FAIL |
| Inventory | reproduced, original PASS / modified FAIL |
| Refund holdout | reproduced with approved synthesized ScenarioSpec |
| Safe pricing refactor | not_reproduced |
| Uncovered shipping change | inconclusive; no invented execution |

Screenshots: `output/pr-report-desktop.png`, `output/evidence-expanded.png`, `output/knowledge-explorer.png`, plus `output/landing-1440.png`, `landing-1366.png`, `landing-390.png`, `report-1440.png`, `report-1366.png`, `report-390.png`, and corresponding `graph-*.png`.

## Future GitHub Checks integration — planned only

PR opened or updated → signature-verified GitHub App webhook → idempotent queued investigation worker → authorized repository snapshot → FalkorDB context → model-assisted or explicitly labeled fallback investigation → controlled dual-revision execution → policy-derived check conclusion → deep link to the immutable saved FAULTLINE report.

A future implementation needs scoped GitHub App installation permissions, webhook delivery deduplication, head-SHA binding, cancellation of superseded runs, and durable worker state. It should publish an in-progress check, then update that same check only from validated execution evidence. A clean result covers only selected scenarios. Missing evidence or infrastructure/provider errors must not produce a success conclusion. Repository branch protection remains a separate administrator-controlled policy. The current demo makes no external GitHub calls and creates no comments, check runs, PR numbers or merge gates.

## Known limitations

- Real GitHub App/webhook/check publishing remains planned; the presentation is local and advisory.
- Live model-driven execution was not revalidated in this UI upgrade. End-to-end scenario checks use the real deterministic fallback, labeled in the report. Existing Groq code is preserved.
- The existing API returns a complete graph snapshot. Rendering and expansion are incremental, but network fetch is not paginated. A production explorer should use bounded authenticated neighborhood endpoints and retention limits.
- Narrow screens keep graph nodes at a readable size and use horizontal scrolling inside the graph, with a textual alternative. The page itself must not overflow.
- The synchronous investigation endpoint returns its action list at completion. The UI reports elapsed time while waiting; it does not simulate streaming tool events.
- The automated browser runner expects Playwright to be installed and an Edge channel available (or FZ_BROWSER_CHANNEL configured). It is not added to production Python dependencies.

## Start and verify

From the FAULTLINE_ZERO project directory:

```powershell
docker compose up --build -d
python -m pytest -q
python scripts/smoke_test.py
```

Application: http://localhost:8000/#investigation

Editing preview (optional): `python scripts/preview.py` → http://localhost:8001

Browser acceptance: `node scripts/verify_ui.cjs` (requires Playwright; set `FZ_BASE_URL=http://localhost:8000` for the rebuilt application).

Final recorded results: **66 browser acceptance checks passed**, with **0 browser JavaScript errors**; **35 pytest tests passed in 41.91s**. The complete Docker smoke suite passed, including legacy regressions, control, persistence and all five trusted Git outcomes. See `output/ui-verification.json` for individual browser assertions. Screenshot inspection included the PR report, expanded five-node path with the node inspector, service explorer, and 390px report/landing layouts.
