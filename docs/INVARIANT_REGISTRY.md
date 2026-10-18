# Invariant registry and authority

Each rule stores ID, repository, immutable revision, description, related service/functions, source references, evidence category, approval status, approved-by identity, associated tests, verification history and review history where applicable.

- **DECLARED:** explicit maintainer requirements. The original trusted sample's four rules and service ownership mappings are now cited in `src/faultline/context_declarations.py`. These were already manually seeded; they were not discovered automatically. Three approved fixed tests point to actual assertions in `fixtures/scenarios.py`. Refund has no pre-existing fixed test and continues to use its supported constrained counterexample.
- **TEST-BACKED:** a suggestion grounded in an actual repository test assertion and statically resolved references. This demonstrates tested behavior, not automatically intended business behavior. Default status: `NEEDS_REVIEW`.
- **INFERRED:** a suggestion from a source `# Invariant:` comment or a constraint-like documentation sentence. Default status: `NEEDS_REVIEW`. It is a hypothesis, not an execution oracle.

Only rules in the correct repository/revision with `APPROVED`, an explicit approval identity and source evidence enter `validated_invariants`. The live agent intersects legacy plans and uncovered invariants with this approved set before execution. Approval alone does not create a new allowed runner scenario or authorize arbitrary code.

The Project Understanding UI is a **read-only review preview**; it has no fake Approve/Edit/Reject buttons. Persisted maintainer operations exist at:

```text
POST /api/v1/context/invariants/{id}/review?revision=baseline
X-Context-Maintainer-Token: <dedicated server-configured key>
{"action":"approve|edit|reject|disable", "reason":"...", "description":"required for edit"}
```

The existing optional API bearer protection also applies. The additional maintainer endpoint is disabled (503) unless `FZ_CONTEXT_MAINTAINER_KEY` is explicitly injected into the API server environment. A missing/wrong dedicated token receives 403. The default Compose setup does not enable this secret or expose review controls. Enabling review is a local operator deployment choice; this is not a multi-user identity system.

Editing returns a rule to `NEEDS_REVIEW`, clears its approval identity and preserves the review audit trail. Reject/disable remove authority. Reviews are scoped to a revision and are not silently propagated to a new revision. Declared sample requirements are explicit operator policy applied to supported source functions; suggestions do not inherit that approval. Verification history stores observed baseline/candidate outcomes and report IDs separately from source provenance.

Payment provenance example: `handle_gateway_webhook` is extracted from `commerce.py`; ownership and `INV-PAY-01` originate in the cited maintainer manifest; `payment_idempotency` in the external approved runner asserts `captures == 1`; the current runner compares both verified revisions. Exact SHAs, line references and measurements are in `output/project-context-evaluation.json`.
