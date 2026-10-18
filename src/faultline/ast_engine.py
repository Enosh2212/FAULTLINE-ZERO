"""Robust, bounded, read-only Python AST extraction and semantic comparison engine.

Never executes arbitrary repository code. All analysis is static and safe.
"""
from __future__ import annotations

import ast
import copy
import hashlib
from typing import Any, Dict, List, Optional, Tuple


def digest(value: str) -> str:
    """Computes a SHA-256 hexadecimal hash of the given string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_docstring(node: ast.AST) -> ast.AST:
    """Returns a deep copy of an AST node with its leading docstring expression removed."""
    node_copy = copy.deepcopy(node)
    if isinstance(node_copy, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        if node_copy.body and isinstance(node_copy.body[0], ast.Expr):
            val = node_copy.body[0].value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                node_copy.body.pop(0)
    return node_copy


def get_docstring(node: ast.AST) -> Optional[str]:
    """Extracts docstring from a function, class, or module node if present."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        if node.body and isinstance(node.body[0], ast.Expr):
            val = node.body[0].value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                return val.value
    return None


def normalize_ast_dump(node: ast.AST, ignore_docstring: bool = True) -> str:
    """
    Produces a normalized AST string dump independent of whitespace, comments,
    formatting, and line numbers. When ignore_docstring=True, leading docstrings are stripped.
    """
    target = strip_docstring(node) if ignore_docstring else node
    return ast.dump(target, include_attributes=False)


class PythonASTExtractor:
    """Extracts symbols, imports, calls, entry points, and test references from Python source code."""

    def __init__(self, source: str, file_path: str):
        # Strip UTF-8 BOM if present to ensure clean AST parsing across Windows & Git checkouts
        if isinstance(source, str) and source.startswith("\ufeff"):
            source = source.lstrip("\ufeff")
        self.source = source or ""
        self.file_path = file_path
        self.tree: Optional[ast.Module] = None
        self.parse_error: Optional[str] = None
        try:
            self.tree = ast.parse(self.source)
        except (SyntaxError, RecursionError, UnicodeDecodeError) as exc:
            self.parse_error = str(exc)[:250]

    def extract(self) -> Dict[str, Any]:
        """Extracts complete static symbol metadata, imports, calls, and entry points."""
        if self.tree is None:
            return {
                "path": self.file_path,
                "lines": len(self.source.splitlines()),
                "is_entry_point": False,
                "symbols": [],
                "imports": [],
                "calls": [],
                "assertions": [],
                "tests": [],
                "entry_points": [],
                "parse_error": self.parse_error,
            }

        symbols: List[Dict[str, Any]] = []
        docstrings: Dict[str, str] = {}

        def walk_body(body: List[ast.stmt], prefix: str = "", parent: Optional[str] = None):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f"{prefix}{node.name}"
                    doc = get_docstring(node)
                    if doc:
                        docstrings[name] = doc

                    raw_fingerprint = digest(ast.dump(node, include_attributes=False))
                    semantic_fingerprint = digest(normalize_ast_dump(node, ignore_docstring=True))

                    symbols.append({
                        "name": name,
                        "kind": type(node).__name__,
                        "start": getattr(node, "lineno", 1),
                        "end": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                        "parent": parent,
                        "fingerprint": raw_fingerprint,
                        "semantic_fingerprint": semantic_fingerprint,
                        "docstring": doc,
                    })

                    walk_body(node.body, f"{name}.", name)

        walk_body(self.tree.body)

        imports: List[Dict[str, Any]] = []
        calls: List[Dict[str, Any]] = []
        assertions: List[Dict[str, Any]] = []
        entry_points: List[str] = []

        # Find enclosing symbol helper
        sorted_symbols = sorted(symbols, key=lambda s: s["end"] - s["start"])

        def find_scope(lineno: int) -> Optional[str]:
            for s in sorted_symbols:
                if s["start"] <= lineno <= s["end"]:
                    return s["name"]
            return None

        # Inspect top-level and walk nodes
        for node in ast.walk(self.tree):
            line = getattr(node, "lineno", 0)
            scope = find_scope(line)

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "alias": alias.asname or alias.name.split(".")[0],
                        "member": None,
                        "explicit_alias": alias.asname is not None,
                        "level": 0,
                        "line": line,
                        "scope": scope,
                    })
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append({
                        "module": node.module or "",
                        "alias": alias.asname or alias.name,
                        "member": alias.name,
                        "level": node.level,
                        "line": line,
                        "scope": scope,
                    })
            elif isinstance(node, ast.Call):
                try:
                    callee = ast.unparse(node.func)
                except Exception:
                    callee = ""
                if callee:
                    calls.append({"callee": callee, "line": line, "scope": scope})
            elif isinstance(node, ast.Assert):
                try:
                    expr_text = ast.unparse(node.test)[:500]
                except Exception:
                    expr_text = "assert"
                assertions.append({"line": line, "expression": expr_text, "scope": scope})
            elif isinstance(node, ast.If):
                # Detect `if __name__ == '__main__':`
                try:
                    test_str = ast.unparse(node.test)
                    if "__name__" in test_str and "__main__" in test_str:
                        entry_points.append(f"{self.file_path}:{line}:__main__")
                except Exception:
                    pass

        # Detect CLI or web framework entrypoints
        for s in symbols:
            s_name_lower = s["name"].lower()
            if s_name_lower in {"main", "run", "cli", "app"} or s_name_lower.startswith("test_"):
                entry_points.append(f"{self.file_path}#{s['name']}")

        tests = [
            {
                "name": s["name"],
                "start": s["start"],
                "end": s["end"],
                "assertions_count": sum(1 for a in assertions if a.get("scope") == s["name"]),
            }
            for s in symbols
            if s["name"].startswith("test_") or s["name"].startswith("test")
        ]

        return {
            "path": self.file_path,
            "lines": len(self.source.splitlines()),
            "is_entry_point": bool(entry_points),
            "symbols": symbols,
            "imports": imports,
            "calls": calls,
            "assertions": assertions,
            "tests": tests,
            "entry_points": list(dict.fromkeys(entry_points)),
            "parse_error": None,
        }


def compare_symbol_ast(
    base_source: Optional[str],
    head_source: Optional[str],
    symbol_name: str,
) -> Dict[str, Any]:
    """
    Compares a symbol between base and head source revisions.
    
    Returns a dictionary with:
      - status: 'ADDED', 'REMOVED', 'IDENTICAL', 'DOCS_ONLY', 'SEMANTIC_MODIFIED'
      - is_semantic: bool
      - details: str explanation
    """
    if isinstance(base_source, str) and base_source.startswith("\ufeff"):
        base_source = base_source.lstrip("\ufeff")
    if isinstance(head_source, str) and head_source.startswith("\ufeff"):
        head_source = head_source.lstrip("\ufeff")

    if base_source is None and head_source is not None:
        return {
            "status": "ADDED",
            "is_semantic": True,
            "details": f"Symbol '{symbol_name}' was newly added in head commit.",
        }
    if base_source is not None and head_source is None:
        return {
            "status": "REMOVED",
            "is_semantic": True,
            "details": f"Symbol '{symbol_name}' was removed in head commit.",
        }
    if base_source is None and head_source is None:
        return {
            "status": "IDENTICAL",
            "is_semantic": False,
            "details": f"Symbol '{symbol_name}' not found in either revision.",
        }

    base_extractor = PythonASTExtractor(base_source, "base")
    head_extractor = PythonASTExtractor(head_source, "head")

    base_syms = {s["name"]: s for s in base_extractor.extract()["symbols"]}
    head_syms = {s["name"]: s for s in head_extractor.extract()["symbols"]}

    b_sym = base_syms.get(symbol_name)
    h_sym = head_syms.get(symbol_name)

    if not b_sym and not h_sym:
        return {
            "status": "IDENTICAL",
            "is_semantic": False,
            "details": f"Symbol '{symbol_name}' not found in AST of either revision.",
        }
    if not b_sym and h_sym:
        return {
            "status": "ADDED",
            "is_semantic": True,
            "details": f"Symbol '{symbol_name}' was added to module.",
        }
    if b_sym and not h_sym:
        return {
            "status": "REMOVED",
            "is_semantic": True,
            "details": f"Symbol '{symbol_name}' was removed from module.",
        }

    assert b_sym is not None and h_sym is not None

    # Check raw fingerprint (exact AST match including docstring)
    if b_sym["fingerprint"] == h_sym["fingerprint"]:
        return {
            "status": "IDENTICAL",
            "is_semantic": False,
            "details": f"Symbol '{symbol_name}' AST is byte-for-byte identical.",
        }

    # Check semantic fingerprint (AST match excluding docstring)
    if b_sym["semantic_fingerprint"] == h_sym["semantic_fingerprint"]:
        return {
            "status": "DOCS_ONLY",
            "is_semantic": False,
            "details": (
                f"Symbol '{symbol_name}' executable AST statements are identical. "
                "Only docstring, comments, or formatting were updated."
            ),
        }

    return {
        "status": "SEMANTIC_MODIFIED",
        "is_semantic": True,
        "details": f"Symbol '{symbol_name}' executable logic or signature was modified.",
    }
