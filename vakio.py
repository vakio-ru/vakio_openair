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

    def __init__(self, data: dict(str, Any)) -> None:
        """Initialize."""
        self.data = data
        self.client_id = f'python-mqtt-{random.randint(0, 1000)}'
        self.client = mqtt.Client(client_id=self.client_id)
        if (len(self.data.keys()) == 5):
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
        except: # pylint: disable=bare-except
            return False

        return True
    
    async def get_condition(self) -> dict(str, Any):
        


class Coordinator(DataUpdateCoordinator):
    """Class for interact with Broker and HA"""
    def __init__(self,
                 hass: HomeAssistant,
                 data: dict(str, Any)) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_TIMEINTERVAL)
        self._data = data
        self.broker = MqttBroker(data)

    async def async_login(self) -> bool:
        status = await self.broker.connect()
        if not status:
            _LOGGER.error(f"Auth error")
        return status

    async def _async_update_data(self) -> bool:
        """Get all data"""
        await self._async_update(datetime.now(timezone.utc))

    async def _async_update(self, now: datetime) -> None:
        """Register in hass, sensors and devices"""
        update: bool = False
        if self.lastUpdate == None:
            self.lastUpdate = now
            update = True
        diff = now - self.lastUpdate
        if diff > timedelta(seconds=2):
            self.lastUpdate = now
            update = True
        if not update:
            return
        self.condition = await self.hass.async_add_executor_job(self.api.Condition)