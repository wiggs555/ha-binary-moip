"""Load integration modules without importing Home Assistant package init."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "custom_components" / "binary_moip"


def _load_module(name: str, path: Path):
    full_name = f"custom_components.binary_moip.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_adapter_module():
    """Import adapter.py without loading binary_moip/__init__.py."""
    _load_module("const", COMPONENTS / "const.py")
    return _load_module("adapter", COMPONENTS / "adapter.py")
