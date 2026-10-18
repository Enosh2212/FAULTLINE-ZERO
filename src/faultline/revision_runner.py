"""Execute only verified, bundled Git demo blobs in a bounded child process."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from faultline.git_demo import inspect_change, repo_path
from faultline.schema import ExecutionResult
from faultline.fixtures.scenarios import ALLOWED_SCENARIOS


class RevisionRunner:
    def __init__(self, key: str, timeout: int = 8):
        self.key, self.timeout = key, timeout
        self.revisions = inspect_change(key)["revisions"]

    def run(self, version: str, testcase_id: str) -> ExecutionResult:
        if version not in self.revisions or testcase_id not in ALLOWED_SCENARIOS:
            return ExecutionResult(outcome="error", observed="Not allowlisted", duration_ms=0)
        started = time.perf_counter()
        # Do not forward API keys or provider credentials to executed code.
        env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA"}}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["FZ_DEMO_REPO"] = str(repo_path())
        try:
            proc = subprocess.run([sys.executable, "-m", "faultline.revision_runner", self.key, version, testcase_id],
                                  env=env, capture_output=True, text=True, timeout=self.timeout, check=False)
            if proc.returncode:
                raise ValueError("Worker failed")
            result = json.loads(proc.stdout)
            return ExecutionResult(**result, duration_ms=int((time.perf_counter()-started)*1000))
        except (ValueError, OSError, subprocess.TimeoutExpired):
            return ExecutionResult(outcome="error", observed="Revision execution failed or timed out", duration_ms=int((time.perf_counter()-started)*1000))

    def run_scenario(self, version: str, spec: object) -> ExecutionResult:
        if version not in self.revisions:
            return ExecutionResult(outcome="error", observed="Unknown revision", duration_ms=0)
        started = time.perf_counter()
        env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA"}}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["FZ_DEMO_REPO"] = str(repo_path())
        try:
            proc = subprocess.run([sys.executable, "-m", "faultline.revision_runner", self.key, version, "--spec", spec.model_dump_json()],
                                  env=env, capture_output=True, text=True, timeout=self.timeout, check=False)
            if proc.returncode:
                raise ValueError(f"Worker failed: {proc.stderr}")
            result = json.loads(proc.stdout)
            return ExecutionResult(**result, duration_ms=int((time.perf_counter()-started)*1000))
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            return ExecutionResult(outcome="error", observed=f"Scenario execution failed: {exc}", duration_ms=int((time.perf_counter()-started)*1000))


def main():
    import types
    from faultline.git_demo import git
    from faultline.scenario_spec import ScenarioInterpreter, ScenarioSpec

    args = sys.argv[1:]
    key, version = args[0], args[1]
    data = inspect_change(key)
    if version not in {"baseline", "candidate"}:
        raise ValueError("Not allowlisted revision")
    source = git(repo_path(), "show", data["revisions"][version] + ":commerce.py")
    module = types.ModuleType("trusted_commerce_revision")
    try:
        exec(compile(source, "commerce.py", "exec"), module.__dict__)
    except Exception as exc:
        print(json.dumps({"outcome": "error", "observed": f"Compilation error: {exc}"[:400]}))
        return

    if len(args) >= 4 and args[2] == "--spec":
        spec = ScenarioSpec.model_validate_json(args[3])
        result = ScenarioInterpreter.execute(module, spec)
        print(json.dumps({"outcome": result.outcome, "observed": result.observed[:400]}))
        return

    test = args[2]
    if test not in ALLOWED_SCENARIOS:
        raise ValueError("Not allowlisted")
    try:
        observed = ALLOWED_SCENARIOS[test](module)
        outcome = "pass"
    except AssertionError as exc:
        outcome, observed = "fail", str(exc)
    except Exception:
        outcome, observed = "error", "Trusted revision raised an execution error"
    print(json.dumps({"outcome": outcome, "observed": observed[:400]}))


if __name__ == "__main__":
    main()

