#!/usr/bin/env python3
"""Fail if any `kevin.*` import under ./kevin does not resolve (missing modules).

Run from repo root: python scripts/check_kevin_imports.py
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


def _kevin_imports_from_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("kevin"):
                found.add(node.module)
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "kevin":
                    found.add("kevin")
                elif name.startswith("kevin."):
                    found.add(name)
    return found


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    kevin_dir = root / "kevin"
    if not kevin_dir.is_dir():
        print("error: kevin/ not found", file=sys.stderr)
        return 2

    sys.path.insert(0, str(root))

    all_modules: set[str] = set()
    for path in kevin_dir.rglob("*.py"):
        if "venv" in path.parts or ".venv" in path.parts:
            continue
        try:
            all_modules |= _kevin_imports_from_file(path)
        except SyntaxError as e:
            print(f"error: syntax error in {path}: {e}", file=sys.stderr)
            return 2

    # Only check submodules of kevin (not bare "kevin" from `import kevin`)
    to_check = sorted(m for m in all_modules if m.startswith("kevin.") or m == "kevin")

    failures: list[str] = []
    for mod in to_check:
        if mod == "kevin":
            spec = importlib.util.find_spec("kevin")
        else:
            spec = importlib.util.find_spec(mod)
        if spec is None:
            failures.append(mod)

    if failures:
        print("Unresolved kevin imports (missing package or module):", file=sys.stderr)
        for m in failures:
            print(f"  - {m}", file=sys.stderr)
        return 1

    print(f"ok: {len(to_check)} distinct kevin import targets resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
