"""Service classes for interacting with Vakio devices"""
from __future__ import annotations
import asyncio
import logging
import random
from typing import Any
import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_TIMEINTERVAL,
    DOMAIN,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOPIC,
    CONF_USERNAME,
    OPENAIR_STATE_OFF,
    OPENAIR_STATE_ON,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

SPEED_ENDPOINT = "speed"
GATE_ENDPOINT = "gate"
STATE_ENDPOINT = "state"
WORKMODE_ENDPOINT = "endpoint"
ENDPOINTS = [SPEED_ENDPOINT, GATE_ENDPOINT, STATE_ENDPOINT, WORKMODE_ENDPOINT]


class MqttClient:
    """MqttClient class for connecting to a broker."""

    def __init__(
        self,
        hass: HomeAssistant,
        data: dict(str, Any),
        coordinator: Coordinator | None = None,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.data = data

        self.client_id = f"python-mqtt-{random.randint(0, 1000)}"
        self._client = mqtt.Client(client_id=self.client_id)
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message

        self._coordinator = coordinator
        self.is_run = False
        if len(self.data.keys()) == 5:
            self._client.username_pw_set(
                self.data[CONF_USERNAME], self.data[CONF_PASSWORD]
            )

        self._paho_lock = asyncio.Lock()  # Prevents parallel calls to the MQTT client
        self.is_connected = False

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        """Callback on message"""
        key = str.split(message.topic, "/")[-1]
        value = message.payload.decode()
        self._coordinator.condition[key] = value
        _LOGGER.error((f"{k}: {val}") for k, val in self._coordinator.condition.items())

    def on_connect(self, client, userdata, flags, rc):  # pylint: disable=invalid-name
        """Callback on connect"""
        self.is_connected = True
        _LOGGER.error("It's works!")
        if self._coordinator is not None:
            self.hass.async_add_executor_job(
                self._client.subscribe,
                [(f"{self.data[CONF_TOPIC]}/{endpoint}", 0) for endpoint in ENDPOINTS],
            )
            # self._client.subscribe(
            #     [(f"{self.data[CONF_TOPIC]}/{endpoint}", 0) for endpoint in ENDPOINTS]
            # )
        else:
            raise Exception()

    async def connect(self) -> bool:
        """Connect with the broker."""
        try:
            await self.hass.async_add_executor_job(
                self._client.connect, self.data[CONF_HOST], self.data[CONF_PORT]
            )
            self._client.loop_start()
            return True
        except OSError as err:
            _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)

        return False

    async def disconnect(self) -> None:
        """Disconnect from the broker"""

        def stop() -> None:
            """Stop the MQTT client."""
            # Do not disconnect, we want the broker to always publish will
            self._client.loop_stop()

        # TODO: unsubscribe all

        async with self._paho_lock:
            self.is_connected = False
            await self.hass.async_add_executor_job(stop)
            self._client.disconnect()

    async def try_connect(self) -> bool:
        """Try to create connection with the broker."""
        self._client.on_connect = None

        try:
            self._client.connect(self.data[CONF_HOST], self.data[CONF_PORT])
            return True
        except Exception:
            return False

    async def get_condition(
        self,
    ) -> dict(str, Any):
        """Get condition of device"""

        # if not self.is_run:
        #     self.client.on_message = on_message
        #     self.client.subscribe(
        #         [(f"{self.data[CONF_TOPIC]}/{endpoint}", 0) for endpoint in ENDPOINTS]
        #     )

        # else:
        #     return coordinator.condition
        return self._coordinator.condition

    def publish(self, endpoint: str, msg: str) -> bool:
        """Publish commands to topic"""
        topic = self.data[CONF_TOPIC] + "/" + endpoint

        pub_status = self._client.publish(topic, msg)[0]
        return True if pub_status == 0 else False


class Coordinator(DataUpdateCoordinator):
    """Class for interact with Broker and HA"""

    def __init__(self, hass: HomeAssistant, data: dict(str, Any)) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_TIMEINTERVAL
        )
        self._data = data
        self.mqttc = MqttClient(self.hass, data, self)
        self.last_update = None
        self.condition = {
            GATE_ENDPOINT: None,
            SPEED_ENDPOINT: None,
            WORKMODE_ENDPOINT: None,
            STATE_ENDPOINT: None,
        }

    async def async_login(self) -> bool:
        """"""
        status = await self.mqttc.connect()
        if not status:
            _LOGGER.error("Auth error")
        return status

    async def _async_update_data(self) -> bool:
        """Get all data"""
        await self.mqttc.get_condition()

    def speed(self, value: int | None = None) -> int | bool | None:
        """Speed of fan"""
        if value is None:
            return self.condition[SPEED_ENDPOINT]

        return self.mqttc.publish(SPEED_ENDPOINT, value)

    def gate(self, value: int | None = None) -> int | bool | None:
        """Gate of device"""
        if value is None:
            return self.condition[GATE_ENDPOINT]

        return self.mqttc.publish(GATE_ENDPOINT, value)

    def state(self, value: str | None = None) -> str | bool | None:
        """State of device"""
        if value is None:
            return self.condition[STATE_ENDPOINT]

        return self.mqttc.publish(STATE_ENDPOINT, value)

    def workmode(self, value: str | None = None) -> str | bool | None:
        """Workmode of device: manual or super_auto"""
        if value is None:
            return self.condition[WORKMODE_ENDPOINT]

        return self.mqttc.publish(WORKMODE_ENDPOINT, value)

    def turn_on(self) -> bool:
        """Turn on the device"""
        current_state = self.state()
        if current_state == OPENAIR_STATE_OFF or current_state is None:
            return self.state(OPENAIR_STATE_ON)

        return False

    def turn_off(self) -> bool:
        """Turn off the device"""
        current_state = self.state()
        if current_state == OPENAIR_STATE_ON or current_state is None:
            return self.state(OPENAIR_STATE_OFF)

        return False

    def is_on(self) -> bool:
        """Check is device on"""
        current_state = self.state()
        return current_state == OPENAIR_STATE_ON
