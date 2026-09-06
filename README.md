# Binary MoIP Home Assistant Integration

Home Assistant custom integration for SnapAV Binary MoIP controllers, built on the [binary-moip](https://github.com/wiggs555/binary-moip) Python driver.

## Features

- **Auto-detect API mode** — tries REST (firmware 4.x+) first, falls back to TCP control (port 23)
- **Media player per receiver** — select video sources and control display power via HDMI CEC or IR
- **IR volume and mute** — optional Pronto codes for volume up/down and mute toggle on older displays
- **Send IR service** — blast any Pronto hex, or common Samsung/LG TV commands, from a receiver IR output
- **Send CEC service** — send ad-hoc HDMI CEC hex frames (or canned TV on/off) from a receiver video output
- **Status sensors** — receiver and transmitter online/routing status
- **Real-time updates** — WebSocket push (REST) or unsolicited TCP routing events, with 60s polling fallback

## Installation

### HACS (recommended)

1. Add this repository as a [custom HACS repository](https://hacs.xyz/docs/faq/custom_repositories/)
2. Install **Binary MoIP** from the Integrations category
3. Restart Home Assistant

### Manual

Copy the `custom_components/binary_moip` folder into your Home Assistant `custom_components` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Binary MoIP**
3. Enter your controller host, credentials, and ports:
   - **HTTPS port** — REST API (default 443)
   - **TCP control port** — legacy control API (default 23)
   - **Verify SSL** — disable for self-signed controller certificates

After setup, use **Configure** on the integration to enable/disable individual receivers and transmitters or override friendly names.

### IR display control

Receivers connected to displays that need IR (instead of HDMI CEC) can be configured in the same **Configure** flow:

1. Choose **IR display control** from the options menu
2. Select a receiver
3. Set **Display power control** to **IR** and paste Pronto hex codes for power on, power off, volume up, volume down, and mute
4. Return to the menu and choose **Save and finish**

Notes:

- Volume is step-only (`volume_up` / `volume_down`); absolute volume level is not available
- Mute is a single toggle code (open-loop; Home Assistant does not track mute state from the display)
- Leave a Pronto field blank to clear it
- REST mode requires the receiver’s `ir_rx` association; TCP mode uses the receiver index

### Send IR service

Use `binary_moip.send_ir` to blast IR from any MoIP receiver media player. Provide **either** raw Pronto hex **or** a built-in brand command (not both).

Built-in brands: `samsung`, `lg`. Commands include `power`, `power_on`, `power_off`, `volume_up`, `volume_down`, `mute`, `channel_up`, `channel_down`, `source`, `home`, `menu`, `info`, `up`, `down`, `left`, `right`, `ok`, `back`, `exit`, `hdmi_1`…`hdmi_4`, and digits `0`–`9`. Discrete power and HDMI codes are model-dependent; use raw Pronto when a built-in command does not work.

```yaml
action: binary_moip.send_ir
target:
  entity_id: media_player.living_room
data:
  brand: samsung
  command: power_on
```

```yaml
action: binary_moip.send_ir
target:
  entity_id: media_player.living_room
data:
  brand: lg
  command: volume_up
```

```yaml
action: binary_moip.send_ir
target:
  entity_id: media_player.living_room
data:
  pronto: "0000 006D 0000 0022 00AC 00AC 0015 0040 ..."
```

### Send CEC service

Use `binary_moip.send_cec` to send HDMI CEC from any MoIP receiver media player. Provide a raw hex frame or a canned `tv_on` / `tv_off` command.

Raw frames use colon- or space-separated hex bytes (the first byte is source+destination, then opcode and optional parameters). REST mode posts them to the receiver’s `video_rx` endpoint. TCP mode only supports the canned `tv_on` / `tv_off` commands (`!CEC=RX,1|0`).

```yaml
action: binary_moip.send_cec
target:
  entity_id: media_player.living_room
data:
  command: "40:04"
```

```yaml
action: binary_moip.send_cec
target:
  entity_id: media_player.living_room
data:
  command: "40:36"
```

```yaml
action: binary_moip.send_cec
target:
  entity_id: media_player.living_room
data:
  command: tv_on
```

Common frames (playback device 1 → TV): `40:04` image view on, `40:36` standby. Capture device-specific frames from your display if these do not work.

Canned `tv_off` is a firmware helper; this integration does not control the exact bytes it puts on the wire. Many LG Simplink TVs ignore directed CEC Standby (`40:36`). In REST mode, try these raw frames in order:

| Command | Meaning |
|---------|---------|
| `4F:36` | System Standby (broadcast) from Playback 1 |
| `F0:36` | Standby from Unregistered → TV |
| `40:44:6D` then `40:45` | User Control Pressed (Power Off) + Released |

```yaml
action: binary_moip.send_cec
target:
  entity_id: media_player.living_room
data:
  command: "4F:36"
```

No hex is guaranteed — Pulse-Eight’s vendor matrix lists LG TV Power Off as unsupported on many models. Confirm Simplink / HDMI CEC is enabled on the TV. If CEC still does nothing, use IR:

```yaml
action: binary_moip.send_ir
target:
  entity_id: media_player.living_room
data:
  brand: lg
  command: power_off
```

Or set that receiver’s **Display power control** to **IR** so `media_player.turn_off` blasts Pronto instead of CEC.

## Entities

| Entity | Description |
|--------|-------------|
| `media_player.*` | One per receiver — source selection via `select_source`; display power via `turn_on`/`turn_off` (CEC or IR); optional IR `volume_up`/`volume_down`/`volume_mute`; `binary_moip.send_cec` for ad-hoc CEC |
| `sensor.*_status` (receiver) | Online status, paired transmitter attributes |
| `sensor.*_status` (transmitter) | Online status, input type, unit name |

## Requirements

- Home Assistant 2024.1 or later (2026.3+ for local brand icons/logos)
- Binary MoIP controller reachable on your LAN
- The integration installs the `binary-moip` Python package automatically

## Brand images

Starting with Home Assistant 2026.3, icons and logos are loaded from `custom_components/binary_moip/brand/`. Images must meet the [Home Assistant brand image specs](https://developers.home-assistant.io/docs/core/integration/brand_images/):

| File | Size |
|------|------|
| `icon.png` | 256 × 256 (square) |
| `icon@2x.png` | 512 × 512 |
| `logo.png` | shortest side 128–256 |
| `logo@2x.png` | shortest side 256–512 |

After updating brand assets, restart Home Assistant or reload the integration.

## Development

```bash
# Run unit tests (requires binary-moip installed)
pip install -e ../binary-moip
pip install pytest pytest-asyncio
pytest
```

## License

MIT
