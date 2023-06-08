"""Service classes for interacting with Vakio devices"""
from __future__ import annotations
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta, datetime, timezone

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
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class MqttBroker:
    """MqttBroker class for connecting to a broker."""

    SPEED_ENDPOINT = "/speed"
    GATE_ENDPOINT = "/gate"
    STATE_ENDPOINT = "/state"
    WORKMODE_ENDPOINT = "/endpoint"
    ENDPOINTS = [SPEED_ENDPOINT, GATE_ENDPOINT, STATE_ENDPOINT, WORKMODE_ENDPOINT]

    def __init__(self, data: dict(str, Any)) -> None:
        """Initialize."""
        self.data = data
        self.client_id = f"python-mqtt-{random.randint(0, 1000)}"
        self.client = mqtt.Client(client_id=self.client_id)
        if len(self.data.keys()) == 5:
            self.client.username_pw_set(self.data["username"], self.data["password"])

    async def try_connect(self) -> bool:
        """Try to create connection with the broker."""
        result = False
        if await self.connect():
            self.client.disconnect()
            result = True
        return result

    async def connect(self) -> bool:
        """Connect with the broker."""
        try:
            self.client.connect(self.data["host"], self.data["port"])
        except:  # pylint: disable=bare-except
            return False

        return True

    def get_condition(self, coordinator: Coordinator) -> dict(str, Any):
        """Getting condition of device"""

        def on_message(client, userdata, message: mqtt.MQTTMessage):
            key = str.split(message.topic)[-1]
            value = message.payload.decode()
            coordinator.condition[key] = value
            _LOGGER.info(
                print(f"{k}: {val}") for k, val in coordinator.condition.items()
            )

        self.client.on_message = on_message
        self.client.subscribe(
            [(self.data["topic"] + "/" + endpoint) for endpoint in self.ENDPOINTS]
        )
        _LOGGER.info()


class Coordinator(DataUpdateCoordinator):
    """Class for interact with Broker and HA"""

    def __init__(self, hass: HomeAssistant, data: dict(str, Any)) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_TIMEINTERVAL
        )
        self._data = data
        self.broker = MqttBroker(data)
        self.last_update = None
        self.condition = {}

    async def async_login(self) -> bool:
        status = await self.broker.connect()
        if not status:
            _LOGGER.error(f"Auth error")
        return status

    async def _async_update_data(self) -> bool:
        """Get all data"""
        await self.broker.get_condition(self)
