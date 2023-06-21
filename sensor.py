"""Demo platform that has a couple of fake sensors."""
from __future__ import annotations
from datetime import datetime, timedelta

from typing import cast

from .vakio import Coordinator
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    conf: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo sensors."""
    temp = VakioSensor(
        hass,
        conf.entry_id,
        "temp",
        "OpenAir Temp Sensor",
        1,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        UnitOfTemperature.CELSIUS,
    )
    hud = VakioSensor(
        hass,
        conf.entry_id,
        "hud",
        "OpenAir Humidity Sensor",
        1,
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        PERCENTAGE,
    )
    async_add_entities([temp, hud])
    async_track_time_interval(hass, temp._async_update, timedelta(seconds=30))
    async_track_time_interval(hass, hud._async_update, timedelta(seconds=30))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, config_entry, async_add_entities)


class VakioSensor(SensorEntity):
    """Representation of a Demo sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        unique_id: str,
        name: str | None,
        state: StateType,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
        battery: StateType | None = None,
        options: list[str] | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.coordinator: Coordinator = hass.data[DOMAIN][entry_id]
        self._entity_id = entry_id
        self._attr_device_class = device_class
        if name is not None:
            self._attr_name = name
        else:
            self._attr_has_entity_name = True
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_value = state
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id
        self._attr_options = options
        self._attr_translation_key = translation_key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

        if battery:
            self._attr_extra_state_attributes = {ATTR_BATTERY_LEVEL: battery}

    # @property
    # def state(self) -> int:
    #     if SensorDeviceClass.TEMPERATURE == self._attr_device_class:
    #         val = self.coordinator.get_temp()
    #     else:
    #         val = self.coordinator.get_hud()
    #     return val if val is not None else 20

    # @property
    # def native_value(self) -> StateType:
    #     if SensorDeviceClass.TEMPERATURE == self._attr_device_class:
    #         val = self.coordinator.get_temp()
    #     else:
    #         val = self.coordinator.get_hud()
    #     return val if val is not None else 20

    async def _async_update(self, now: datetime) -> None:
        if SensorDeviceClass.TEMPERATURE == self._attr_device_class:
            val = self.coordinator.get_temp()
        else:
            val = self.coordinator.get_hud()

        self._attr_native_value = val if val is not None else 20
        self.async_write_ha_state()
