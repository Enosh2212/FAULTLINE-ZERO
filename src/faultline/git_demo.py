"""Trusted synthetic Git repository. No user-selected paths or refs are accepted.

Source blobs are checked against built-in contents before indexing or execution.
The subprocess boundary is for reliability, not an untrusted-code sandbox.
"""
import ast
import hashlib
import os
from pathlib import Path
import subprocess

from faultline.fixtures import baseline

BASE = Path(baseline.__file__).read_text(encoding="utf-8") + "\n\ndef shipping_quote(weight: int) -> int:\n    return weight * 10\n"
SOURCES = {
    "payment": BASE.replace('    if not any(item["event_id"] == event_id for item in ledger):\n        ledger.append', '    if True:  # regression: repeated delivery captures again\n        ledger.append'),
    "inventory": BASE.replace('    if stock < requested:\n        raise ValueError("not enough stock")\n', ''),
    "control": BASE.replace('return max(0, subtotal - discount)', 'return max(subtotal - discount, 0)'),
    "uncovered": BASE.replace('return weight * 10', 'return weight * 12'),
    "refund": BASE.replace('    if refund_id not in processed:\n        wallet["balance"] = wallet.get("balance", 0) + amount', '    if True:  # regression: duplicate refund delivery credits multiple times\n        wallet["balance"] = wallet.get("balance", 0) + amount'),
}
OWNERS = {
    "handle_gateway_webhook": "S-PAYMENTS",
    "reserve_inventory": "S-INVENTORY",
    "calculate_total": "S-ORDERS",
    "shipping_quote": "S-SHIPPING",
    "process_refund": "S-REFUNDS",
}
TITLES = {
    "payment": "Duplicate payment capture",
    "inventory": "Inventory oversell",
    "control": "Safe pricing refactor",
    "uncovered": "Shipping change without validated tests",
    "refund": "Refund balance idempotency regression (Holdout)",
}


def repo_path() -> Path:
    return Path(os.getenv("FZ_DEMO_REPO", str(Path(__file__).resolve().parents[2] / "demo-repository"))).resolve()


def git(root: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(root), *args],
                          check=True, capture_output=True, text=True, timeout=8, env=env).stdout.strip()


def create_demo(root: Path) -> None:
    if (root / ".git").exists():
        try:
            tags = set(git(root, "tag").splitlines())
            if "baseline" in tags and all(k in tags for k in SOURCES):
                return
        except Exception:
            return

    source = root / "commerce.py"
    if not (root / ".git").exists():
        root.mkdir(parents=True, exist_ok=True)
        if list(root.iterdir()):
            raise ValueError("Demo destination must be empty")
        git(root, "init")
        git(root, "config", "user.name", "FAULTLINE ZERO Demo")
        git(root, "config", "user.email", "demo@example.invalid")

    tags = set(git(root, "tag").splitlines()) if (root / ".git").exists() else set()
    rebuild_all = "baseline" not in tags

    if not rebuild_all:
        try:
            curr_base = git(root, "show", "baseline:commerce.py") + "\n"
            if curr_base.strip() != BASE.strip():
                rebuild_all = True
        except Exception:
            rebuild_all = True

    if rebuild_all:
        source.write_text(BASE, encoding="utf-8", newline="\n")
        git(root, "add", "commerce.py")
        git(root, "commit", "-m", "Correct independent commerce baseline")
        git(root, "tag", "-f", "baseline")

    for key, content in SOURCES.items():
        need_tag = rebuild_all or (key not in tags)
        if not need_tag:
            try:
                curr_content = git(root, "show", f"{key}:commerce.py") + "\n"
                if curr_content.strip() != content.strip():
                    need_tag = True
            except Exception:
                need_tag = True
        if need_tag:
            git(root, "checkout", "--detach", "baseline")
            source.write_text(content, encoding="utf-8", newline="\n")
            git(root, "add", "commerce.py")
            git(root, "commit", "-m", TITLES[key])
            git(root, "tag", "-f", key)

    git(root, "checkout", "--detach", "baseline")



def symbols(source: str) -> list[dict]:
    result = []
    def walk(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                result.append({"name": name, "kind": type(node).__name__, "start": node.lineno,
                               "end": node.end_lineno, "ast": ast.dump(node, include_attributes=False)})
                walk(node.body, name + ".")
    walk(ast.parse(source).body)
    return result


def inspect_change(key: str, root: Path | None = None) -> dict:
    if key not in SOURCES:
        raise ValueError("Unknown trusted demo change")
    root = root or repo_path()
    revisions = {"baseline": git(root, "rev-parse", "baseline^{commit}"), "candidate": git(root, "rev-parse", key + "^{commit}")}
    contents = {}
    for version, revision in revisions.items():
        content = git(root, "show", revision + ":commerce.py") + "\n"
        expected = BASE if version == "baseline" else SOURCES[key]
        if content.strip() != expected.strip():
            raise ValueError("Trusted demo source verification failed")
        files = git(root, "ls-tree", "--name-only", "-r", revision).splitlines()
        if files != ["commerce.py"]:
            raise ValueError("Unexpected files in trusted revision")
        contents[version] = content
    old = {s["name"]: s for s in symbols(contents["baseline"])}
    indexed = symbols(contents["candidate"])
    modified = [s for s in indexed if s["name"] not in old or s["ast"] != old[s["name"]]["ast"]]
    diff = git(root, "diff", "--no-ext-diff", "--no-textconv", "--unified=3", revisions["baseline"], revisions["candidate"], "--", "commerce.py")
    return {"key": key, "change_id": "GIT-" + key.upper(), "title": TITLES[key], "repository": "trusted-commerce", "revisions": revisions,
            "diff": diff, "files": ["commerce.py"], "imports": sorted({n.module or "" for n in ast.walk(ast.parse(contents["candidate"])) if isinstance(n, ast.ImportFrom)} | {alias.name for n in ast.walk(ast.parse(contents["candidate"])) if isinstance(n, ast.Import) for alias in n.names}), "symbols": [{k: v for k, v in s.items() if k != "ast"} for s in indexed],
            "modified_symbols": [s["name"] for s in modified], "sha256": {v: hashlib.sha256(c.encode()).hexdigest() for v,c in contents.items()}}


if __name__ == "__main__":
    create_demo(repo_path())
