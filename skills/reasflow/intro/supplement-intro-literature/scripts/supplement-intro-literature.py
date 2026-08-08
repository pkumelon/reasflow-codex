#!/usr/bin/env python3
"""Stable skill entry point for Introduction bibliography supplementation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


TARGET = (
    Path(__file__).resolve().parents[2]
    / "introduction-framing"
    / "scripts"
    / "supplement-intro-bib.py"
)


def _load_main():
    spec = importlib.util.spec_from_file_location("reasflow_supplement_intro_bib", TARGET)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bibliography supplementer: {TARGET}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
