# Binary MoIP Home Assistant Integration

Home Assistant custom integration for SnapAV Binary MoIP controllers, built on the [binary-moip](https://github.com/wiggs555/binary-moip) Python driver.

## Features

- **Auto-detect API mode** — tries REST (firmware 4.x+) first, falls back to TCP control (port 23)
- **Media player per receiver** — select video sources from Home Assistant
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

## Entities

| Entity | Description |
|--------|-------------|
| `media_player.*` | One per receiver — source selection via `select_source` |
| `sensor.*_status` (receiver) | Online status, paired transmitter attributes |
| `sensor.*_status` (transmitter) | Online status, input type, unit name |

## Requirements

- Home Assistant 2024.1 or later
- Binary MoIP controller reachable on your LAN
- The integration installs the `binary-moip` Python package automatically

## Development

```bash
# Run unit tests (requires binary-moip installed)
pip install -e ../binary-moip
pip install pytest pytest-asyncio
pytest
```

## License

MIT
