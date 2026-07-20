"""Tests for Binary MoIP adapter helpers and probe logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binary_moip.control.protocol import CecMode, IrType

from tests.conftest import load_adapter_module

adapter_mod = load_adapter_module()

MoIPAdapter = adapter_mod.MoIPAdapter
MoIPReceiver = adapter_mod.MoIPReceiver
MoIPState = adapter_mod.MoIPState
MoIPTransmitter = adapter_mod.MoIPTransmitter
_normalize_state = adapter_mod._normalize_state
_extract_unit_ids = adapter_mod._extract_unit_ids
build_rest_base_url = adapter_mod.build_rest_base_url
probe_api_mode = adapter_mod.probe_api_mode

API_MODE_REST = "rest"
API_MODE_TCP = "tcp"


def test_extract_unit_ids_dict_items() -> None:
    assert _extract_unit_ids({"items": [1, 2, 3]}) == [1, 2, 3]


def test_extract_unit_ids_list_of_dicts() -> None:
    assert _extract_unit_ids([{"id": 10}, {"id": 20}]) == [10, 20]


def test_extract_unit_ids_empty() -> None:
    assert _extract_unit_ids(None) == []
    assert _extract_unit_ids({}) == []


def test_build_rest_base_url_default_port() -> None:
    assert build_rest_base_url("192.168.1.10", 443) == "https://192.168.1.10"


def test_build_rest_base_url_custom_port() -> None:
    assert build_rest_base_url("192.168.1.10", 8443) == "https://192.168.1.10:8443"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("online", "online"),
        ("Connected", "online"),
        ("streaming", "online"),
        ("offline", "offline"),
        ("Disconnected", "offline"),
        ("idle", "idle"),
        (None, None),
    ],
)
def test_normalize_state(raw: str | None, expected: str | None) -> None:
    assert _normalize_state(raw) == expected


@pytest.mark.asyncio
async def test_probe_api_mode_rest_success() -> None:
    mock_rest = MagicMock()
    mock_rest.moip.list_unit = AsyncMock(return_value={"items": []})
    mock_rest.aclose = AsyncMock()

    with patch.object(adapter_mod, "AsyncConfigClient", return_value=mock_rest):
        result = await probe_api_mode(
            "192.168.1.10",
            "admin",
            "secret",
            https_port=443,
            control_port=23,
            verify_ssl=False,
        )

    assert result == API_MODE_REST
    mock_rest.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_api_mode_tcp_fallback() -> None:
    mock_rest = MagicMock()
    mock_rest.moip.list_unit = AsyncMock(side_effect=OSError("connection refused"))
    mock_rest.aclose = AsyncMock()

    mock_tcp = MagicMock()
    mock_tcp.connect = AsyncMock()
    mock_tcp.get_devices = AsyncMock(return_value=MagicMock(tx=2, rx=3))
    mock_tcp.close = AsyncMock()

    with (
        patch.object(adapter_mod, "AsyncConfigClient", return_value=mock_rest),
        patch.object(adapter_mod, "AsyncControlClient", return_value=mock_tcp),
    ):
        result = await probe_api_mode(
            "192.168.1.10",
            "admin",
            "secret",
            https_port=443,
            control_port=23,
            verify_ssl=False,
        )

    assert result == API_MODE_TCP
    mock_tcp.connect.assert_awaited_once()
    mock_tcp.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_api_mode_both_fail() -> None:
    mock_rest = MagicMock()
    mock_rest.moip.list_unit = AsyncMock(side_effect=OSError("connection refused"))
    mock_rest.aclose = AsyncMock()

    mock_tcp = MagicMock()
    mock_tcp.connect = AsyncMock(side_effect=OSError("connection refused"))
    mock_tcp.close = AsyncMock()

    with (
        patch.object(adapter_mod, "AsyncConfigClient", return_value=mock_rest),
        patch.object(adapter_mod, "AsyncControlClient", return_value=mock_tcp),
    ):
        result = await probe_api_mode(
            "192.168.1.10",
            "admin",
            "secret",
            https_port=443,
            control_port=23,
            verify_ssl=False,
        )

    assert result is None


def test_moip_state_dataclasses() -> None:
    state = MoIPState(
        receivers={
            1: MoIPReceiver(id=1, name="Living Room", paired_tx_id=2, state="online"),
        },
        transmitters={
            2: MoIPTransmitter(id=2, name="Apple TV", state="online", input_type="hdmi"),
        },
        api_mode=API_MODE_TCP,
    )
    assert state.receivers[1].paired_tx_id == 2
    assert state.transmitters[2].input_type == "hdmi"
    assert state.api_mode == API_MODE_TCP


@pytest.mark.asyncio
async def test_async_set_tv_power_tcp_on() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_TCP, control_port=23
    )
    adapter._tcp = MagicMock()
    adapter._tcp.set_cec = AsyncMock()

    receiver = MoIPReceiver(id=2, name="Living Room", index=2)
    await adapter.async_set_tv_power(receiver, True)

    adapter._tcp.set_cec.assert_awaited_once_with(2, CecMode.ON)


@pytest.mark.asyncio
async def test_async_set_tv_power_tcp_off() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_TCP, control_port=23
    )
    adapter._tcp = MagicMock()
    adapter._tcp.set_cec = AsyncMock()

    receiver = MoIPReceiver(id=3, name="Bedroom")
    await adapter.async_set_tv_power(receiver, False)

    adapter._tcp.set_cec.assert_awaited_once_with(3, CecMode.OFF)


@pytest.mark.asyncio
async def test_async_set_tv_power_rest_on() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()
    adapter._rest.moip.post_moip_video_rx_id = AsyncMock()

    receiver = MoIPReceiver(id=1050, name="Living Room", video_rx_id=1052)
    await adapter.async_set_tv_power(receiver, True)

    adapter._rest.moip.post_moip_video_rx_id.assert_awaited_once_with(
        1052,
        json={"format": "tv_on", "message": None},
    )


@pytest.mark.asyncio
async def test_async_set_tv_power_rest_off() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()
    adapter._rest.moip.post_moip_video_rx_id = AsyncMock()

    receiver = MoIPReceiver(id=1050, name="Living Room", video_rx_id=1052)
    await adapter.async_set_tv_power(receiver, False)

    adapter._rest.moip.post_moip_video_rx_id.assert_awaited_once_with(
        1052,
        json={"format": "tv_off", "message": None},
    )


@pytest.mark.asyncio
async def test_async_set_tv_power_rest_missing_video_rx() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()

    receiver = MoIPReceiver(id=1050, name="Living Room")
    with pytest.raises(adapter_mod.CommandError, match="no associated video_rx"):
        await adapter.async_set_tv_power(receiver, True)


@pytest.mark.asyncio
async def test_async_send_ir_tcp() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_TCP, control_port=23
    )
    adapter._tcp = MagicMock()
    adapter._tcp.send_ir = AsyncMock()

    receiver = MoIPReceiver(id=2, name="Living Room", index=2)
    await adapter.async_send_ir(receiver, " 0000 006C 0000 0000 ")

    adapter._tcp.send_ir.assert_awaited_once_with(
        IrType.RX, 2, "0000 006C 0000 0000"
    )


@pytest.mark.asyncio
async def test_async_send_ir_tcp_falls_back_to_id() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_TCP, control_port=23
    )
    adapter._tcp = MagicMock()
    adapter._tcp.send_ir = AsyncMock()

    receiver = MoIPReceiver(id=3, name="Bedroom")
    await adapter.async_send_ir(receiver, "0000 006C")

    adapter._tcp.send_ir.assert_awaited_once_with(IrType.RX, 3, "0000 006C")


@pytest.mark.asyncio
async def test_async_send_ir_rest() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()
    adapter._rest.moip.post_moip_ir_rx_id = AsyncMock()

    receiver = MoIPReceiver(id=1050, name="Living Room", ir_rx_id=1055)
    await adapter.async_send_ir(receiver, "0000 006C 0000 0000")

    adapter._rest.moip.post_moip_ir_rx_id.assert_awaited_once_with(
        1055,
        json={"format": "pronto", "message": "0000 006C 0000 0000"},
    )


@pytest.mark.asyncio
async def test_async_send_ir_rest_missing_ir_rx() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()

    receiver = MoIPReceiver(id=1050, name="Living Room")
    with pytest.raises(adapter_mod.CommandError, match="no associated ir_rx"):
        await adapter.async_send_ir(receiver, "0000 006C")


@pytest.mark.asyncio
async def test_async_send_ir_empty_code() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_TCP, control_port=23
    )
    adapter._tcp = MagicMock()

    receiver = MoIPReceiver(id=1, name="Living Room", index=1)
    with pytest.raises(adapter_mod.CommandError, match="empty IR Pronto code"):
        await adapter.async_send_ir(receiver, "   ")


@pytest.mark.asyncio
async def test_discover_rest_reads_ir_rx_id() -> None:
    adapter = MoIPAdapter(
        "192.168.1.10", "admin", "secret", API_MODE_REST, verify_ssl=False
    )
    adapter._rest = MagicMock()
    adapter._rest.moip.list_unit = AsyncMock(return_value={"items": [100]})
    adapter._rest.moip.get_moip_unit_id = AsyncMock(
        return_value={
            "id": 100,
            "settings": {"name": "Unit 1"},
            "status": {"unit_state": "online"},
            "associations": {"group": {"rx": [1050], "tx": []}},
        }
    )
    adapter._rest.moip.get_moip_group_rx_id = AsyncMock(
        return_value={
            "id": 1050,
            "settings": {"name": "Living Room", "index": 1},
            "status": {"state": "online"},
            "associations": {
                "unit": 100,
                "paired_tx": None,
                "video_rx": 1052,
                "ir_rx": 1055,
            },
        }
    )

    state = await adapter.async_discover()

    assert state.receivers[1050].ir_rx_id == 1055
    assert state.receivers[1050].video_rx_id == 1052
