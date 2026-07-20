"""The Binary MoIP integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, MANUFACTURER, OPT_ENABLED, OPT_RECEIVERS, OPT_TRANSMITTERS, PLATFORMS
from .coordinator import BinaryMoIPConfigEntry, BinaryMoIPDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _enabled_ids(options: dict, key: str, known_ids: set[str]) -> set[str]:
    """Return enabled entity ids for receivers or transmitters."""
    configured = options.get(key, {})
    enabled: set[str] = set()
    for entity_id in known_ids:
        opts = configured.get(entity_id, {})
        if opts.get(OPT_ENABLED, True):
            enabled.add(entity_id)
    # Include explicitly configured ids even if not currently discovered.
    for entity_id, opts in configured.items():
        if opts.get(OPT_ENABLED, True):
            enabled.add(str(entity_id))
    return enabled


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

    if coordinator.data is not None:
        coordinator.enabled_receiver_ids = _enabled_ids(
            entry.options,
            OPT_RECEIVERS,
            {str(i) for i in coordinator.data.receivers},
        )
        coordinator.enabled_transmitter_ids = _enabled_ids(
            entry.options,
            OPT_TRANSMITTERS,
            {str(i) for i in coordinator.data.transmitters},
        )

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
    refresh is enough unless the enabled entity set changed.
    """
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None or coordinator.data is None:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    new_rx = _enabled_ids(
        entry.options,
        OPT_RECEIVERS,
        {str(i) for i in coordinator.data.receivers},
    )
    new_tx = _enabled_ids(
        entry.options,
        OPT_TRANSMITTERS,
        {str(i) for i in coordinator.data.transmitters},
    )
    if (
        new_rx != getattr(coordinator, "enabled_receiver_ids", new_rx)
        or new_tx != getattr(coordinator, "enabled_transmitter_ids", new_tx)
    ):
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
