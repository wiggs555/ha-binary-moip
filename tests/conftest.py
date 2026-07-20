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

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = object
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


def load_media_player_helpers():
    """Import media_player helpers with Home Assistant stubs."""
    _ensure_homeassistant_stubs()
    adapter = load_adapter_module()

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
