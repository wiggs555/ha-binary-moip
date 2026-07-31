"""Load integration modules without importing Home Assistant package init."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

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


def _ensure_homeassistant_stubs() -> None:
    """Install lightweight Home Assistant stubs for unit tests."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    components = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = components

    media_player = types.ModuleType("homeassistant.components.media_player")

    class MediaPlayerEntity:  # noqa: D101
        pass

    class MediaPlayerEntityFeature:  # noqa: D101
        SELECT_SOURCE = 1
        TURN_ON = 2
        TURN_OFF = 4
        VOLUME_STEP = 8
        VOLUME_MUTE = 16

    class MediaPlayerState:  # noqa: D101
        ON = "on"
        OFF = "off"

    media_player.MediaPlayerEntity = MediaPlayerEntity
    media_player.MediaPlayerEntityFeature = MediaPlayerEntityFeature
    media_player.MediaPlayerState = MediaPlayerState
    sys.modules["homeassistant.components.media_player"] = media_player

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda f: f
    sys.modules["homeassistant.core"] = core

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = Exception
    sys.modules["homeassistant.exceptions"] = exceptions

    helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers

    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = str
    sys.modules["homeassistant.helpers.config_validation"] = config_validation
    helpers.config_validation = config_validation

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = object
    entity_platform.async_get_current_platform = MagicMock()
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )

    class CoordinatorEntity:  # noqa: D101
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self) -> bool:
            return True

    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.UpdateFailed = Exception
    update_coordinator.DataUpdateCoordinator = object
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    config_entries.ConfigFlow = object
    config_entries.ConfigFlowResult = object
    config_entries.OptionsFlow = object
    sys.modules["homeassistant.config_entries"] = config_entries

    # Coordinator module imports these; keep stubs ready for broader loads.
    debounce = types.ModuleType("homeassistant.helpers.debounce")
    debounce.Debouncer = MagicMock
    sys.modules["homeassistant.helpers.debounce"] = debounce

    # voluptuous is an HA dependency; provide a minimal stub if missing.
    if "voluptuous" not in sys.modules:
        try:
            import voluptuous  # noqa: F401
        except ImportError:
            vol = types.ModuleType("voluptuous")

            class _Schema:  # noqa: D101
                def __init__(self, *args, **kwargs):
                    pass

                def __call__(self, value):
                    return value

            def _optional(key):
                return key

            def _in(options):
                return options

            vol.Schema = _Schema
            vol.Optional = _optional
            vol.Required = _optional
            vol.In = _in
            sys.modules["voluptuous"] = vol


def load_media_player_helpers():
    """Import media_player helpers with Home Assistant stubs."""
    _ensure_homeassistant_stubs()
    adapter = load_adapter_module()

    # Ensure package parents exist for relative imports.
    _ensure_pkg("custom_components", ROOT / "custom_components")
    _ensure_pkg("custom_components.binary_moip", COMPONENTS)
    _load_ir_codes_package()

    # media_player imports coordinator; stub it to avoid a full HA stack.
    coordinator_name = "custom_components.binary_moip.coordinator"
    if coordinator_name not in sys.modules:
        coordinator = types.ModuleType(coordinator_name)
        coordinator.BinaryMoIPConfigEntry = object
        coordinator.BinaryMoIPDataUpdateCoordinator = object
        sys.modules[coordinator_name] = coordinator

    media_player = _load_module("media_player", COMPONENTS / "media_player.py")
    media_player.MoIPReceiver = adapter.MoIPReceiver
    return media_player


def _ensure_pkg(name: str, path: Path) -> None:
    if name in sys.modules and hasattr(sys.modules[name], "__path__"):
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


def _load_ir_codes_package():
    """Load ir_codes package modules for media_player imports."""
    ir_dir = COMPONENTS / "ir_codes"
    _ensure_pkg("custom_components.binary_moip.ir_codes", ir_dir)
    for name in ("pronto", "samsung", "lg"):
        full = f"custom_components.binary_moip.ir_codes.{name}"
        if full not in sys.modules:
            _load_module_path(full, ir_dir / f"{name}.py")
    init_name = "custom_components.binary_moip.ir_codes"
    # Replace namespace stub with real package init if needed.
    init_path = ir_dir / "__init__.py"
    if not getattr(sys.modules.get(init_name), "resolve_pronto", None):
        _load_module_path(init_name, init_path)


def _load_module_path(full_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(full_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module
