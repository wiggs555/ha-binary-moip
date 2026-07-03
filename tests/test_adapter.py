"""Tests for Binary MoIP adapter helpers and probe logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import load_adapter_module

adapter_mod = load_adapter_module()

MoIPReceiver = adapter_mod.MoIPReceiver
MoIPState = adapter_mod.MoIPState
MoIPTransmitter = adapter_mod.MoIPTransmitter
_normalize_state = adapter_mod._normalize_state
build_rest_base_url = adapter_mod.build_rest_base_url
probe_api_mode = adapter_mod.probe_api_mode

API_MODE_REST = "rest"
API_MODE_TCP = "tcp"


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
