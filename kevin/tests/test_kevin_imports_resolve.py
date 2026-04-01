"""Guardrail: every `kevin.*` import under kevin/ must resolve (no missing modules)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_all_kevin_imports_resolve() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "check_kevin_imports.py"
    spec = importlib.util.spec_from_file_location("check_kevin_imports", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
