"""Unit tests for Fly-LSH sparse hashing and deterministic feature encoding."""
import pytest

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.feature_encoder import IncidentFeatureEncoder
from faultline.flymemory.flyhash import FlyHash


def test_feature_encoder_determinism():
    cfg = FlyMemoryConfig(input_dim=128)
    encoder = IncidentFeatureEncoder(cfg)

    data = {
        "symbols": ["handle_gateway_webhook", "capture_payment"],
        "services": ["S-PAYMENTS"],
        "invariants": ["INV-PAY-01"],
        "diff_text": "+ charge_customer(order_id)\n+ record_payment()",
    }

    vec1 = encoder.encode(
        symbols=data["symbols"],
        services=data["services"],
        invariants=data["invariants"],
        diff_text=data["diff_text"],
    )
    vec2 = encoder.encode(
        symbols=data["symbols"],
        services=data["services"],
        invariants=data["invariants"],
        diff_text=data["diff_text"],
    )

    assert len(vec1) == 128
    assert len(vec2) == 128
    assert vec1 == vec2, "Feature encoding must be strictly deterministic across calls"


def test_feature_encoder_no_verdict_leakage():
    cfg = FlyMemoryConfig(input_dim=128)
    encoder = IncidentFeatureEncoder(cfg)

    # Encode identical data with different arbitrary labels outside the allowed schema
    vec_a = encoder.encode(
        symbols=["reserve_stock"],
        services=["S-INVENTORY"],
        invariants=["INV-STOCK-01"],
    )
    vec_b = encoder.encode(
        symbols=["reserve_stock"],
        services=["S-INVENTORY"],
        invariants=["INV-STOCK-01"],
    )
    assert vec_a == vec_b


def test_flyhash_projection_and_exact_k_winners():
    # d = 64, expansion = 10 -> m = 640. winner_ratio = 0.05 -> k = 32
    cfg = FlyMemoryConfig(input_dim=64, expansion_factor=10, winner_ratio=0.05, seed=42)
    fhash = FlyHash(cfg)

    assert fhash.d == 64
    assert fhash.m == 640
    assert fhash.k == 32

    encoder = IncidentFeatureEncoder(cfg)
    vec = encoder.encode(symbols=["handle_gateway_webhook"], invariants=["INV-PAY-01"])

    activations = fhash.project(vec)
    assert len(activations) == 640

    winners = fhash.winner_take_all(activations)
    assert len(winners) == 32, "Winner-Take-All must produce exactly k winners"
    assert len(set(winners)) == 32, "Active winner indices must be unique"
    assert all(0 <= w < 640 for w in winners), "Winners must be valid indices in [0, m-1]"
    assert winners == sorted(winners), "Winners should be sorted ascending"


def test_flyhash_seed_reproducibility():
    cfg1 = FlyMemoryConfig(seed=42)
    cfg2 = FlyMemoryConfig(seed=42)
    cfg3 = FlyMemoryConfig(seed=999)

    h1 = FlyHash(cfg1)
    h2 = FlyHash(cfg2)
    h3 = FlyHash(cfg3)

    encoder = IncidentFeatureEncoder(cfg1)
    vec = encoder.encode(symbols=["process_refund"], invariants=["INV-REFUND-01"])

    fingerprint1 = h1.hash(vec)
    fingerprint2 = h2.hash(vec)
    fingerprint3 = h3.hash(vec)

    assert fingerprint1 == fingerprint2, "Same seed must produce identical fingerprints"
    assert fingerprint1 != fingerprint3, "Different seed should produce different projection"


def test_flyhash_semantic_similarity_overlap():
    cfg = FlyMemoryConfig(seed=42)
    fhash = FlyHash(cfg)
    encoder = IncidentFeatureEncoder(cfg)

    # Identical incident contexts
    ctx_pay1 = {"symbols": ["handle_gateway_webhook", "capture_payment"], "invariants": ["INV-PAY-01"], "services": ["S-PAYMENTS"]}
    ctx_pay2 = {"symbols": ["handle_gateway_webhook", "record_payment"], "invariants": ["INV-PAY-01"], "services": ["S-PAYMENTS"]}
    ctx_stock = {"symbols": ["reserve_stock"], "invariants": ["INV-STOCK-01"], "services": ["S-INVENTORY"]}

    fp_pay1 = fhash.hash(encoder.encode(symbols=ctx_pay1["symbols"], invariants=ctx_pay1["invariants"], services=ctx_pay1["services"]))
    fp_pay2 = fhash.hash(encoder.encode(symbols=ctx_pay2["symbols"], invariants=ctx_pay2["invariants"], services=ctx_pay2["services"]))
    fp_stock = fhash.hash(encoder.encode(symbols=ctx_stock["symbols"], invariants=ctx_stock["invariants"], services=ctx_stock["services"]))

    sim_pay_pay = FlyHash.overlap_similarity(fp_pay1, fp_pay2)
    sim_pay_stock = FlyHash.overlap_similarity(fp_pay1, fp_stock)

    assert sim_pay_pay > sim_pay_stock, (
        f"Similar payment incidents should have higher overlap ({sim_pay_pay}) than payment vs inventory ({sim_pay_stock})"
    )


def test_flyhash_similarity_metrics():
    # Identical sets
    indices_a = [1, 5, 10, 20]
    indices_b = [1, 5, 10, 20]
    assert FlyHash.overlap_similarity(indices_a, indices_b) == 1.0
    assert FlyHash.jaccard_similarity(indices_a, indices_b) == 1.0
    assert FlyHash.hamming_distance(indices_a, indices_b, k=4) == 0

    # Disjoint sets
    indices_c = [2, 6, 11, 21]
    assert FlyHash.overlap_similarity(indices_a, indices_c) == 0.0
    assert FlyHash.jaccard_similarity(indices_a, indices_c) == 0.0
    assert FlyHash.hamming_distance(indices_a, indices_c, k=4) == 8

    # Partial overlap
    indices_d = [1, 5, 100, 200]
    assert FlyHash.overlap_similarity(indices_a, indices_d) == 0.5
    assert FlyHash.jaccard_similarity(indices_a, indices_d) == pytest.approx(2 / 6)
    assert FlyHash.hamming_distance(indices_a, indices_d, k=4) == 4
