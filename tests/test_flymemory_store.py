"""Unit tests for FlyMemoryStore persistent memory indexing and isolation."""
import pytest

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.store import FlyMemoryStore, IncidentMemory


def test_store_add_get_and_count():
    store = FlyMemoryStore()
    assert store.count() == 0

    mem = IncidentMemory(
        id="MEM-TEST-001",
        incident_id="INV-TEST-01",
        repo_id="REPO-COMMERCE",
        title="Test Payment Incident",
        change_id="payment",
        verdict="reproduced",
        verified=True,
        active_indices=[5, 12, 42, 99],
        symbols=["handle_gateway_webhook"],
        services=["S-PAYMENTS"],
        invariants=["INV-PAY-01"],
    )
    store.add(mem)

    assert store.count() == 1
    assert store.count("REPO-COMMERCE") == 1
    assert store.count("REPO-OTHER") == 0

    retrieved = store.get("MEM-TEST-001")
    assert retrieved is not None
    assert retrieved.title == "Test Payment Incident"
    assert retrieved.active_indices == [5, 12, 42, 99]


def test_store_repository_isolation():
    store = FlyMemoryStore()

    mem_a = IncidentMemory(
        id="MEM-A",
        incident_id="INV-A",
        repo_id="REPO-ALICE",
        title="Alice Payment Incident",
        change_id="payment",
        verdict="reproduced",
        verified=True,
        active_indices=[1, 2, 3, 4],
    )
    mem_b = IncidentMemory(
        id="MEM-B",
        incident_id="INV-B",
        repo_id="REPO-BOB",
        title="Bob Payment Incident",
        change_id="payment",
        verdict="reproduced",
        verified=True,
        active_indices=[1, 2, 3, 4],
    )
    store.add(mem_a)
    store.add(mem_b)

    # Searching in Alice's repo must NEVER return Bob's memories
    results_alice = store.search_similar("REPO-ALICE", [1, 2, 3, 4], top_k=5)
    assert len(results_alice) == 1
    assert results_alice[0][0].id == "MEM-A"

    results_bob = store.search_similar("REPO-BOB", [1, 2, 3, 4], top_k=5)
    assert len(results_bob) == 1
    assert results_bob[0][0].id == "MEM-B"


def test_store_projection_version_mismatch():
    cfg = FlyMemoryConfig(projection_version="fly-lsh-v1.0-standard")
    store = FlyMemoryStore(cfg)

    compatible_mem = IncidentMemory(
        id="MEM-COMPAT",
        incident_id="INV-1",
        repo_id="REPO-X",
        title="Compat Memory",
        change_id="c1",
        verdict="reproduced",
        verified=True,
        active_indices=[10, 20, 30],
        projection_version="fly-lsh-v1.0-standard",
    )
    incompatible_mem = IncidentMemory(
        id="MEM-INCOMPAT",
        incident_id="INV-2",
        repo_id="REPO-X",
        title="Incompat Memory",
        change_id="c2",
        verdict="reproduced",
        verified=True,
        active_indices=[10, 20, 30],
        projection_version="fly-lsh-v2.0-experimental",
    )

    store.add(compatible_mem)
    store.add(incompatible_mem)

    # Search should safely ignore incompatible projection version
    results = store.search_similar("REPO-X", [10, 20, 30], top_k=5)
    matched_ids = [m.id for m, _ in results]
    assert "MEM-COMPAT" in matched_ids
    assert "MEM-INCOMPAT" not in matched_ids, "Incompatible projection versions must be excluded from search"


def test_store_verified_only_filter():
    store = FlyMemoryStore()

    mem_verified = IncidentMemory(
        id="MEM-VERIF",
        incident_id="INV-V",
        repo_id="REPO-COMMERCE",
        title="Verified Regression",
        change_id="payment",
        verdict="reproduced",
        verified=True,
        active_indices=[1, 2, 3],
    )
    mem_unverified = IncidentMemory(
        id="MEM-UNVERIF",
        incident_id="INV-U",
        repo_id="REPO-COMMERCE",
        title="Unverified Guess",
        change_id="payment",
        verdict="inconclusive",
        verified=False,
        active_indices=[1, 2, 3],
    )

    store.add(mem_verified)
    store.add(mem_unverified)

    results = store.search_similar("REPO-COMMERCE", [1, 2, 3], only_verified=True)
    assert len(results) == 1
    assert results[0][0].id == "MEM-VERIF"
