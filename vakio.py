"""Service classes for interacting with Vakio devices"""
from __future__ import annotations
import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta, datetime, timezone
import time

import logging
import random
from typing import Any
import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_TIMEINTERVAL,
    DOMAIN,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOPIC,
    CONF_USERNAME,
    CONNECTION_TIMEOUT,
    OPENAIR_STATE_OFF,
    OPENAIR_STATE_ON,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

SPEED_ENDPOINT = "speed"
GATE_ENDPOINT = "gate"
STATE_ENDPOINT = "state"
WORKMODE_ENDPOINT = "endpoint"
ENDPOINTS = [SPEED_ENDPOINT, GATE_ENDPOINT, STATE_ENDPOINT, WORKMODE_ENDPOINT]


class MqttBroker:
    """MqttBroker class for connecting to a broker."""

    def __init__(
        self, data: dict(str, Any), coordinator: Coordinator | None = None
    ) -> None:
        """Initialize."""
        self.data = data
        self.client_id = f"python-mqtt-{random.randint(0, 1000)}"
        self.client = mqtt.Client(client_id=self.client_id)
        self._coordinator = coordinator
        if len(self.data.keys()) == 5:
            self.client.username_pw_set(
                self.data[CONF_USERNAME], self.data[CONF_PASSWORD]
            )

    def on_message():

    async def try_connect(self) -> bool:
        """Try to create connection with the broker."""
        result = False
        if await self.connect():
            self.client.disconnect()
            result = True
        return result

    async def connect(self) -> bool:
        """Connect with the broker."""
        global status
        status = None

        def on_connect(client, userdata, flags, rc):
            global status
            status = True if rc == 0 else False

        self.client.on_connect = on_connect
        try:
            self.client.connect(self.data[CONF_HOST], self.data[CONF_PORT])
        except Exception:  # pylint: disable=broad-exception-caught
            return False

        return status if status is not None else True

    async def get_condition(self, coordinator: Coordinator) -> dict(str, Any):
        """Get condition of device"""

        def on_message(client, userdata, message: mqtt.MQTTMessage):
            key = str.split(message.topic, "/")[-1]
            value = message.payload.decode()
            coordinator.condition[key] = value
            _LOGGER.info(
                print(f"{k}: {val}") for k, val in coordinator.condition.items()
            )

        self.client.on_message = on_message
        self.client.subscribe(
            [(f"{self.data[CONF_TOPIC]}/{endpoint}", 0) for endpoint in ENDPOINTS]
        )

    def publish(self, endpoint: str, msg: str) -> bool:
        """Publish commands to topic"""
        topic = self.data[CONF_TOPIC] + "/" + endpoint

        pub_status = self.client.publish(topic, msg)[0]
        return True if pub_status == 0 else False


class Coordinator(DataUpdateCoordinator):
    """Class for interact with Broker and HA"""

    def __init__(self, hass: HomeAssistant, data: dict(str, Any)) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_TIMEINTERVAL
        )
        self._data = data
        self.broker = MqttBroker(data, self)
        self.last_update = None
        self.condition = {
            GATE_ENDPOINT: None,
            SPEED_ENDPOINT: None,
            WORKMODE_ENDPOINT: None,
            STATE_ENDPOINT: None,
        }

    async def async_login(self) -> bool:
        status = await self.broker.connect()
        if not status:
            _LOGGER.error("Auth error")
        return status

    async def _async_update_data(self) -> bool:
        """Get all data"""
        await self.broker.get_condition(self)

    def speed(self, value: int | None = None) -> int | bool | None:
        """Speed of fan"""
        if value is None:
            return self.condition[SPEED_ENDPOINT]

        return self.broker.publish(SPEED_ENDPOINT, value)

    def gate(self, value: int | None = None) -> int | bool | None:
        """Gate of device"""
        if value is None:
            return self.condition[GATE_ENDPOINT]

        return self.broker.publish(GATE_ENDPOINT, value)

    def state(self, value: str | None = None) -> str | bool | None:
        """State of device"""
        if value is None:
            return self.condition[STATE_ENDPOINT]

        return self.broker.publish(STATE_ENDPOINT, value)

    def workmode(self, value: str | None = None) -> str | bool | None:
        """Workmode of device: manual or super_auto"""
        if value is None:
            return self.condition[WORKMODE_ENDPOINT]

        return self.broker.publish(WORKMODE_ENDPOINT, value)

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
