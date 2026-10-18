"""Child process entry point. Only allowlisted synthetic scenarios may be executed."""
import json
import sys
from faultline.fixtures.scenarios import execute


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"outcome": "error", "observed": "invalid arguments"}))
        return 2
    version, testcase_id = sys.argv[1:]
    try:
        observed = execute(version, testcase_id)
        payload = {"outcome": "pass", "observed": observed}
    except AssertionError as exc:
        payload = {"outcome": "fail", "observed": str(exc)[:400]}
    except (ValueError, ImportError, AttributeError) as exc:
        payload = {"outcome": "error", "observed": str(exc)[:400]}
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
