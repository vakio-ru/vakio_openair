"""The Vakio Smart Control integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant import config_entries, setup
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
)
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    ERROR_AUTH,
    ERROR_CONFIG_NO_TREADY,
)
from .vakio import MqttBroker

PLATFORMS: list[Platform] = []
_LOGGER: logging.Logger = logging.getLogger(__package__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the demo environment."""
    _LOGGER.info("Function __init__.async_setup() called.")

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    data = {}
    for key, value in config_entry.data.items():
        data[key] = value

    broker = MqttBroker(data)

    # Try to connect
    if not await broker.try_connect():
        raise ConfigEntryAuthFailed(ERROR_AUTH)

    # Data refresh
    # TODO refresh
    # await coordinator.async_config_entry_first_refresh()
    # if not coordinator.last_update_success:
    #     raise ConfigEntryNotReady(ERROR_CONFIG_NO_TREADY)

    # Registration of integration in HA
    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    config_entry.add_update_listener(async_reload_entry)
    config_entry.async_on_unload(config_entry.add_update_listener(config_entry_update_listener))
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def config_entry_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Функция вызывается при обновлении конфигурации."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    unload_ok: bool = False
    if DOMAIN not in hass.data:
        return True
    if config_entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        unload_ok = all(
            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_unload(config_entry, platform)
                    for platform in PLATFORMS
                ]
            )
        )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        _LOGGER.info(
            f"Координатор Coordinator() домена {DOMAIN} удалён, entry_id: {config_entry.entry_id}."
        )

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Перезагрузка интеграции."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
