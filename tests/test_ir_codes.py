"""Unit tests for built-in IR code maps and Pronto encoding."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IR_CODES = ROOT / "custom_components" / "binary_moip" / "ir_codes"


def _ensure_pkg(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


def _load(name: str, path: Path):
    full_name = f"custom_components.binary_moip.ir_codes.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    _ensure_pkg("custom_components", ROOT / "custom_components")
    _ensure_pkg("custom_components.binary_moip", ROOT / "custom_components" / "binary_moip")
    _ensure_pkg("custom_components.binary_moip.ir_codes", IR_CODES)
    spec = importlib.util.spec_from_file_location(full_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _load_ir_codes():
    _load("pronto", IR_CODES / "pronto.py")
    _load("samsung", IR_CODES / "samsung.py")
    _load("lg", IR_CODES / "lg.py")
    return _load("__init__", IR_CODES / "__init__.py")


ir_codes = _load_ir_codes()
pronto = sys.modules["custom_components.binary_moip.ir_codes.pronto"]
samsung = sys.modules["custom_components.binary_moip.ir_codes.samsung"]
lg = sys.modules["custom_components.binary_moip.ir_codes.lg"]

resolve_pronto = ir_codes.resolve_pronto
list_commands = ir_codes.list_commands
SUPPORTED_BRANDS = ir_codes.SUPPORTED_BRANDS
encode_samsung = pronto.encode_samsung


KNOWN_SAMSUNG_POWER_ON = (
    "0000 006D 0000 0022 00AC 00AC 0015 0040 0015 0040 0015 0040 0015 0015 "
    "0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 "
    "0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 "
    "0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 "
    "0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 "
    "0015 0689"
)


def test_encode_samsung_matches_known_power_on() -> None:
    assert encode_samsung(0xE0E09966) == KNOWN_SAMSUNG_POWER_ON


def test_resolve_samsung_power_on() -> None:
    assert resolve_pronto("samsung", "power_on") == KNOWN_SAMSUNG_POWER_ON


def test_resolve_is_case_insensitive() -> None:
    assert resolve_pronto("Samsung", "POWER_ON") == resolve_pronto("samsung", "power_on")


def test_resolve_lg_returns_pronto() -> None:
    code = resolve_pronto("lg", "mute")
    words = code.split()
    assert words[0] == "0000"
    assert words[1] == "006D"
    assert len(words) == 72  # header + 34 pairs


def test_brands_share_command_names() -> None:
    assert set(samsung.COMMANDS) == set(lg.COMMANDS)


def test_list_commands() -> None:
    commands = list_commands("samsung")
    assert "power_on" in commands
    assert commands == sorted(commands)


def test_unsupported_brand() -> None:
    with pytest.raises(ValueError, match="Unsupported IR brand"):
        resolve_pronto("sony", "power")


def test_unknown_command() -> None:
    with pytest.raises(ValueError, match="Unknown IR command"):
        resolve_pronto("samsung", "picture_mode")


def test_supported_brands() -> None:
    assert SUPPORTED_BRANDS == ("samsung", "lg")
