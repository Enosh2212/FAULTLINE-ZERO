"""FlyMemory Store: Persistent associative incident memory.

Stores verified investigation patterns with their sparse FlyHash fingerprints,
FalkorDB graph references, and verification status.

Enforces:
- Repository isolation (no cross-tenant memory leakage).
- Projection version validation (prevents comparing incompatible fingerprints).
- Distinction between verified historical evidence and unverified hypotheses.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Any, Sequence
from uuid import uuid4

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.flyhash import FlyHash

logger = logging.getLogger(__name__)


@dataclass
class IncidentMemory:
    """A single persistent software incident memory record."""

    id: str
    incident_id: str
    repo_id: str
    title: str
    change_id: str
    verdict: str
    verified: bool
    active_indices: list[int]
    symbols: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    test_strategy: str = ""
    evidence_path: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    encoder_version: str = "fly-feat-v1.0"
    projection_version: str = "fly-lsh-v1.0-d128-m2560-k128-seed42"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncidentMemory:
        return cls(
            id=data["id"],
            incident_id=data["incident_id"],
            repo_id=data.get("repo_id", "REPO-COMMERCE"),
            title=data.get("title", ""),
            change_id=data.get("change_id", ""),
            verdict=data.get("verdict", "inconclusive"),
            verified=data.get("verified", False),
            active_indices=list(data.get("active_indices", [])),
            symbols=list(data.get("symbols", [])),
            services=list(data.get("services", [])),
            invariants=list(data.get("invariants", [])),
            test_strategy=data.get("test_strategy", ""),
            evidence_path=list(data.get("evidence_path", [])),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            encoder_version=data.get("encoder_version", "fly-feat-v1.0"),
            projection_version=data.get("projection_version", ""),
            metadata=data.get("metadata", {}),
        )


class FlyMemoryStore:
    """Manages associative incident memories with in-memory caching and FalkorDB persistence."""

    def __init__(self, config: FlyMemoryConfig | None = None) -> None:
        self.config = config or FlyMemoryConfig()
        self.memories: dict[str, IncidentMemory] = {}

    def add(self, memory: IncidentMemory) -> None:
        """Adds or updates a memory in the store."""
        # Enforce version compatibility
        if memory.projection_version and memory.projection_version != self.config.projection_version:
            logger.warning(
                "Memory %s has incompatible projection version %s != %s; adding with warning",
                memory.id,
                memory.projection_version,
                self.config.projection_version,
            )
        self.memories[memory.id] = memory

    def get(self, memory_id: str) -> IncidentMemory | None:
        return self.memories.get(memory_id)

    def count(self, repo_id: str | None = None) -> int:
        if repo_id is None:
            return len(self.memories)
        return sum(1 for m in self.memories.values() if m.repo_id == repo_id)

    def search_similar(
        self,
        repo_id: str,
        query_indices: Sequence[int],
        top_k: int = 5,
        min_threshold: float = 0.05,
        metric: str = "overlap",
        only_verified: bool = False,
    ) -> list[tuple[IncidentMemory, float]]:
        """Searches memories within repo_id for those with high fingerprint similarity."""
        candidates: list[tuple[IncidentMemory, float]] = []

        for mem in self.memories.values():
            # 1. Repository isolation
            if mem.repo_id != repo_id:
                continue

            # 2. Verification filter
            if only_verified and not mem.verified:
                continue

            # 3. Projection version check
            if mem.projection_version and mem.projection_version != self.config.projection_version:
                continue

            # 4. Compute similarity
            if metric == "jaccard":
                sim = FlyHash.jaccard_similarity(query_indices, mem.active_indices)
            else:
                sim = FlyHash.overlap_similarity(query_indices, mem.active_indices)

            if sim >= min_threshold:
                candidates.append((mem, sim))

        # Sort descending by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def save_to_falkordb(self, repo: Any, memory: IncidentMemory) -> None:
        """Persists an incident memory node and relationships in FalkorDB."""
        if not hasattr(repo, "_write"):
            return

        indices_json = json.dumps(memory.active_indices)
        symbols_json = json.dumps(memory.symbols)
        services_json = json.dumps(memory.services)
        invariants_json = json.dumps(memory.invariants)
        evidence_json = json.dumps(memory.evidence_path)

        cypher = """
        MERGE (m:IncidentMemory {id: $id})
        SET m.incident_id = $incident_id,
            m.repo_id = $repo_id,
            m.title = $title,
            m.change_id = $change_id,
            m.verdict = $verdict,
            m.verified = $verified,
            m.active_indices = $active_indices,
            m.symbols = $symbols,
            m.services = $services,
            m.invariants = $invariants,
            m.test_strategy = $test_strategy,
            m.evidence_path = $evidence_path,
            m.timestamp = $timestamp,
            m.projection_version = $projection_version
        """
        try:
            repo._write(
                cypher,
                id=memory.id,
                incident_id=memory.incident_id,
                repo_id=memory.repo_id,
                title=memory.title,
                change_id=memory.change_id,
                verdict=memory.verdict,
                verified=str(memory.verified),
                active_indices=indices_json,
                symbols=symbols_json,
                services=services_json,
                invariants=invariants_json,
                test_strategy=memory.test_strategy,
                evidence_path=evidence_json,
                timestamp=memory.timestamp,
                projection_version=memory.projection_version,
            )

            # Link to Repository
            repo._write(
                "MATCH (r:Repository {id: $repo_id}), (m:IncidentMemory {id: $id}) "
                "MERGE (r)-[:RECORDS_MEMORY]->(m)",
                repo_id=memory.repo_id,
                id=memory.id,
            )

            # Link to Services
            for svc in memory.services:
                repo._write(
                    "MATCH (s:Service {id: $svc}), (m:IncidentMemory {id: $id}) "
                    "MERGE (m)-[:AFFECTS]->(s)",
                    svc=svc,
                    id=memory.id,
                )

            # Link to Invariants
            for inv in memory.invariants:
                repo._write(
                    "MATCH (i:Invariant {id: $inv}), (m:IncidentMemory {id: $id}) "
                    "MERGE (m)-[:VIOLATES]->(i)",
                    inv=inv,
                    id=memory.id,
                )
        except Exception as exc:
            logger.warning("Failed to persist IncidentMemory to FalkorDB: %s", exc)

    def load_from_falkordb(self, repo: Any, repo_id: str = "REPO-COMMERCE") -> int:
        """Loads historical incident memories from FalkorDB into memory."""
        if not hasattr(repo, "_read"):
            return 0

        cypher = """
        MATCH (m:IncidentMemory {repo_id: $repo_id})
        RETURN m.id, m.incident_id, m.repo_id, m.title, m.change_id, m.verdict,
               m.verified, m.active_indices, m.symbols, m.services, m.invariants,
               m.test_strategy, m.evidence_path, m.timestamp, m.projection_version
        """
        count = 0
        try:
            rows = repo._read(cypher, repo_id=repo_id)
            for row in rows:
                mid, inc_id, r_id, title, chg_id, verd, verif, act_ind, syms, svcs, invs, strat, ev_p, ts, proj_ver = row
                active_indices = json.loads(act_ind) if isinstance(act_ind, str) else list(act_ind or [])
                symbols = json.loads(syms) if isinstance(syms, str) else list(syms or [])
                services = json.loads(svcs) if isinstance(svcs, str) else list(svcs or [])
                invariants = json.loads(invs) if isinstance(invs, str) else list(invs or [])
                evidence_path = json.loads(ev_p) if isinstance(ev_p, str) else list(ev_p or [])

                mem = IncidentMemory(
                    id=mid,
                    incident_id=inc_id,
                    repo_id=r_id,
                    title=title or "",
                    change_id=chg_id or "",
                    verdict=verd or "inconclusive",
                    verified=str(verif).lower() in ("true", "1"),
                    active_indices=active_indices,
                    symbols=symbols,
                    services=services,
                    invariants=invariants,
                    test_strategy=strat or "",
                    evidence_path=evidence_path,
                    timestamp=ts or datetime.now(timezone.utc).isoformat(),
                    projection_version=proj_ver or self.config.projection_version,
                )
                self.add(mem)
                count += 1
        except Exception as exc:
            logger.warning("Could not load memories from FalkorDB: %s", exc)
        return count


def seed_default_memories(store: FlyMemoryStore) -> None:
    """Seeds the store with canonical historical software incident regressions."""
    from faultline.flymemory.feature_encoder import IncidentFeatureEncoder

    cfg = store.config
    enc = IncidentFeatureEncoder(cfg)
    fhash = FlyHash(cfg)

    defaults = [
        {
            "id": "MEM-PAY-001",
            "incident_id": "INC-PAY-001",
            "title": "Payment gateway duplicate capture on network timeout",
            "change_id": "payment",
            "symbols": ["handle_gateway_webhook", "capture_payment"],
            "services": ["S-PAYMENTS", "S-GATEWAY"],
            "invariants": ["INV-PAY-01"],
            "test_strategy": "TC-PAY-IDEMPOTENCY",
            "evidence_path": ["GIT-PAYMENT", "handle_gateway_webhook", "S-PAYMENTS", "INV-PAY-01", "TC-PAY-IDEMPOTENCY"],
            "diff": "+ charge_customer(order_id)\n+ record_payment()",
        },
        {
            "id": "MEM-STK-001",
            "incident_id": "INC-STK-001",
            "title": "Warehouse inventory oversell missing select-for-update lock",
            "change_id": "inventory",
            "symbols": ["reserve_stock", "check_available_quantity"],
            "services": ["S-INVENTORY"],
            "invariants": ["INV-STOCK-01"],
            "test_strategy": "TC-STOCK-NONNEGATIVE",
            "evidence_path": ["GIT-INVENTORY", "reserve_stock", "S-INVENTORY", "INV-STOCK-01", "TC-STOCK-NONNEGATIVE"],
            "diff": "+ stock -= quantity\n+ save(stock)",
        },
        {
            "id": "MEM-REF-001",
            "incident_id": "INC-REF-001",
            "title": "Duplicate refund transaction credit race (Dynamic Counterexample)",
            "change_id": "refund",
            "symbols": ["process_refund"],
            "services": ["S-REFUNDS", "S-PAYMENTS"],
            "invariants": ["INV-REFUND-01"],
            "test_strategy": "SCENARIO-REFUND-01",
            "evidence_path": ["GIT-REFUND", "process_refund", "S-REFUNDS", "INV-REFUND-01", "SPEC-REFUND-01"],
            "diff": "+ customer_balance += refund_amount",
        },
        {
            "id": "MEM-CTL-001",
            "incident_id": "INC-CTL-001",
            "title": "Safe order total calculation refactoring clean control",
            "change_id": "control",
            "symbols": ["compute_total"],
            "services": ["S-ORDERS", "S-PRICING"],
            "invariants": ["INV-ORDER-01"],
            "test_strategy": "TC-ORDER-TOTAL-NONNEGATIVE",
            "evidence_path": ["GIT-CONTROL", "compute_total", "S-ORDERS", "INV-ORDER-01", "TC-ORDER-TOTAL-NONNEGATIVE"],
            "diff": "+ subtotal = sum(item.price for item in items)",
        },
    ]

    for d in defaults:
        vec = enc.encode(
            symbols=d["symbols"],
            services=d["services"],
            invariants=d["invariants"],
            diff_text=d["diff"],
            testcases=[d["test_strategy"]],
        )
        fingerprint = fhash.hash(vec)
        mem = IncidentMemory(
            id=d["id"],
            incident_id=d["incident_id"],
            repo_id="REPO-COMMERCE",
            title=d["title"],
            change_id=d["change_id"],
            verdict="reproduced" if d["change_id"] != "control" else "not_reproduced",
            verified=True,
            active_indices=fingerprint,
            symbols=d["symbols"],
            services=d["services"],
            invariants=d["invariants"],
            test_strategy=d["test_strategy"],
            evidence_path=d["evidence_path"],
            projection_version=cfg.projection_version,
        )
        store.add(mem)


# Global singleton store instance
_DEFAULT_STORE: FlyMemoryStore | None = None


def get_flymemory_store() -> FlyMemoryStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = FlyMemoryStore()
        seed_default_memories(_DEFAULT_STORE)
    return _DEFAULT_STORE
