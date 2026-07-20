"""Unit tests for media player IR helpers (no Home Assistant import)."""

from __future__ import annotations

from types import SimpleNamespace

from tests.conftest import load_media_player_helpers

helpers = load_media_player_helpers()

DISPLAY_CONTROL_CEC = helpers.DISPLAY_CONTROL_CEC
DISPLAY_CONTROL_IR = helpers.DISPLAY_CONTROL_IR
OPT_DISPLAY_CONTROL = helpers.OPT_DISPLAY_CONTROL
OPT_IR_MUTE = helpers.OPT_IR_MUTE
OPT_IR_POWER_OFF = helpers.OPT_IR_POWER_OFF
OPT_IR_POWER_ON = helpers.OPT_IR_POWER_ON
OPT_IR_VOLUME_DOWN = helpers.OPT_IR_VOLUME_DOWN
OPT_IR_VOLUME_UP = helpers.OPT_IR_VOLUME_UP
_cec_supported = helpers._cec_supported
_display_control = helpers._display_control
_ir_code = helpers._ir_code
_ir_supported = helpers._ir_supported
_mute_ir_configured = helpers._mute_ir_configured
_volume_ir_configured = helpers._volume_ir_configured
MoIPReceiver = helpers.MoIPReceiver


def _entry(receivers: dict) -> SimpleNamespace:
    return SimpleNamespace(options={"receivers": receivers})


def test_display_control_defaults_to_cec() -> None:
    entry = _entry({})
    assert _display_control(entry, 1) == DISPLAY_CONTROL_CEC


def test_display_control_ir() -> None:
    entry = _entry({"1": {OPT_DISPLAY_CONTROL: DISPLAY_CONTROL_IR}})
    assert _display_control(entry, 1) == DISPLAY_CONTROL_IR


def test_ir_code_strips_and_rejects_blank() -> None:
    entry = _entry(
        {
            "1": {
                OPT_IR_POWER_ON: " 0000 006C ",
                OPT_IR_POWER_OFF: "   ",
            }
        }
    )
    assert _ir_code(entry, 1, OPT_IR_POWER_ON) == "0000 006C"
    assert _ir_code(entry, 1, OPT_IR_POWER_OFF) is None


def test_volume_ir_requires_both_codes() -> None:
    entry = _entry({"1": {OPT_IR_VOLUME_UP: "up"}})
    assert _volume_ir_configured(entry, 1) is False

    entry = _entry(
        {"1": {OPT_IR_VOLUME_UP: "up", OPT_IR_VOLUME_DOWN: "down"}}
    )
    assert _volume_ir_configured(entry, 1) is True


def test_mute_ir_configured() -> None:
    entry = _entry({})
    assert _mute_ir_configured(entry, 1) is False
    entry = _entry({"1": {OPT_IR_MUTE: "mute"}})
    assert _mute_ir_configured(entry, 1) is True


def test_ir_supported_rest_requires_ir_rx() -> None:
    assert _ir_supported(MoIPReceiver(id=1, name="RX"), "rest") is False
    assert (
        _ir_supported(MoIPReceiver(id=1, name="RX", ir_rx_id=10), "rest") is True
    )
    assert _ir_supported(MoIPReceiver(id=1, name="RX"), "tcp") is True


def test_cec_supported_rest_requires_video_rx() -> None:
    assert _cec_supported(MoIPReceiver(id=1, name="RX"), "rest") is False
    assert (
        _cec_supported(MoIPReceiver(id=1, name="RX", video_rx_id=10), "rest")
        is True
    )
