"""Config flow for the Binary MoIP integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from binary_moip.exceptions import AuthError

from .adapter import probe_api_mode
from .const import (
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
    OPT_ENABLED,
    OPT_LABEL,
    OPT_RECEIVERS,
    OPT_TRANSMITTERS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_HTTPS_PORT, default=DEFAULT_HTTPS_PORT): int,
        vol.Optional(CONF_CONTROL_PORT, default=DEFAULT_CONTROL_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class BinaryMoIPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Binary MoIP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()

            try:
                api_mode = await probe_api_mode(
                    host,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    https_port=user_input[CONF_HTTPS_PORT],
                    control_port=user_input[CONF_CONTROL_PORT],
                    verify_ssl=user_input[CONF_VERIFY_SSL],
                )
            except AuthError:
                errors["invalid_auth"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during probe: %s", err)
                errors["cannot_connect"] = "cannot_connect"
            else:
                if api_mode is None:
                    errors["cannot_connect"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"Binary MoIP ({host})",
                        data={
                            **user_input,
                            CONF_HOST: host,
                            CONF_API_MODE: api_mode,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BinaryMoIPOptionsFlowHandler:
        """Get the options flow."""
        return BinaryMoIPOptionsFlowHandler(config_entry)


class BinaryMoIPOptionsFlowHandler(OptionsFlow):
    """Handle options for Binary MoIP."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage entity enable/disable options."""
        if user_input is not None:
            receivers: dict[str, dict[str, Any]] = {}
            transmitters: dict[str, dict[str, Any]] = {}
            for key, value in user_input.items():
                if key.startswith("rx_"):
                    receivers[key.removeprefix("rx_")] = value
                elif key.startswith("tx_"):
                    transmitters[key.removeprefix("tx_")] = value
            return self.async_create_entry(
                title="",
                data={
                    OPT_RECEIVERS: receivers,
                    OPT_TRANSMITTERS: transmitters,
                },
            )

        coordinator = self.config_entry.runtime_data
        if coordinator is None or coordinator.data is None:
            return self.async_create_entry(title="", data={})

        state = coordinator.data
        schema: dict[vol.Marker, Any] = {}

        for rx_id, receiver in sorted(state.receivers.items()):
            opts = self.config_entry.options.get(OPT_RECEIVERS, {}).get(str(rx_id), {})
            schema[
                vol.Optional(
                    f"rx_{rx_id}",
                    description={"suggested_value": receiver.name},
                    default={
                        OPT_ENABLED: opts.get(OPT_ENABLED, True),
                        OPT_LABEL: opts.get(OPT_LABEL, receiver.name),
                    },
                )
            ] = vol.Schema(
                {
                    vol.Optional(OPT_ENABLED, default=True): bool,
                    vol.Optional(OPT_LABEL, default=receiver.name): str,
                }
            )

        for tx_id, transmitter in sorted(state.transmitters.items()):
            opts = self.config_entry.options.get(OPT_TRANSMITTERS, {}).get(str(tx_id), {})
            schema[
                vol.Optional(
                    f"tx_{tx_id}",
                    description={"suggested_value": transmitter.name},
                    default={
                        OPT_ENABLED: opts.get(OPT_ENABLED, True),
                        OPT_LABEL: opts.get(OPT_LABEL, transmitter.name),
                    },
                )
            ] = vol.Schema(
                {
                    vol.Optional(OPT_ENABLED, default=True): bool,
                    vol.Optional(OPT_LABEL, default=transmitter.name): str,
                }
            )

        if not schema:
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
