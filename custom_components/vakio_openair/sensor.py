"""Sensor platform."""

import logging

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PREFIX, DEFAULT_PREFIX, DOMAIN, HUD_ENDPOINT, TEMP_ENDPOINT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenAir sensor devices from a config entry."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if len(config) == 0:
        config = config_entry.data

    prefix = config.get(CONF_PREFIX, DEFAULT_PREFIX)

    async_add_entities(
        [
            OpenAirTemperatureSensor(hass, prefix, config_entry.entry_id),
            OpenAirHumiditySensor(hass, prefix, config_entry.entry_id),
        ]
    )


class OpenAirTemperatureSensor(SensorEntity):
    """Representation of an OpenAir temperature sensor."""

    def __init__(self, hass, prefix, entry_id):
        """Initialize the sensor."""
        self._hass = hass
        self._prefix = prefix
        self.unique_id = f"{entry_id}_temp_{prefix}"
        self._state = None
        self._sub_temp = None
        self._attr_name = "OpenAir Temperature"

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        await mqtt.async_subscribe(
            self.hass, f"{self._prefix}/{TEMP_ENDPOINT}", self._handle_temp_message
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @callback
    def _handle_temp_message(self, msg):
        """Handle new temperature messages."""
        self._state = float(msg.payload)
        self.async_write_ha_state()


class OpenAirHumiditySensor(SensorEntity):
    """Representation of an OpenAir humidity sensor."""

    def __init__(self, hass, prefix, entry_id):
        """Initialize the sensor."""
        self._hass = hass
        self._prefix = prefix
        self.unique_id = f"{entry_id}_hud_{prefix}"
        self._state = None
        self._sub_hud = None
        self._attr_name = "OpenAir Humidity"

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        await mqtt.async_subscribe(
            self.hass, f"{self._prefix}/{HUD_ENDPOINT}", self._handle_hud_message
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @callback
    def _handle_hud_message(self, msg):
        """Handle new humidity messages."""
        self._state = float(msg.payload)
        self.async_write_ha_state()
