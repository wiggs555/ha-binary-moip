"""Media player platform for Binary MoIP receivers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .adapter import MoIPReceiver, MoIPTransmitter
from .const import (
    API_MODE_TCP,
    ATTR_CEC_INDEX,
    ATTR_CEC_SUPPORTED,
    ATTR_VIDEO_RX_ID,
    DOMAIN,
    MANUFACTURER,
    OPT_ENABLED,
    OPT_LABEL,
    OPT_RECEIVERS,
    OPT_TRANSMITTERS,
    SOURCE_OFF,
)
from .coordinator import BinaryMoIPConfigEntry, BinaryMoIPDataUpdateCoordinator

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


def _receiver_enabled(entry: BinaryMoIPConfigEntry, receiver_id: int) -> bool:
    opts = entry.options.get(OPT_RECEIVERS, {}).get(str(receiver_id), {})
    return opts.get(OPT_ENABLED, True)


def _transmitter_enabled(entry: BinaryMoIPConfigEntry, transmitter_id: int) -> bool:
    opts = entry.options.get(OPT_TRANSMITTERS, {}).get(str(transmitter_id), {})
    return opts.get(OPT_ENABLED, True)


def _receiver_name(
    entry: BinaryMoIPConfigEntry, receiver: MoIPReceiver
) -> str:
    opts = entry.options.get(OPT_RECEIVERS, {}).get(str(receiver.id), {})
    return opts.get(OPT_LABEL, receiver.name)


def _transmitter_name(
    entry: BinaryMoIPConfigEntry, transmitter: MoIPTransmitter
) -> str:
    opts = entry.options.get(OPT_TRANSMITTERS, {}).get(str(transmitter.id), {})
    return opts.get(OPT_LABEL, transmitter.name)


def _enabled_transmitters(
    coordinator: BinaryMoIPDataUpdateCoordinator,
    entry: BinaryMoIPConfigEntry,
) -> dict[int, MoIPTransmitter]:
    if coordinator.data is None:
        return {}
    return {
        tx_id: tx
        for tx_id, tx in coordinator.data.transmitters.items()
        if _transmitter_enabled(entry, tx_id)
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BinaryMoIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media_player entities for enabled receivers."""
    coordinator = entry.runtime_data
    if coordinator.data is None:
        return

    entities = [
        BinaryMoIPReceiverMediaPlayer(coordinator, entry, receiver)
        for receiver in coordinator.data.receivers.values()
        if _receiver_enabled(entry, receiver.id)
    ]
    async_add_entities(entities)


class BinaryMoIPReceiverMediaPlayer(
    CoordinatorEntity[BinaryMoIPDataUpdateCoordinator], MediaPlayerEntity
):
    """Media player representing a Binary MoIP receiver."""

    _attr_supported_features = SUPPORTED_FEATURES
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BinaryMoIPDataUpdateCoordinator,
        entry: BinaryMoIPConfigEntry,
        receiver: MoIPReceiver,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._receiver_id = receiver.id
        self._attr_unique_id = f"{entry.entry_id}_rx_{receiver.id}"
        self._attr_name = _receiver_name(entry, receiver)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_rx_{receiver.id}")},
            name=_receiver_name(entry, receiver),
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _receiver(self) -> MoIPReceiver | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.receivers.get(self._receiver_id)

    @property
    def available(self) -> bool:
        return super().available and self._receiver is not None

    @property
    def state(self) -> MediaPlayerState | None:
        receiver = self._receiver
        if receiver is None:
            return None
        if receiver.paired_tx_id:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source_list(self) -> list[str] | None:
        transmitters = _enabled_transmitters(self.coordinator, self._entry)
        names = [_transmitter_name(self._entry, tx) for tx in transmitters.values()]
        return [SOURCE_OFF, *sorted(names)]

    @property
    def source(self) -> str | None:
        receiver = self._receiver
        if receiver is None or receiver.paired_tx_id is None:
            return SOURCE_OFF
        if self.coordinator.data is None:
            return None
        transmitter = self.coordinator.data.transmitters.get(receiver.paired_tx_id)
        if transmitter is None:
            return None
        return _transmitter_name(self._entry, transmitter)

    async def async_select_source(self, source: str) -> None:
        """Route the receiver to the selected transmitter."""
        if source == SOURCE_OFF:
            await self.coordinator.async_select_source(self._receiver_id, None)
            return

        transmitters = _enabled_transmitters(self.coordinator, self._entry)
        for tx_id, transmitter in transmitters.items():
            if _transmitter_name(self._entry, transmitter) == source:
                await self.coordinator.async_select_source(self._receiver_id, tx_id)
                return

        raise HomeAssistantError(f"Unknown source: {source}")

    async def async_turn_on(self) -> None:
        """Power on the TV connected to this receiver via HDMI CEC."""
        await self._async_set_tv_power(True)

    async def async_turn_off(self) -> None:
        """Power off the TV connected to this receiver via HDMI CEC."""
        await self._async_set_tv_power(False)

    async def _async_set_tv_power(self, on: bool) -> None:
        receiver = self._receiver
        if receiver is None:
            raise HomeAssistantError("Receiver is unavailable")
        if not _cec_supported(receiver, self.coordinator.data.api_mode):
            raise HomeAssistantError(
                "HDMI CEC is not available for this receiver"
            )
        try:
            await self.coordinator.async_set_tv_power(self._receiver_id, on)
        except UpdateFailed as err:
            raise HomeAssistantError(str(err)) from err

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        receiver = self._receiver
        if receiver is None or self.coordinator.data is None:
            return None
        attrs: dict[str, Any] = {
            "receiver_id": receiver.id,
            "api_mode": self.coordinator.data.api_mode,
        }
        if receiver.paired_tx_id is not None:
            attrs["paired_transmitter_id"] = receiver.paired_tx_id
            tx = self.coordinator.data.transmitters.get(receiver.paired_tx_id)
            if tx is not None:
                attrs["paired_transmitter_name"] = _transmitter_name(self._entry, tx)
        if receiver.unit_name:
            attrs["unit_name"] = receiver.unit_name
        attrs[ATTR_CEC_SUPPORTED] = _cec_supported(
            receiver, self.coordinator.data.api_mode
        )
        if receiver.video_rx_id is not None:
            attrs[ATTR_VIDEO_RX_ID] = receiver.video_rx_id
        cec_index = receiver.index or receiver.id
        if cec_index is not None:
            attrs[ATTR_CEC_INDEX] = cec_index
        return attrs


def _cec_supported(receiver: MoIPReceiver, api_mode: str) -> bool:
    """Return whether CEC power control is available for this receiver."""
    if api_mode == API_MODE_TCP:
        return True
    return receiver.video_rx_id is not None
