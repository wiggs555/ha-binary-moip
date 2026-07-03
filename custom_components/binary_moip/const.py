"""Constants for the Binary MoIP integration."""

from datetime import timedelta

DOMAIN = "binary_moip"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_HTTPS_PORT = "https_port"
CONF_CONTROL_PORT = "control_port"
CONF_VERIFY_SSL = "verify_ssl"
CONF_API_MODE = "api_mode"

API_MODE_REST = "rest"
API_MODE_TCP = "tcp"

DEFAULT_HTTPS_PORT = 443
DEFAULT_CONTROL_PORT = 23
DEFAULT_VERIFY_SSL = False

FALLBACK_SCAN_INTERVAL = timedelta(seconds=60)
WS_REFRESH_COOLDOWN = 2.0
WS_BACKOFF_START = 2.0
WS_BACKOFF_MAX = 60.0

OPT_RECEIVERS = "receivers"
OPT_TRANSMITTERS = "transmitters"
OPT_ENABLED = "enabled"
OPT_LABEL = "label"

SOURCE_OFF = "Off"
MANUFACTURER = "SnapAV Binary"

ATTR_PAIRED_TRANSMITTER = "paired_transmitter"
ATTR_PAIRED_TRANSMITTER_NAME = "paired_transmitter_name"
ATTR_API_MODE = "api_mode"
ATTR_INPUT_TYPE = "input_type"
ATTR_UNIT_NAME = "unit_name"
ATTR_INDEX = "index"

PLATFORMS = ["media_player", "sensor"]
