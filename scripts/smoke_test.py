#!/usr/bin/env python3
"""End-to-end smoke verification against live Docker Compose deployment."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.getenv("FZ_BASE_URL", "http://localhost:8000")
KEY = os.getenv("FZ_API_KEY", "")


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/json"
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    with urlopen(Request(BASE + path, headers=headers, data=data), timeout=180) as response:
        return json.load(response)


def main():
    print("[1/6] Checking live FalkorDB graph...")
    assert request("/api/v1/health/ready")["graph"] == "FalkorDB"
    print("[2/6] Checking graph topology...")
    graph = request("/api/v1/graph")
    assert len(graph["nodes"]) >= 14 and len(graph["edges"]) >= 14, graph
    print(f"  {len(graph['nodes'])} nodes / {len(graph['edges'])} edges")
    print("[3/6] Checking graph-backed changes...")
    changes = request("/api/v1/changes")
    assert len(changes) >= 3
    print("[4/6] Executing two known regressions...")
    reports = []
    for identifier in ["CHG-PAY-001", "CHG-STOCK-002"]:
        report = request("/api/v1/investigations", {"change_id": identifier})
        assert report["verdict"] == "reproduced", report
        assert report["cases"][0]["baseline"]["outcome"] == "pass"
        assert report["cases"][0]["candidate"]["outcome"] == "fail"
        print(f"  {identifier} -> {report['id']} / REPRODUCED")
        reports.append(report)
    print("[5/6] Validating clean control without false positive...")
    control = request("/api/v1/investigations", {"change_id": "CHG-ORDER-003"})
    assert control["verdict"] == "not_reproduced", control
    print("[6/6] Verifying persisted graph investigation memory...")
    persisted = request("/api/v1/investigations/" + reports[0]["id"])
    assert persisted["cases"][0]["evidence_path"] == reports[0]["cases"][0]["evidence_path"]
    assert len(request("/api/v1/investigations")) >= 3
    print("[7/7] Verifying trusted real Git revisions and five honest outcomes (including holdout refund)...")
    for key, expected in [("payment", "reproduced"), ("inventory", "reproduced"), ("control", "not_reproduced"), ("uncovered", "inconclusive"), ("refund", "reproduced")]:
        diff = request("/api/v1/git/changes/" + key)
        assert "diff --git" in diff["diff"] and diff["modified_symbols"], diff
        report = request("/api/v1/git/investigations", {"change": key, "mode": "deterministic"})
        assert report["verdict"] == expected, report
        assert report["mode"] == "deterministic_fallback" and report["status"] == "completed"
        assert not any(s["status"] == "error" for s in report["steps"]), report
        if key == "uncovered":
            assert not report["cases"]
        elif key == "refund":
            assert len(report["cases"]) == 1
            assert report["cases"][0]["testcase_id"] == "SPEC-REFUND-IDEMPOTENCY"
        assert request("/api/v1/investigations/" + report["id"])["revisions"] == report["revisions"]
        print(f"  Git {key}: {expected}; tests={report['metrics']['tests_executed']}")
    print("PASS: legacy and real Git workflows, FalkorDB, holdout counterexample discovery, actual execution, persistence")



if __name__ == "__main__":
    try:
        main()
    except (AssertionError, HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
