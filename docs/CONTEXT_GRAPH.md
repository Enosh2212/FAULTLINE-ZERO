# Context graph and provenance

The additive graph `<FZ_GRAPH_NAME>_context` stores repository and immutable revision on every source entity and relationship. Entity IDs take the form `repository@commit:kind:logical-name`. This prevents accidental cross-project/revision joins. Existing synthetic demo graph contracts are retained separately.

Node labels: Repository, Commit, File, Symbol, Service, BusinessInvariant, TestCase, DocumentationSource, Investigation and VerifiedFinding. Internal ContextProject/ContextSnapshot metadata stores current revision pointers and complete snapshot markers. A snapshot is consumed only after its completion marker is written. Repeat indexing uses MERGE and cached immutable snapshots; incomplete imports can be retried. Operations are serialized per registered repository in the API process.

Extracted edges include Commit CONTAINS File, File DEFINES Symbol, Symbol BELONGS_TO File, Class DEFINES Method, File IMPORTS local File, Symbol CALLS statically resolved Symbol, and Test Symbol REFERENCES target Symbol. Commit MODIFIES Symbol is based on AST differences. Declared Symbol BELONGS_TO Service, Service ENFORCES BusinessInvariant and approved external TestCase VALIDATES BusinessInvariant are explicitly marked DECLARED and cited to operator configuration/runner assertions. Rule SUPPORTED_BY source/symbol links preserve their evidence classification. Findings are created only from actual original-pass/modified-fail execution and remain separate from hypotheses.

Source paths, line ranges, content digests, revision, origin and classification are retained in JSON provenance. Query parameters carry all repository values; only fixed allowlisted node and edge labels are interpolated. The model receives no facility for writing arbitrary Cypher.

Example queries (parameters are mandatory):

```cypher
MATCH (s:Symbol {repository:$repository, revision:$revision})
RETURN s.name, s.id
```

```cypher
MATCH (s:Symbol)-[:BELONGS_TO]->(svc:Service)-[:ENFORCES]->(rule:BusinessInvariant)
WHERE s.repository=$repository AND s.revision=$revision
  AND svc.repository=$repository AND svc.revision=$revision
  AND rule.repository=$repository AND rule.revision=$revision
RETURN s.name, svc.name, rule.name, rule.payload
```

```cypher
MATCH (rule:BusinessInvariant {repository:$repository, revision:$revision})-[r:SUPPORTED_BY]->(source)
RETURN rule.name, source.name, r.provenance, r.classification
```

The retriever queries connected service/rule context with a bounded CALLS depth and row limit, filters approved rule records, caps source facts/hypotheses/documentation/history, and enforces a 24KB model package limit. Historical execution records are scoped to the same repository and candidate revision. The current pointer marks a view as current or historical; older immutable graphs are retained rather than relabeled as current facts.

Actual query text and outputs from an independent example are captured in `output/independent-context-demo.json`. Live approved-rule provenance and retrieval measurements are captured in `output/project-context-evaluation.json`. No performance improvement is claimed from these measurements.
