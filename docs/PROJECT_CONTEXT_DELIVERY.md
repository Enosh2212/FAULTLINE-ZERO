# Project context delivery and measured evidence

Implemented inside the existing application. The web preview is at http://localhost:8000/#project.

## Files added

- `src/faultline/repository_indexer.py`
- `src/faultline/code_relationship_extractor.py`
- `src/faultline/documentation_ingestor.py`
- `src/faultline/invariant_registry.py`
- `src/faultline/context_graph_builder.py`
- `src/faultline/context_retriever.py`
- `src/faultline/context_declarations.py`
- `src/faultline/project_context.py`
- `src/faultline/web/project_understanding.js`
- `tests/test_project_context.py`
- `scripts/context_smoke.py`, `scripts/context_demo.py`, `scripts/verify_context_ui.cjs`
- `docs/PROJECT_CONTEXT_ARCHITECTURE.md`, `docs/REPOSITORY_INDEXING.md`, `docs/INVARIANT_REGISTRY.md`, `docs/CONTEXT_GRAPH.md`, this delivery record

## Files modified

- `src/faultline/api.py`: additive registered-project APIs and separately protected invariant review
- `src/faultline/graph_repository.py`: context service hooks alongside existing behavior
- `src/faultline/tool_agent.py`: recorded bounded context, model prompt data and approved-rule gating
- `src/faultline/schema.py`: additive report `project_context` field
- `src/faultline/web/index.html`, `app.js`, `product.css`, `evidence_graph.js`: required landing copy, Project navigation/view, provenance and context graph
- `docs/AGENT_DESIGN.md`, `docs/PRODUCT_VISION.md`, `docs/BUILD_STATUS.md`, `README.md`

Compose, runner source, original fixtures, execution allowlists and existing API contracts remain in place.

## Exact independent indexing demonstration

Command: `docker compose exec -T api python scripts/context_demo.py`

Repository ID: `independent-python-example`

Original commit: `22800c165d5b93d30fda143b7a74f1d0fb747ee3`

Changed commit: `ad7927c4d6ec862678f869d2b4696795075fbe27`

This new local Python repository contains `orders.py`, `test_orders.py` and `README.md`, with no predefined payment, inventory or refund change identifier. Only source indexing occurred. The second revision parsed 1 changed file and reused 2 AST records. The repeat request was cached: `True`. Measured indexing: 16.453ms; graph persistence: 18.325ms. These are observations on this machine, not a claimed benchmark improvement.

No business rule was approved automatically. The initial bounded context status was `INSUFFICIENT_CONTEXT`. The operator-only persistence demo then exercised approve → edit → reject → disable on a test-backed suggestion; final status is DISABLED. This did not enable execution of the independent source.

## Actual FalkorDB query and rows

Parameters: `repository=independent-python-example`, `revision=ad7927c4d6ec862678f869d2b4696795075fbe27`.

```cypher
MATCH (a)-[r]->(b) WHERE a.repository=$repository AND a.revision=$revision RETURN a.name, type(r), b.name ORDER BY a.name, b.name LIMIT 12
```

First recorded rows:

| Source | Relationship | Target |
|---|---|---|
| A maintainer-reviewed example constraint | SUPPORTED_BY | bounded_total |
| A maintainer-reviewed example constraint | SUPPORTED_BY | test_orders.py |
| Order totals should never be negative. | SUPPORTED_BY | README.md |
| README.md | DOCUMENTED_BY | README.md |
| ad7927c4d6ec | CONTAINS | README.md |
| ad7927c4d6ec | MODIFIES | bounded_total |
| ad7927c4d6ec | CONTAINS | orders.py |
| ad7927c4d6ec | CONTAINS | test_orders.py |
| bounded_total | BELONGS_TO | orders.py |
| independent-python-example | CONTAINS | ad7927c4d6ec |

Complete output: [independent-context-demo.json](../output/independent-context-demo.json).

## One business-rule provenance trace

`INV-PAY-01` — A payment event must be captured only once.

Category `DECLARED`, approval `APPROVED`, authority `bundled demo maintainer manifest`. Related function: `handle_gateway_webhook`. The manifest establishes business intent; the external approved runner supplies the real assertion `captures == 1`. Source paths, line ranges and SHA256 digests are persisted:

- `package:faultline/context_declarations.py:10` · operator_declared_configuration
- `package:faultline/fixtures/scenarios.py:6` · operator_approved_runner

The trusted Git tree itself has 1 file, 5 discovered symbols and 0 repository test files. Its 3 runner tests are explicitly external declarations; the interface does not claim they were found in that Git tree.

Screenshot: [invariant-provenance.png](../output/invariant-provenance.png).

## Actual agent context trace

Report `INV-A2D808973AA2` recorded tool `retrieve_project_context`. Scope: `trusted-commerce` / `f31d7ccf6e051e1471107bcd0e5ed991155b3b53`. Status `GROUNDED_CONTEXT`. The changed symbol is `handle_gateway_webhook` and the approved rule is `INV-PAY-01`. This package is supplied as untrusted data to the existing model/tool protocol and is stored on the executed report. Scripted-model tests verify receipt; live scenario evaluation uses the real deterministic fallback.

| Change | Actual verdict | Approved rule | Retrieval ms | Graph reads ms | Context bytes |
|---|---|---|---:|---:|---:|
| payment | reproduced | INV-PAY-01 | 4.562 | 4.023 | 4968 |
| inventory | reproduced | INV-STOCK-01 | 4.338 | 3.918 | 4373 |
| refund | reproduced | INV-REFUND-01 | 2.567 | 2.246 | 5097 |
| control | not_reproduced | INV-ORDER-01 | 3.495 | 3.115 | 4613 |
| uncovered | inconclusive |  | 2.204 | 1.922 | 3469 |

Complete actual package, recorded step, rule provenance and timings: [project-context-evaluation.json](../output/project-context-evaluation.json).

## Validation

- Baseline: **35 passed in 45.19s**.
- Final automated suite: **69 passed in 63.49s**; includes **21 new context tests**.
- Existing browser acceptance: **66 passed**, zero JavaScript errors.
- Project Understanding browser acceptance: **15 passed**, zero JavaScript errors, including 1440px desktop and 390px mobile.
- Existing Docker smoke suite: **PASS**, legacy and real Git regressions, control, uncovered, refund holdout and persistence.
- Context smoke suite: **PASS**, persisted indexing, repeat behavior, approved provenance and all five context-enabled outcomes.
- Independent source-only demonstration: **PASS**, revision-aware reuse and persisted review lifecycle.
- Final API and FalkorDB containers are healthy.

## Screenshots

- [Project Understanding desktop](../output/project-understanding-desktop.png)
- [Project Understanding mobile](../output/project-understanding-mobile.png)
- [Business-rule source trace](../output/invariant-provenance.png)
- [Updated landing desktop](../output/context-landing-desktop.png)
- [Updated landing mobile](../output/context-landing-mobile.png)

## Remaining boundaries

The HTTP demo supports only the trusted bundled repository. The independent operator CLI supports source-only Python indexing; it does not authorize unknown code execution. Static analysis intentionally leaves dynamic/ambiguous calls unresolved. Documentation/API specifications are cited text, not complete semantic models. Approval UI is read-only; the separately authenticated review API is disabled by default. The default maintainer manifest remains manually declared and is visibly distinguished from automatic source facts.

Each new revision gets an immutable graph projection; AST reuse is incremental, while graph records are materialized for that revision. In-process indexing locks are not a distributed job queue. Snapshot retention, structural sharing, additional languages, multi-user authorization, public GitHub onboarding, webhook verification and secure unfamiliar-code execution require future work. Real Groq provider quality was not benchmarked here.

## Start / verify

From the FAULTLINE_ZERO repository:

```powershell
docker compose up --build -d
python -m pytest -q
python scripts/smoke_test.py
python scripts/context_smoke.py
docker compose exec -T api python scripts/context_demo.py
```
