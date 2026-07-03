"""Sensor platform for Binary MoIP receiver and transmitter status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .adapter import MoIPReceiver, MoIPTransmitter
from .const import (
    ATTR_API_MODE,
    ATTR_INDEX,
    ATTR_INPUT_TYPE,
    ATTR_PAIRED_TRANSMITTER,
    ATTR_PAIRED_TRANSMITTER_NAME,
    ATTR_UNIT_NAME,
    DOMAIN,
    MANUFACTURER,
    OPT_ENABLED,
    OPT_LABEL,
    OPT_RECEIVERS,
    OPT_TRANSMITTERS,
)
from .coordinator import BinaryMoIPConfigEntry, BinaryMoIPDataUpdateCoordinator


def _receiver_enabled(entry: BinaryMoIPConfigEntry, receiver_id: int) -> bool:
    opts = entry.options.get(OPT_RECEIVERS, {}).get(str(receiver_id), {})
    return opts.get(OPT_ENABLED, True)


def _transmitter_enabled(entry: BinaryMoIPConfigEntry, transmitter_id: int) -> bool:
    opts = entry.options.get(OPT_TRANSMITTERS, {}).get(str(transmitter_id), {})
    return opts.get(OPT_ENABLED, True)


def _receiver_name(entry: BinaryMoIPConfigEntry, receiver: MoIPReceiver) -> str:
    opts = entry.options.get(OPT_RECEIVERS, {}).get(str(receiver.id), {})
    return opts.get(OPT_LABEL, receiver.name)


def _transmitter_name(
    entry: BinaryMoIPConfigEntry, transmitter: MoIPTransmitter
) -> str:
    opts = entry.options.get(OPT_TRANSMITTERS, {}).get(str(transmitter.id), {})
    return opts.get(OPT_LABEL, transmitter.name)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BinaryMoIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up status sensor entities."""
    coordinator = entry.runtime_data
    if coordinator.data is None:
        return

    entities: list[SensorEntity] = []
    for receiver in coordinator.data.receivers.values():
        if _receiver_enabled(entry, receiver.id):
            entities.append(BinaryMoIPReceiverStatusSensor(coordinator, entry, receiver))
    for transmitter in coordinator.data.transmitters.values():
        if _transmitter_enabled(entry, transmitter.id):
            entities.append(
                BinaryMoIPTransmitterStatusSensor(coordinator, entry, transmitter)
            )
    async_add_entities(entities)


class BinaryMoIPReceiverStatusSensor(
    CoordinatorEntity[BinaryMoIPDataUpdateCoordinator], SensorEntity
):
    """Sensor reporting receiver online status and routing."""

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
        self._attr_unique_id = f"{entry.entry_id}_rx_{receiver.id}_status"
        self._attr_name = f"{_receiver_name(entry, receiver)} status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_rx_{receiver.id}")},
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
    def native_value(self) -> str | None:
        receiver = self._receiver
        if receiver is None:
            return None
        return receiver.state or "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        receiver = self._receiver
        if receiver is None or self.coordinator.data is None:
            return None
        attrs: dict[str, Any] = {
            ATTR_API_MODE: self.coordinator.data.api_mode,
            ATTR_INDEX: receiver.id,
        }
        if receiver.paired_tx_id is not None:
            attrs[ATTR_PAIRED_TRANSMITTER] = receiver.paired_tx_id
            tx = self.coordinator.data.transmitters.get(receiver.paired_tx_id)
            if tx is not None:
                attrs[ATTR_PAIRED_TRANSMITTER_NAME] = _transmitter_name(self._entry, tx)
        if receiver.unit_name:
            attrs[ATTR_UNIT_NAME] = receiver.unit_name
        return attrs


class BinaryMoIPTransmitterStatusSensor(
    CoordinatorEntity[BinaryMoIPDataUpdateCoordinator], SensorEntity
):
    """Sensor reporting transmitter online status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BinaryMoIPDataUpdateCoordinator,
        entry: BinaryMoIPConfigEntry,
        transmitter: MoIPTransmitter,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._transmitter_id = transmitter.id
        self._attr_unique_id = f"{entry.entry_id}_tx_{transmitter.id}_status"
        self._attr_name = f"{_transmitter_name(entry, transmitter)} status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_tx_{transmitter.id}")},
            name=_transmitter_name(entry, transmitter),
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _transmitter(self) -> MoIPTransmitter | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.transmitters.get(self._transmitter_id)

    @property
    def available(self) -> bool:
        return super().available and self._transmitter is not None

    @property
    def native_value(self) -> str | None:
        transmitter = self._transmitter
        if transmitter is None:
            return None
        return transmitter.state or "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        transmitter = self._transmitter
        if transmitter is None or self.coordinator.data is None:
            return None
        attrs: dict[str, Any] = {
            ATTR_API_MODE: self.coordinator.data.api_mode,
            ATTR_INDEX: transmitter.id,
        }
        if transmitter.input_type:
            attrs[ATTR_INPUT_TYPE] = transmitter.input_type
        if transmitter.unit_name:
            attrs[ATTR_UNIT_NAME] = transmitter.unit_name
        return attrs
