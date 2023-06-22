"""Config flow for Vakio Smart Control integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_TOPIC,
    DEFAULT_SMART_GATE,
    DEFAULT_SMART_SPEED,
    DEFAULT_SMART_EMERG_SHUNT,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TOPIC,
    OPT_EMERG_SHUNT,
    OPT_SMART_SPEED,
    OPT_SMART_GATE,
)
from .vakio import MqttClient, Coordinator

_LOGGER = logging.getLogger(__name__)

TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PORT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)),
    vol.Coerce(int),
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
GATE_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.SLIDER, min=1, max=4)),
    vol.Coerce(int),
)
SPEED_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.SLIDER, min=1, max=5)),
    vol.Coerce(int),
)
TEMP_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=15)),
    vol.Coerce(int),
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TEXT_SELECTOR,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): PORT_SELECTOR,
        vol.Optional(CONF_USERNAME): TEXT_SELECTOR,
        vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
        vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): TEXT_SELECTOR,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    broker = MqttClient(hass, data)

    if not await broker.try_connect():
        raise InvalidAuth

    # return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vakio Smart Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle a options flow for Vakio Smart Control"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            coordinator: Coordinator = self.hass.data[DOMAIN][
                self.config_entry.entry_id
            ]
            await coordinator.update_smart_mode(
                user_input[OPT_EMERG_SHUNT], user_input[OPT_SMART_GATE], user_input[OPT_SMART_SPEED]
            )
            return self.async_create_entry(title="Параметры обновлены", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_EMERG_SHUNT, default=DEFAULT_SMART_EMERG_SHUNT
                    ): TEMP_SELECTOR,
                    vol.Required(
                        OPT_SMART_GATE, default=DEFAULT_SMART_GATE
                    ): GATE_SELECTOR,
                    vol.Required(
                        OPT_SMART_SPEED, default=DEFAULT_SMART_SPEED
                    ): SPEED_SELECTOR,
                }
            ),
        )
        # return await self.async_step_smartauto_options()

    # async def async_step_smartauto_options(self, user_input=None):


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
