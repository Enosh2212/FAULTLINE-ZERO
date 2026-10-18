// Essential agent tool: graph-based affected-test discovery.
// $change_id is passed by FalkorDB parameter binding in the Python client.
MATCH (change:Change {id: $change_id})-[:TOUCHES]->(symbol:Symbol)-[:PART_OF]->(seed:Service)
MATCH (seed)-[:CALLS*0..3]->(impacted:Service)
MATCH (impacted)-[:ENFORCES]->(invariant:Invariant)<-[:VALIDATES]-(test:TestCase)
RETURN DISTINCT symbol.id, seed.id, impacted.id, invariant.id, test.id
ORDER BY test.id;

// Graph provenance / visualization (service, invariant and test edges).
MATCH (a)-[r]->(b)
WHERE a.id IS NOT NULL AND b.id IS NOT NULL
RETURN a.id, type(r), b.id;

// Read recent cross-session agent investigations.
MATCH (i:Investigation)
RETURN i.payload
ORDER BY i.created_at DESC
LIMIT 8;

// Explicit reasoning: which code changes are connected to a business invariant?
MATCH (change:Change)-[:TOUCHES]->(:Symbol)-[:PART_OF]->(s:Service)
MATCH (s)-[:CALLS*0..3]->(affected:Service)-[:ENFORCES]->(inv:Invariant {id: $invariant_id})
RETURN DISTINCT change.id, affected.id, inv.id;


// Git facts: label/relation choices are internal constants, values are parameters.
MERGE (r:Repository {id: $repository_id}) SET r.name = $name;
MERGE (c:Commit {id: $commit_id}) SET c.name = $sha;
MATCH (r:Repository {id: $repository_id}), (c:Commit {id: $commit_id})
MERGE (r)-[:CONTAINS]->(c);
MATCH (f:File {id: $file_id}), (s:Symbol {id: $symbol_id})
MERGE (f)-[:DEFINES]->(s);
MATCH (c:Commit {id: $commit_id}), (s:Symbol {id: $symbol_id})
MERGE (c)-[:MODIFIES]->(s);

// Explicit changed-symbol provenance; retains original plan compatibility.
MATCH (c:Change {id: $change_id}), (s:Symbol {id: $symbol_id})
MERGE (c)-[:TOUCHES]->(s);

// Tool checkpoint. Full JSON contains arguments, duration, status and actual result.
MATCH (i:Investigation {id:$id}) MERGE (t:ToolExecution {id:$eid})
SET t.name=$name, t.payload=$payload MERGE (i)-[:EXECUTED]->(t);

// Findings always originate from executed comparisons, never model prose.
MATCH (i:Investigation {id:$id}), (t:TestCase {id:$test})
MERGE (f:Finding {id:$fid}) SET f.name=$name, f.payload=$payload
MERGE (i)-[:FOUND]->(f) MERGE (f)-[:SUPPORTED_BY]->(t);

// Historical memory candidate query; application then filters same change/completed.
MATCH (i:Investigation) RETURN i.payload ORDER BY i.created_at DESC LIMIT 25;
