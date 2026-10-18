#!/usr/bin/env python3
"""CLI runner for FlyMemory scientific evaluation benchmark."""
import json
from pathlib import Path
import sys

# Ensure src is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faultline.flymemory.evaluation import run_full_benchmark


def main():
    print("[FlyMemory] Running 4-strategy comparative retrieval benchmark...")
    results = run_full_benchmark()

    out_dir = Path(__file__).resolve().parents[1] / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "flymemory_evaluation.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[FlyMemory] Benchmark completed. Results saved to {out_file}")
    print("\n--- Comparative Strategies Summary ---")
    for strat in results["comparative_strategies"]:
        print(f"Strategy: {strat['strategy']}")
        if "recall_at_1" in strat:
            print(f"  Recall@1: {strat['recall_at_1']} | Recall@3: {strat['recall_at_3']} | MRR: {strat['mrr']}")
            print(f"  Mean Latency: {strat['latency_mean_ms']} ms")
        if "note" in strat:
            print(f"  Note: {strat['note']}")
        print()


if __name__ == "__main__":
    main()
