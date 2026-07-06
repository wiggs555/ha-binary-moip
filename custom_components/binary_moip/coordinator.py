"""DataUpdateCoordinator for the Binary MoIP integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from binary_moip.exceptions import AuthError, CommandError, ConnectionError

from .adapter import MoIPAdapter, MoIPReceiver, MoIPState
from .const import (
    API_MODE_REST,
    CONF_API_MODE,
    CONF_CONTROL_PORT,
    CONF_HOST,
    CONF_HTTPS_PORT,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_CONTROL_PORT,
    DEFAULT_HTTPS_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    FALLBACK_SCAN_INTERVAL,
    WS_BACKOFF_MAX,
    WS_BACKOFF_START,
    WS_REFRESH_COOLDOWN,
)

_LOGGER = logging.getLogger(__name__)

type BinaryMoIPConfigEntry = ConfigEntry[BinaryMoIPDataUpdateCoordinator]


class BinaryMoIPDataUpdateCoordinator(DataUpdateCoordinator[MoIPState]):
    """Coordinate MoIP state with push updates and polling fallback."""

    config_entry: BinaryMoIPConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BinaryMoIPConfigEntry,
        adapter: MoIPAdapter,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FALLBACK_SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=WS_REFRESH_COOLDOWN, immediate=True
            ),
        )
        self.adapter = adapter
        self.ws_connected = False
        self._push_task: asyncio.Task[None] | None = None

    @classmethod
    def from_entry(
        cls, hass: HomeAssistant, entry: BinaryMoIPConfigEntry
    ) -> BinaryMoIPDataUpdateCoordinator:
        """Build a coordinator from a config entry."""
        adapter = MoIPAdapter(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_API_MODE],
            https_port=entry.data.get(CONF_HTTPS_PORT, DEFAULT_HTTPS_PORT),
            control_port=entry.data.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT),
            verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        return cls(hass, entry, adapter)

    async def async_setup(self) -> None:
        """Connect adapter and start push listeners."""
        await self.adapter.async_connect()
        if self.adapter.api_mode == API_MODE_REST:
            self._push_task = self.config_entry.async_create_background_task(
                self.hass, self._ws_listen(), name=f"{DOMAIN}_ws"
            )
        else:
            self.adapter.set_unsolicited_callback(
                lambda: self.hass.loop.call_soon_threadsafe(
                    self._schedule_refresh
                )
            )

    def _schedule_refresh(self) -> None:
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self.async_request_refresh())
        )

    async def async_shutdown(self) -> None:
        """Close adapter connections."""
        if self._push_task is not None:
            self._push_task.cancel()
            with asyncio.suppress(asyncio.CancelledError):
                await self._push_task
            self._push_task = None
        await self.adapter.async_close()

    async def _async_update_data(self) -> MoIPState:
        try:
            return await self.adapter.async_discover()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (ConnectionError, CommandError, OSError) as err:
            raise UpdateFailed(f"Error communicating with MoIP controller: {err}") from err

    async def async_select_source(
        self, receiver_id: int, transmitter_id: int | None
    ) -> None:
        """Switch a receiver to a transmitter."""
        try:
            await self.adapter.async_select_source(receiver_id, transmitter_id)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (ConnectionError, CommandError) as err:
            raise UpdateFailed(str(err)) from err
        await self.async_request_refresh()

    async def async_set_tv_power(self, receiver_id: int, on: bool) -> None:
        """Send HDMI CEC power on/off to the TV connected to a receiver."""
        if self.data is None:
            raise UpdateFailed("MoIP controller state is unavailable")
        receiver = self.data.receivers.get(receiver_id)
        if receiver is None:
            raise UpdateFailed(f"Unknown receiver: {receiver_id}")
        try:
            await self.adapter.async_set_tv_power(receiver, on)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (ConnectionError, CommandError) as err:
            raise UpdateFailed(str(err)) from err

    async def _ws_listen(self) -> None:
        """Maintain REST websocket, refreshing on MoIP changes."""
        backoff = WS_BACKOFF_START
        while True:
            try:
                await self._ws_consume()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("MoIP websocket error: %s", err)
            finally:
                self.ws_connected = False

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, WS_BACKOFF_MAX)

    async def _ws_consume(self) -> None:
        """Read websocket events until disconnect."""
        self.ws_connected = True
        _LOGGER.debug("MoIP websocket connected")
        async for event in self.adapter.async_subscribe_events():
            raw = event.raw
            if isinstance(raw, dict):
                changes = raw.get("changes", [])
                if any(
                    c.get("kind") in ("added", "removed", "modified")
                    and "/moip/" in (c.get("url") or "")
                    for c in changes
                ):
                    await self.async_request_refresh()
            elif isinstance(raw, str) and "/moip/" in raw:
                await self.async_request_refresh()
