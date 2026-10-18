"""FalkorDB persistence: graph is the required source of test selection and evidence.

FalkorDB.query returns row-oriented result_set. Repository translates only primitives
into public schema; no arbitrary Cypher is accepted from callers.
"""
from __future__ import annotations
import json
import logging
from typing import Protocol

from faultline.config import Settings
from faultline.schema import ChangeSummary, GraphEdge, GraphNode, GraphSnapshot, Investigation, PlanEntry
from faultline.seed import NODES, EDGES


logger = logging.getLogger(__name__)


class GraphUnavailable(RuntimeError):
    """Raised when FalkorDB query execution fails; API returns 503."""


PLAN_CYPHER = """
MATCH (change:Change {id: $change_id})-[:TOUCHES]->(symbol:Symbol)-[:PART_OF]->(seed:Service)
MATCH (seed)-[:CALLS*0..3]->(impacted:Service)
MATCH (impacted)-[:ENFORCES]->(invariant:Invariant)<-[:VALIDATES]-(test:TestCase)
RETURN DISTINCT symbol.id, seed.id, impacted.id, invariant.id, test.id
ORDER BY test.id
""".strip()

UNCOVERED_CYPHER = """
MATCH (change:Change {id: $change_id})-[:TOUCHES]->(symbol:Symbol)-[:PART_OF]->(seed:Service)
MATCH (seed)-[:CALLS*0..3]->(impacted:Service)
MATCH (impacted)-[:ENFORCES]->(invariant:Invariant)
WHERE NOT (invariant)<-[:VALIDATES]-(:TestCase)
RETURN DISTINCT symbol.id, seed.id, impacted.id, invariant.id, invariant.name, invariant.description
ORDER BY invariant.id
""".strip()


class GraphRepository(Protocol):
    def ready(self) -> bool: ...
    def bootstrap(self) -> None: ...
    def changes(self) -> list[ChangeSummary]: ...
    def change(self, change_id: str) -> ChangeSummary | None: ...
    def snapshot(self) -> GraphSnapshot: ...
    def plan(self, change_id: str) -> list[PlanEntry]: ...
    def uncovered_invariants(self, change_id: str) -> list[dict]: ...
    def evidence_subgraph(self, change_id: str) -> GraphSnapshot: ...
    def save(self, investigation: Investigation) -> None: ...
    def report(self, investigation_id: str) -> Investigation | None: ...
    def recent_reports(self, limit: int = 8) -> list[Investigation]: ...
    def save_incident_memory(self, memory: Any) -> None: ...



class FalkorGraphRepository:
    def __init__(self, settings: Settings) -> None:
        # Import on creation so pure runner/unit tests can run without a live graph.
        from falkordb import FalkorDB
        kwargs = {"host": settings.graph_host, "port": settings.graph_port, "socket_timeout": 5, "socket_connect_timeout": 5}
        if settings.graph_password:
            kwargs["password"] = settings.graph_password
        self.db = FalkorDB(**kwargs)
        self.graph = self.db.select_graph(settings.graph_name)

    def _read(self, query: str, **params: str) -> list[list]:
        try:
            return self.graph.ro_query(query, params=params).result_set
        except Exception as exc:
            logger.exception("FalkorDB read query failed")
            raise GraphUnavailable("Graph read unavailable") from exc

    def _write(self, query: str, **params: str) -> list[list]:
        try:
            return self.graph.query(query, params=params).result_set
        except Exception as exc:
            logger.exception("FalkorDB write query failed")
            raise GraphUnavailable("Graph write unavailable") from exc

    def ready(self) -> bool:
        try:
            return bool(self._write("RETURN 1"))
        except Exception:  # Readiness must never take the API down.
            return False

    def bootstrap(self) -> None:
        # Repeated startup is safe: MERGE on deterministic ids, then SET properties.
        for label, nodes in NODES.items():
            for item_id, name, description in nodes:
                self._write(
                    f"MERGE (n:{label} {{id: $id}}) SET n.name = $name, n.description = $description",
                    id=item_id, name=name, description=description,
                )
        for relation, edges in EDGES.items():
            for source_type, source, target_type, target in edges:
                self._write(
                    f"MATCH (a:{source_type} {{id: $source}}), (b:{target_type} {{id: $target}}) "
                    f"MERGE (a)-[:{relation}]->(b)", source=source, target=target,
                )

    def changes(self) -> list[ChangeSummary]:
        rows = self._read("MATCH (c:Change) RETURN c.id, c.name, c.description ORDER BY c.id")
        return [ChangeSummary(id=r[0], title=r[1], summary=r[2]) for r in rows]

    def change(self, change_id: str) -> ChangeSummary | None:
        rows = self._read(
            "MATCH (c:Change {id: $change_id}) RETURN c.id, c.name, c.description LIMIT 1",
            change_id=change_id,
        )
        return ChangeSummary(id=rows[0][0], title=rows[0][1], summary=rows[0][2]) if rows else None

    def snapshot(self) -> GraphSnapshot:
        nodes = self._read("MATCH (n) WHERE n.id IS NOT NULL RETURN n.id, n.name, labels(n)")
        edges = self._read(
            "MATCH (a)-[r]->(b) WHERE a.id IS NOT NULL AND b.id IS NOT NULL "
            "RETURN a.id, type(r), b.id"
        )
        return GraphSnapshot(
            nodes=[GraphNode(id=r[0], label=r[1] or r[0], kind=r[2][0]) for r in nodes],
            edges=[GraphEdge(source=r[0], relation=r[1], target=r[2]) for r in edges],
        )

    def plan(self, change_id: str) -> list[PlanEntry]:
        return [PlanEntry(
            symbol_id=r[0], origin_service=r[1], impacted_service=r[2],
            invariant_id=r[3], testcase_id=r[4],
        ) for r in self._read(PLAN_CYPHER, change_id=change_id)]

    def uncovered_invariants(self, change_id: str) -> list[dict]:
        rows = self._read(UNCOVERED_CYPHER, change_id=change_id)
        return [{"symbol_id": r[0], "origin_service": r[1], "impacted_service": r[2],
                 "invariant_id": r[3], "invariant_name": r[4], "description": r[5]} for r in rows]

    def evidence_subgraph(self, change_id: str) -> GraphSnapshot:
        node_rows = self._read("""
            MATCH path = (c:Change {id: $change_id})-[:TOUCHES]->(sym:Symbol)-[:PART_OF]->(svc:Service)-[:CALLS*0..3]->(imp:Service)-[:ENFORCES]->(inv:Invariant)
            UNWIND nodes(path) AS n
            RETURN DISTINCT n.id, n.name, labels(n)
        """, change_id=change_id)
        test_rows = self._read("""
            MATCH (c:Change {id: $change_id})-[:TOUCHES]->(:Symbol)-[:PART_OF]->(:Service)-[:CALLS*0..3]->(:Service)-[:ENFORCES]->(inv:Invariant)<-[:VALIDATES]-(t:TestCase)
            RETURN DISTINCT t.id, t.name, labels(t)
        """, change_id=change_id)
        spec_rows = self._read("""
            MATCH (c:Change {id: $change_id})<-[:INVESTIGATES]-(i:Investigation)-[:DISCOVERED]->(s:Scenario)
            RETURN DISTINCT s.id, s.name, labels(s)
        """, change_id=change_id)
        all_nodes = {r[0]: GraphNode(id=r[0], label=r[1] or r[0], kind=r[2][0]) for r in node_rows + test_rows + spec_rows}
        if not all_nodes:
            return GraphSnapshot(nodes=[], edges=[])
        node_ids = list(all_nodes.keys())
        edge_rows = self._read("""
            MATCH (a)-[r]->(b)
            WHERE a.id IN $node_ids AND b.id IN $node_ids
            RETURN DISTINCT a.id, type(r), b.id
        """, node_ids=node_ids)
        edges = [GraphEdge(source=r[0], relation=r[1], target=r[2]) for r in edge_rows]
        return GraphSnapshot(nodes=list(all_nodes.values()), edges=edges)


    def save(self, investigation: Investigation) -> None:
        # Public synthetic evidence only; production needs bounded retention/TTL.
        payload = investigation.model_dump_json()
        self._write(
            "MERGE (i:Investigation {id: $id}) "
            "SET i.change_id=$change_id, i.created_at=$created_at, i.verdict=$verdict, i.payload=$payload "
            "WITH i MATCH (c:Change {id: $change_id}) MERGE (i)-[:INVESTIGATES]->(c)",
            id=investigation.id, change_id=investigation.change_id,
            created_at=investigation.generated_at, verdict=investigation.verdict.value,
            payload=payload,
        )
        for case in investigation.cases:
            self._write(
                "MATCH (i:Investigation {id: $id}), (t:TestCase {id: $testcase}) "
                "MERGE (i)-[e:EXECUTED]->(t) SET e.verdict=$verdict",
                id=investigation.id, testcase=case.testcase_id, verdict=case.verdict.value,
            )

    def report(self, investigation_id: str) -> Investigation | None:
        rows = self._read(
            "MATCH (i:Investigation {id: $id}) RETURN i.payload LIMIT 1", id=investigation_id
        )
        return Investigation.model_validate_json(rows[0][0]) if rows else None

    def recent_reports(self, limit: int = 8) -> list[Investigation]:
        # Limit is not user-controlled and does not interpolate arbitrary SQL/Cypher.
        limit = max(1, min(limit, 25))
        rows = self._read(
            f"MATCH (i:Investigation) RETURN i.payload ORDER BY i.created_at DESC LIMIT {limit}"
        )
        reports = []
        for row in rows:
            try:
                reports.append(Investigation.model_validate_json(row[0]))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        return reports

    def project_context(self, data):
        from faultline.project_context import service_for
        return service_for(self).prepare_change(data)

    def record_project_context(self, data, report):
        from faultline.project_context import service_for
        service_for(self).store.record(data['repository'],data['revisions']['candidate'],report)

    def index_git(self, data: dict) -> None:
        """AST facts plus explicit service ownership; never infer business rules from code."""
        from faultline.git_demo import OWNERS
        def node(label, identifier, name):
            self._write(f"MERGE (n:{label} {{id:$id}}) SET n.name=$name", id=identifier, name=name)
        def edge(source, relation, target):
            self._write(f"MATCH (a {{id:$source}}), (b {{id:$target}}) MERGE (a)-[:{relation}]->(b)", source=source, target=target)
        node("Repository", "REPO-COMMERCE", "Trusted commerce Git demo")
        node("Service", "S-SHIPPING", "Shipping (no validated test)")
        self._write("MERGE (c:Change {id:$id}) SET c.name=$name, c.description=$description",
                    id=data["change_id"], name=data["title"], description=data["diff"][:8000])
        for version, sha in data["revisions"].items():
            commit = "COMMIT-" + sha
            node("Commit", commit, sha)
            edge("REPO-COMMERCE", "CONTAINS", commit)
            edge(data["change_id"], "COMPARES", commit)
        file_id = data["change_id"] + ":commerce.py"
        node("File", file_id, "commerce.py")
        edge("REPO-COMMERCE", "CONTAINS", file_id)
        edge("COMMIT-" + data["revisions"]["candidate"], "CONTAINS", file_id)
        for module in data.get("imports", []):
            node("Dependency", "MODULE-" + module, module)
            edge(file_id, "IMPORTS", "MODULE-" + module)
        for symbol in data["symbols"]:
            sid = data["change_id"] + ":" + symbol["name"]
            node("Symbol", sid, symbol["name"])
            self._write("MATCH (s:Symbol {id:$id}) SET s.start=$start, s.end=$end, s.kind=$kind",
                        id=sid, start=symbol["start"], end=symbol["end"], kind=symbol["kind"])
            edge(file_id, "DEFINES", sid)
            if symbol["name"] in OWNERS:
                edge(sid, "PART_OF", OWNERS[symbol["name"]])
            if symbol["name"] in data["modified_symbols"]:
                edge(data["change_id"], "TOUCHES", sid)
                edge("COMMIT-" + data["revisions"]["candidate"], "MODIFIES", sid)

    def save_actions(self, investigation: Investigation) -> None:
        for index, step in enumerate(investigation.steps):
            eid = investigation.id + ":TOOL:" + str(index)
            self._write("MATCH (i:Investigation {id:$id}) MERGE (t:ToolExecution {id:$eid}) "
                        "SET t.name=$name, t.payload=$payload MERGE (i)-[:EXECUTED]->(t)",
                        id=investigation.id, eid=eid, name=step.tool, payload=step.model_dump_json())
        for index, case in enumerate(investigation.cases):
            fid = investigation.id + ":FINDING:" + str(index)
            if case.testcase_id.startswith("SPEC-"):
                self._write("MATCH (i:Investigation {id:$id}) "
                            "MERGE (s:Scenario {id:$test}) SET s.name=$test "
                            "MERGE (f:Finding {id:$fid}) SET f.name=$name, f.payload=$payload "
                            "MERGE (i)-[:FOUND]->(f) MERGE (i)-[:DISCOVERED]->(s) MERGE (f)-[:SUPPORTED_BY]->(s)",
                            id=investigation.id, test=case.testcase_id, fid=fid, name=case.verdict.value,
                            payload=case.model_dump_json())
                self._write("MATCH (s:Scenario {id:$test}), (inv:Invariant {id:$inv_id}) MERGE (s)-[:TARGETS]->(inv)",
                            test=case.testcase_id, inv_id=case.invariant_id)
            else:
                self._write("MATCH (i:Investigation {id:$id}), (t:TestCase {id:$test}) "
                            "MERGE (f:Finding {id:$fid}) SET f.name=$name, f.payload=$payload "
                            "MERGE (i)-[:FOUND]->(f) MERGE (f)-[:SUPPORTED_BY]->(t)",
                            id=investigation.id, test=case.testcase_id, fid=fid, name=case.verdict.value,
                            payload=case.model_dump_json())

            for action_index, step in enumerate(investigation.steps):
                match_step = (
                    (step.tool == "compare_revisions" and step.arguments.get("testcase_id") == case.testcase_id) or
                    (step.tool == "execute_counterexample" and step.arguments.get("scenario_id") == case.testcase_id)
                )
                if match_step and step.status == "ok":
                    self._write("MATCH (f:Finding {id:$fid}), (t:ToolExecution {id:$eid}) MERGE (f)-[:SUPPORTED_BY]->(t)",
                                fid=fid, eid=investigation.id + ":TOOL:" + str(action_index))

    def save_incident_memory(self, memory: Any) -> None:
        """Persists FlyMemory IncidentMemory node and topological association edges in FalkorDB."""
        from faultline.flymemory.store import get_flymemory_store
        store = get_flymemory_store()
        store.save_to_falkordb(self, memory)

