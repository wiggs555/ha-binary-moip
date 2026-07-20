"""The Binary MoIP integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, MANUFACTURER, PLATFORMS
from .coordinator import BinaryMoIPConfigEntry, BinaryMoIPDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Binary MoIP integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BinaryMoIPConfigEntry) -> bool:
    """Set up Binary MoIP from a config entry."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
    )

    coordinator = BinaryMoIPDataUpdateCoordinator.from_entry(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Apply options without tearing down the integration when possible.

    Saving IR Pronto codes used to call ``async_reload``, which hung while
    awaiting the REST websocket task and left the entry in failed-unload.
    IR codes and labels are read live from ``entry.options``, so a coordinator
    refresh is enough. Fall back to a full reload only when runtime data is
    missing (e.g. after a prior failed unload).
    """
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: BinaryMoIPConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator = getattr(entry, "runtime_data", None)
    if unload_ok and coordinator is not None:
        try:
            await coordinator.async_shutdown()
        except Exception:  # noqa: BLE001
            # Never fail unload because cleanup raised; entry would get stuck.
            _LOGGER.exception("Error shutting down Binary MoIP coordinator")
    return unload_ok
