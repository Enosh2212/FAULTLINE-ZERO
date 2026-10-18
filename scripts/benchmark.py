#!/usr/bin/env python3
"""Measure real end-to-end investigation latency; prints observed values only.

Runs against the local Docker stack; creates an Investigation graph node per run.
"""
import os
import json
import statistics
import time
from urllib.request import Request, urlopen

BASE = os.getenv("FZ_BASE_URL", "http://localhost:8000")
CHANGE = os.getenv("FZ_BENCHMARK_CHANGE", "CHG-PAY-001")
ITERATIONS = max(1, min(20, int(os.getenv("FZ_BENCHMARK_RUNS", "5"))))
KEY = os.getenv("FZ_API_KEY", "")

def main():
    times = []
    for i in range(ITERATIONS):
        headers = {"Content-Type": "application/json"}
        if KEY:
            headers["Authorization"] = "Bearer " + KEY
        request = Request(BASE + "/api/v1/investigations", method="POST", headers=headers,
                          data=json.dumps({"change_id": CHANGE}).encode())
        start = time.perf_counter()
        with urlopen(request, timeout=25) as response:
            report = json.load(response)
        elapsed = (time.perf_counter() - start) * 1000
        assert report["selected_test_count"] > 0
        times.append(elapsed)
        print(f"Run {i+1}: {elapsed:.1f}ms / {report['verdict']}")
    s = sorted(times)
    print(f"Count={len(times)} p50={statistics.median(times):.1f}ms "
          f"p95={s[max(0, int(len(s)*0.95+0.999)-1)]:.1f}ms "
          f"min={min(times):.1f}ms max={max(times):.1f}ms")

if __name__ == "__main__":
    main()
