"""Config flow for the Binary MoIP integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    DISPLAY_CONTROL_CEC,
    DISPLAY_CONTROL_IR,
    DOMAIN,
    OPT_DISPLAY_CONTROL,
    OPT_ENABLED,
    OPT_IR_MUTE,
    OPT_IR_POWER_OFF,
    OPT_IR_POWER_ON,
    OPT_IR_VOLUME_DOWN,
    OPT_IR_VOLUME_UP,
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

_IR_OPTION_KEYS = (
    OPT_DISPLAY_CONTROL,
    OPT_IR_POWER_ON,
    OPT_IR_POWER_OFF,
    OPT_IR_VOLUME_UP,
    OPT_IR_VOLUME_DOWN,
    OPT_IR_MUTE,
)

_IR_MENU_DONE = "done"


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
        self._receivers: dict[str, dict[str, Any]] = {}
        self._transmitters: dict[str, dict[str, Any]] = {}
        self._ir_receiver_id: str | None = None

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title="",
            data={
                OPT_RECEIVERS: self._receivers,
                OPT_TRANSMITTERS: self._transmitters,
            },
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage entity enable/disable options."""
        if user_input is not None:
            existing = self.config_entry.options.get(OPT_RECEIVERS, {})
            receivers: dict[str, dict[str, Any]] = {}
            transmitters: dict[str, dict[str, Any]] = {}
            for key, value in user_input.items():
                if key.startswith("rx_"):
                    rx_id = key.removeprefix("rx_")
                    merged = dict(existing.get(rx_id, {}))
                    merged.update(value)
                    receivers[rx_id] = merged
                elif key.startswith("tx_"):
                    transmitters[key.removeprefix("tx_")] = value
            self._receivers = receivers
            self._transmitters = transmitters
            return await self.async_step_ir_menu()

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

    async def async_step_ir_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a receiver to configure IR display control, or finish."""
        coordinator = self.config_entry.runtime_data
        if coordinator is None or coordinator.data is None:
            return self._finish()

        options: list[selector.SelectOptionDict] = [
            {"value": _IR_MENU_DONE, "label": "Done"},
        ]
        for rx_id, receiver in sorted(coordinator.data.receivers.items()):
            opts = self._receivers.get(str(rx_id), {})
            label = opts.get(OPT_LABEL, receiver.name)
            options.append({"value": str(rx_id), "label": label})

        if user_input is not None:
            choice = user_input["receiver"]
            if choice == _IR_MENU_DONE:
                return self._finish()
            self._ir_receiver_id = choice
            return await self.async_step_ir_codes()

        return self.async_show_form(
            step_id="ir_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("receiver", default=_IR_MENU_DONE): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    ),
                }
            ),
        )

    async def async_step_ir_codes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit IR Pronto codes and display control for one receiver."""
        rx_id = self._ir_receiver_id
        if rx_id is None:
            return await self.async_step_ir_menu()

        opts = self._receivers.setdefault(rx_id, {})

        if user_input is not None:
            for key in _IR_OPTION_KEYS:
                value = user_input.get(key)
                if isinstance(value, str):
                    value = value.strip()
                if value:
                    opts[key] = value
                else:
                    opts.pop(key, None)
            if OPT_DISPLAY_CONTROL not in opts:
                opts[OPT_DISPLAY_CONTROL] = DISPLAY_CONTROL_CEC
            self._ir_receiver_id = None
            return await self.async_step_ir_menu()

        coordinator = self.config_entry.runtime_data
        receiver_name = opts.get(OPT_LABEL, rx_id)
        if coordinator is not None and coordinator.data is not None:
            receiver = coordinator.data.receivers.get(int(rx_id))
            if receiver is not None:
                receiver_name = opts.get(OPT_LABEL, receiver.name)

        return self.async_show_form(
            step_id="ir_codes",
            description_placeholders={"receiver": receiver_name},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_DISPLAY_CONTROL,
                        default=opts.get(OPT_DISPLAY_CONTROL, DISPLAY_CONTROL_CEC),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": DISPLAY_CONTROL_CEC, "label": "HDMI CEC"},
                                {"value": DISPLAY_CONTROL_IR, "label": "IR"},
                            ]
                        )
                    ),
                    vol.Optional(
                        OPT_IR_POWER_ON,
                        description={"suggested_value": opts.get(OPT_IR_POWER_ON, "")},
                        default=opts.get(OPT_IR_POWER_ON, ""),
                    ): str,
                    vol.Optional(
                        OPT_IR_POWER_OFF,
                        description={"suggested_value": opts.get(OPT_IR_POWER_OFF, "")},
                        default=opts.get(OPT_IR_POWER_OFF, ""),
                    ): str,
                    vol.Optional(
                        OPT_IR_VOLUME_UP,
                        description={"suggested_value": opts.get(OPT_IR_VOLUME_UP, "")},
                        default=opts.get(OPT_IR_VOLUME_UP, ""),
                    ): str,
                    vol.Optional(
                        OPT_IR_VOLUME_DOWN,
                        description={
                            "suggested_value": opts.get(OPT_IR_VOLUME_DOWN, "")
                        },
                        default=opts.get(OPT_IR_VOLUME_DOWN, ""),
                    ): str,
                    vol.Optional(
                        OPT_IR_MUTE,
                        description={"suggested_value": opts.get(OPT_IR_MUTE, "")},
                        default=opts.get(OPT_IR_MUTE, ""),
                    ): str,
                }
            ),
        )
