"""Executes pre-approved test scenarios on actual Python revision modules.

NOT a safe sandbox for executing untrusted user repositories. An isolated runner is
required before accepting arbitrary source, PRs or code attachments.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from faultline.schema import ExecutionResult
from faultline.fixtures.scenarios import ALLOWED_SCENARIOS


class ScenarioRunner:
    def __init__(self, timeout: int = 8) -> None:
        self.timeout = timeout

    def run(self, version: str, testcase_id: str) -> ExecutionResult:
        if testcase_id not in ALLOWED_SCENARIOS or version not in {"baseline", "candidate"}:
            return ExecutionResult(outcome="error", observed="Scenario not allowlisted", duration_ms=0)
        started = time.perf_counter()
        env = os.environ.copy()
        local_src = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = local_src + os.pathsep + env.get("PYTHONPATH", "")
        try:
            # No shell, no user-provided command, bounded runtime, separate process.
            proc = subprocess.run(
                [sys.executable, "-m", "faultline.runner_worker", version, testcase_id],
                capture_output=True, text=True, timeout=self.timeout, check=False, env=env,
            )
            payload = json.loads(proc.stdout.strip())
            if proc.returncode != 0 or payload.get("outcome") not in {"pass", "fail", "error"}:
                raise ValueError("runner reported an invalid response")
            return ExecutionResult(
                outcome=payload["outcome"], observed=str(payload["observed"])[:400],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError, OSError, KeyError):
            return ExecutionResult(outcome="error", observed="Execution unavailable or timed out",
                                   duration_ms=int((time.perf_counter() - started) * 1000))
