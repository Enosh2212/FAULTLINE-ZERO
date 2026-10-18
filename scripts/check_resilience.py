"""Explicit local Docker disruption test; always restore the project graph service."""
import json
import os
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.getenv("FZ_BASE_URL", "http://127.0.0.1:8000")


def request(path, payload=None):
    headers = {"Content-Type": "application/json"}
    if os.getenv("FZ_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["FZ_API_KEY"]
    data = None if payload is None else json.dumps(payload).encode()
    with urlopen(Request(BASE + path, data=data, headers=headers), timeout=30) as response:
        return json.load(response)


def compose(*args):
    subprocess.run(["docker", "compose", *args], check=True)


def main():
    before = request("/api/v1/git/investigations", {"change":"payment", "mode":"deterministic"})
    try:
        compose("stop", "graph")
        try:
            request("/api/v1/git/investigations", {"change":"payment", "mode":"deterministic"})
            raise AssertionError("Graph-dependent execution unexpectedly succeeded")
        except HTTPError as exc:
            assert exc.code == 503, exc.code
            print("PASS: disconnected graph investigation returns 503", flush=True)
    finally:
        compose("start", "graph")
        compose("restart", "api")
    for _ in range(30):
        try:
            request("/api/v1/health/ready")
            break
        except (HTTPError, URLError, TimeoutError, ConnectionError):
            time.sleep(1)
    else:
        raise AssertionError("Graph/API did not recover")
    after = request("/api/v1/investigations/" + before["id"])
    assert after == before, "Persisted report changed across restart"
    print("PASS: full report, tool trace, revision hashes and findings survive graph/API restart", flush=True)


if __name__ == "__main__":
    main()
