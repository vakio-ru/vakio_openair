from __future__ import annotations
import decimal
from typing import Any, Optional
import logging
import voluptuous as vol
from datetime import datetime, timedelta, timezone

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .vakio import Coordinator
from .const import (
    DOMAIN,
    OPENAIR_STATE_ON,
    OPENAIR_STATE_OFF,
    OPENAIR_WORKMODE_MANUAL,
    OPENAIR_WORKMODE_SUPERAUTO,
    OPENAIR_SPEED_LIST,
    OPENAIR_GATE_LIST,
)


async def async_setup_entry(
    hass: HomeAssistant, conf: ConfigEntry, entities: AddEntitiesCallback
) -> bool:
    """Register settings of device."""
    return await async_setup_platform(hass, conf, entities)


async def async_setup_platform(
    hass: HomeAssistant,
    conf: ConfigType,
    entities: AddEntitiesCallback,
    info: DiscoveryInfoType | None = None,
) -> bool:
    pass


class VakioOpenAirBase(FanEntity):
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        entry_id: str,
        supported_features: FanEntityFeature,
        preset_modes: list[str] | None,
        translation_key: str | None = None,
    ) -> None:
        """Конструктор."""
        self.hass = hass
        self._unique_id = unique_id
        self._attr_supported_features = supported_features
        self._percentage: int | None = None
        self._preset_modes = preset_modes
        self._preset_mode: str | None = None
        self._oscillating: bool | None = None
        self._direction: str | None = None
        self._attr_name = name
        self._entity_id = entry_id
        if supported_features & FanEntityFeature.OSCILLATE:
            self._oscillating = False
        if supported_features & FanEntityFeature.DIRECTION:
            self._direction = None
        self._attr_translation_key = translation_key
        self.coordinator: Coordinator = hass.data[DOMAIN][entry_id]

    @property
    def unique_id(self) -> str:
        """Возвращение уникального идентификатора."""
        return self._unique_id
