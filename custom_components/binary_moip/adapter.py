"""Adapter wrapping the binary-moip driver for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from binary_moip import AsyncConfigClient, AsyncControlClient
from binary_moip.control.protocol import UnsolicitedReceivers
from binary_moip.exceptions import ApiError, AuthError, CommandError, ConnectionError

from .const import API_MODE_REST, API_MODE_TCP

_LOGGER = logging.getLogger(__name__)

ApiMode = Literal["rest", "tcp"]


@dataclass
class MoIPReceiver:
    """Normalized receiver (zone) state."""

    id: int
    name: str
    paired_tx_id: int | None = None
    state: str | None = None
    unit_id: int | None = None
    unit_name: str | None = None


@dataclass
class MoIPTransmitter:
    """Normalized transmitter (source) state."""

    id: int
    name: str
    state: str | None = None
    unit_id: int | None = None
    unit_name: str | None = None
    input_type: str | None = None


@dataclass
class MoIPState:
    """Full controller topology and routing state."""

    receivers: dict[int, MoIPReceiver] = field(default_factory=dict)
    transmitters: dict[int, MoIPTransmitter] = field(default_factory=dict)
    api_mode: ApiMode = API_MODE_REST


def _opt_int(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_state(raw: str | None) -> str | None:
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in ("online", "connected", "active", "streaming"):
        return "online"
    if lowered in ("offline", "disconnected", "inactive"):
        return "offline"
    return raw


def build_rest_base_url(host: str, https_port: int) -> str:
    """Build the REST base URL for the controller."""
    if https_port == 443:
        return f"https://{host}"
    return f"https://{host}:{https_port}"


async def probe_api_mode(
    host: str,
    username: str,
    password: str,
    *,
    https_port: int,
    control_port: int,
    verify_ssl: bool,
) -> ApiMode | None:
    """Try REST first, then TCP. Return detected mode or None."""
    base_url = build_rest_base_url(host, https_port)
    rest_client = AsyncConfigClient(
        base_url, username, password, verify_ssl=verify_ssl
    )
    try:
        await rest_client.moip.list_unit()
        return API_MODE_REST
    except AuthError:
        raise
    except (ApiError, ConnectionError, OSError) as err:
        _LOGGER.debug("REST probe failed: %s", err)
    finally:
        await rest_client.aclose()

    tcp_client = AsyncControlClient(
        host, username, password, port=control_port
    )
    try:
        await tcp_client.connect()
        await tcp_client.get_devices()
        return API_MODE_TCP
    except AuthError:
        raise
    except (CommandError, ConnectionError, OSError) as err:
        _LOGGER.debug("TCP probe failed: %s", err)
        return None
    finally:
        await tcp_client.close()


class MoIPAdapter:
    """Unified async interface to Binary MoIP controllers."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        api_mode: ApiMode,
        *,
        https_port: int = 443,
        control_port: int = 23,
        verify_ssl: bool = False,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.api_mode = api_mode
        self.https_port = https_port
        self.control_port = control_port
        self.verify_ssl = verify_ssl

        self._rest: AsyncConfigClient | None = None
        self._tcp: AsyncControlClient | None = None
        self._unsolicited_callback: Callable[[], None] | None = None

    async def async_connect(self) -> None:
        """Open the client for the configured API mode."""
        if self.api_mode == API_MODE_REST:
            self._rest = AsyncConfigClient(
                build_rest_base_url(self.host, self.https_port),
                self.username,
                self.password,
                verify_ssl=self.verify_ssl,
            )
            return

        self._tcp = AsyncControlClient(
            self.host,
            self.username,
            self.password,
            port=self.control_port,
        )
        await self._tcp.connect()
        if self._unsolicited_callback is not None:
            self._register_tcp_unsolicited()

    async def async_close(self) -> None:
        """Close all open clients."""
        if self._rest is not None:
            await self._rest.aclose()
            self._rest = None
        if self._tcp is not None:
            await self._tcp.close()
            self._tcp = None

    def set_unsolicited_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for TCP routing push updates."""
        self._unsolicited_callback = callback
        if self._tcp is not None:
            self._register_tcp_unsolicited()

    def _register_tcp_unsolicited(self) -> None:
        if self._tcp is None or self._unsolicited_callback is None:
            return

        def _handle(message: object) -> None:
            if isinstance(message, UnsolicitedReceivers):
                self._unsolicited_callback()

        self._tcp.on_unsolicited(_handle)

    async def async_discover(self) -> MoIPState:
        """Fetch current topology and routing."""
        if self.api_mode == API_MODE_REST:
            return await self._discover_rest()
        return await self._discover_tcp()

    async def _discover_rest(self) -> MoIPState:
        assert self._rest is not None
        state = MoIPState(api_mode=API_MODE_REST)
        units: dict[int, dict[str, Any]] = {}

        unit_list = await self._rest.moip.list_unit()
        unit_ids = [int(i) for i in (unit_list or {}).get("items", [])]

        unit_objs = await asyncio.gather(
            *(self._rest.moip.get_unit_id(uid) for uid in unit_ids)
        )

        group_rx_ids: list[int] = []
        group_tx_ids: list[int] = []
        for raw in unit_objs:
            uid = int(raw["id"])
            settings = raw.get("settings") or {}
            status = raw.get("status") or {}
            units[uid] = {
                "name": settings.get("name") or f"Unit {uid}",
                "state": status.get("unit_state"),
            }
            assoc = (raw.get("associations") or {}).get("group") or {}
            group_rx_ids.extend(int(i) for i in assoc.get("rx", []))
            group_tx_ids.extend(int(i) for i in assoc.get("tx", []))

        rx_objs, tx_objs = await asyncio.gather(
            asyncio.gather(
                *(self._rest.moip.get_group_rx_id(rid) for rid in group_rx_ids)
            ),
            asyncio.gather(
                *(self._rest.moip.get_group_tx_id(tid) for tid in group_tx_ids)
            ),
        )

        audio_tx_ids: list[int | None] = []
        for raw in tx_objs:
            assoc = raw.get("associations") or {}
            audio_tx_ids.append(_opt_int(assoc.get("audio_tx")))

        audio_tx_objs = await asyncio.gather(
            *(
                self._rest.moip.get_audio_tx_id(atx_id)
                if atx_id is not None
                else _async_none()
                for atx_id in audio_tx_ids
            )
        )

        for raw, atx_raw in zip(tx_objs, audio_tx_objs, strict=True):
            settings = raw.get("settings") or {}
            assoc = raw.get("associations") or {}
            status = raw.get("status") or {}
            unit_id = _opt_int(assoc.get("unit"))
            tx_id = int(raw["id"])
            input_type = None
            if atx_raw:
                src = (atx_raw.get("settings") or {}).get("source")
                if isinstance(src, list):
                    input_type = next((p for p in src if p), None)
                elif src:
                    input_type = str(src)

            state.transmitters[tx_id] = MoIPTransmitter(
                id=tx_id,
                name=settings.get("name") or f"Source {tx_id}",
                state=_normalize_state(status.get("state")),
                unit_id=unit_id,
                unit_name=units[unit_id]["name"] if unit_id in units else None,
                input_type=input_type,
            )

        for raw in rx_objs:
            settings = raw.get("settings") or {}
            assoc = raw.get("associations") or {}
            status = raw.get("status") or {}
            unit_id = _opt_int(assoc.get("unit"))
            rx_id = int(raw["id"])
            state.receivers[rx_id] = MoIPReceiver(
                id=rx_id,
                name=settings.get("name") or f"Receiver {rx_id}",
                paired_tx_id=_opt_int(assoc.get("paired_tx")),
                state=_normalize_state(status.get("state")),
                unit_id=unit_id,
                unit_name=units[unit_id]["name"] if unit_id in units else None,
            )

        return state

    async def _discover_tcp(self) -> MoIPState:
        assert self._tcp is not None
        state = MoIPState(api_mode=API_MODE_TCP)

        devices, routings, rx_names, tx_names = await asyncio.gather(
            self._tcp.get_devices(),
            self._tcp.get_receivers(),
            self._tcp.get_names(tx=False),
            self._tcp.get_names(tx=True),
        )

        routing_map = {r.rx: r.tx for r in routings if r.tx != 0}

        rx_name_map = {n.index: n.name for n in rx_names}
        tx_name_map = {n.index: n.name for n in tx_names}

        for rx_index in range(1, devices.rx + 1):
            paired = routing_map.get(rx_index)
            state.receivers[rx_index] = MoIPReceiver(
                id=rx_index,
                name=rx_name_map.get(rx_index, f"Receiver {rx_index}"),
                paired_tx_id=paired if paired else None,
                state="online" if paired else "offline",
            )

        for tx_index in range(1, devices.tx + 1):
            state.transmitters[tx_index] = MoIPTransmitter(
                id=tx_index,
                name=tx_name_map.get(tx_index, f"Source {tx_index}"),
                state="online",
            )

        return state

    async def async_select_source(
        self, receiver_id: int, transmitter_id: int | None
    ) -> None:
        """Route a transmitter to a receiver, or disconnect when None."""
        if self.api_mode == API_MODE_REST:
            assert self._rest is not None
            await self._rest.moip.put_group_rx_id(
                receiver_id,
                json={"associations": {"paired_tx": transmitter_id}},
            )
            return

        assert self._tcp is not None
        tx = transmitter_id if transmitter_id is not None else 0
        await self._tcp.switch(tx, receiver_id)

    async def async_subscribe_events(self) -> AsyncIterator[object]:
        """Yield change events for REST mode (websocket)."""
        assert self._rest is not None
        async for event in self._rest.events.subscribe_websocket():
            yield event


async def _async_none() -> None:
    return None
