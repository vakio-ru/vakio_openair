"""Fan platform."""

from __future__ import annotations

import decimal
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    CONF_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
    GATE_ENDPOINT,
    JSON_CAPABILITIES,
    JSON_COMMAND_TOPIC,
    JSON_GATE,
    JSON_MODE,
    JSON_ON_OFF,
    JSON_SPEED,
    JSON_STATE_TOPIC,
    JSON_SYSTEM_TOPIC,
    OPENAIR_GATE_04,
    OPENAIR_GATE_LIST,
    OPENAIR_SPEED_00,
    OPENAIR_SPEED_01,
    OPENAIR_SPEED_LIST,
    OPENAIR_STATE_OFF,
    OPENAIR_STATE_ON,
    OPENAIR_WORKMODE_MANUAL,
    OPENAIR_WORKMODE_SUPERAUTO,
    RESPONSE_ENDPOINT,
    SPEED_ENDPOINT,
    STATE_ENDPOINT,
    WORKMODE_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

# Seconds to wait after start before asking the device for its state.
PROBE_DELAY = 5

percentage = ordered_list_item_to_percentage(
    OPENAIR_SPEED_LIST, OPENAIR_SPEED_01)
named_speed = percentage_to_ordered_list_item(OPENAIR_SPEED_LIST, 20)

FULL_SUPPORT = (
    FanEntityFeature.SET_SPEED
    | FanEntityFeature.DIRECTION
    | FanEntityFeature.TURN_ON
    | FanEntityFeature.TURN_OFF
    | FanEntityFeature.OSCILLATE
    | FanEntityFeature.PRESET_MODE
)
LIMITED_SUPPORT = (
    FanEntityFeature.SET_SPEED
    | FanEntityFeature.PRESET_MODE
    | FanEntityFeature.TURN_ON
    | FanEntityFeature.TURN_OFF
)
PRESET_MOD_GATE_00 = "Gate 0"
PRESET_MOD_GATE_01 = "Gate 1"
PRESET_MOD_GATE_02 = "Gate 2"
PRESET_MOD_GATE_03 = "Gate 3"
PRESET_MOD_GATE_04 = "Gate 4"
PRESET_MOD_SUPER_AUTO = "Super Auto"

PRESET_MOD_GATES = {
    PRESET_MOD_GATE_00: OPENAIR_GATE_LIST[0],
    PRESET_MOD_GATE_01: OPENAIR_GATE_LIST[1],
    PRESET_MOD_GATE_02: OPENAIR_GATE_LIST[2],
    PRESET_MOD_GATE_03: OPENAIR_GATE_LIST[3],
    PRESET_MOD_GATE_04: OPENAIR_GATE_LIST[4],
}

PRESET_MODS = [
    PRESET_MOD_GATE_00,
    PRESET_MOD_GATE_01,
    PRESET_MOD_GATE_02,
    PRESET_MOD_GATE_03,
    PRESET_MOD_GATE_04,
    PRESET_MOD_SUPER_AUTO,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenAir fan device from a config entry."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if len(config) == 0:
        config = config_entry.data

    prefix = config.get(CONF_PREFIX, DEFAULT_PREFIX)
    async_add_entities(
        [
            VakioOpenAirFan(
                hass,
                prefix,
                "OpenAir",
                config_entry.entry_id,
                LIMITED_SUPPORT,
                PRESET_MODS,
            )
        ]
    )


class VakioOpenAirFan(FanEntity):
    """Base class for VakioOperAirFan."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        prefix: str,
        name: str,
        entry_id: str,
        supported_features: FanEntityFeature,
        preset_modes: list[str] | None,
    ) -> None:
        """Функция инициализации."""
        self.hass = hass
        self._prefix = prefix
        self._unique_id = f"{entry_id}_{prefix}"
        self._attr_supported_features = supported_features
        self._percentage: int | None = None
        self._preset_modes = preset_modes
        self._preset_mode: str | None = None
        self._attr_name = name
        self._entity_id = entry_id
        self._state = False
        self._attr_is_on = None

        self._prev_preset_mode: str | None = None
        self._prev_percentage: int | None = None

        self._sub_state = None
        self._sub_speed = None
        self._sub_gate = None
        self._sub_workmode = None

        # Becomes True as soon as the device sends any JSON message
        # (firmware >= 1.1.0). From then on commands are sent as JSON, and the
        # device confirms each of them on "{prefix}/response".
        self._json_protocol = False

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        await mqtt.async_subscribe(
            self.hass, f"{self._prefix}/{STATE_ENDPOINT}", self._handle_state_message, 1
        )
        await mqtt.async_subscribe(
            self.hass, f"{self._prefix}/{SPEED_ENDPOINT}", self._handle_speed_message, 1
        )
        await mqtt.async_subscribe(
            self.hass, f"{self._prefix}/{GATE_ENDPOINT}", self._handle_gate_message, 1
        )
        await mqtt.async_subscribe(
            self.hass,
            f"{self._prefix}/{WORKMODE_ENDPOINT}",
            self._handle_workmode_message,
            1,
        )
        for topic in (
            f"{self._prefix}/{RESPONSE_ENDPOINT}",
            JSON_STATE_TOPIC.format(prefix=self._prefix),
            JSON_SYSTEM_TOPIC.format(prefix=self._prefix),
        ):
            await mqtt.async_subscribe(self.hass, topic, self._handle_json_message, 1)

        # Ask the device for its state a few seconds later: right after start
        # the subscriptions above may not have reached the broker yet, and the
        # answer would be lost.
        self.async_on_remove(
            async_call_later(self.hass, PROBE_DELAY, self._async_probe)
        )

    async def _async_probe(self, _now=None) -> None:
        """Ask the device for its state without changing anything.

        Firmware >= 1.1.0 answers an empty capabilities object on
        "{prefix}/response", which also switches us to the JSON protocol.
        Older firmware does not listen on this topic, so nothing happens there.
        """
        await self.async_publish(
            JSON_COMMAND_TOPIC.format(prefix=self._prefix),
            json.dumps({JSON_CAPABILITIES: {}}),
        )

    async def async_publish(self, topic, payload):
        """Publish a message to MQTT."""
        await mqtt.async_publish(self.hass, topic, payload, 1)

    async def async_send(
        self, capabilities: dict[str, Any], legacy: list[tuple[str, Any]]
    ) -> None:
        """Send a command using the protocol the device understands.

        JSON firmware gets one message with all capabilities; older firmware
        gets one message per legacy topic, in the given order.
        """
        if self._json_protocol:
            await self.async_publish(
                JSON_COMMAND_TOPIC.format(prefix=self._prefix),
                json.dumps({JSON_CAPABILITIES: capabilities}),
            )
            return
        for endpoint, value in legacy:
            await self.async_publish(f"{self._prefix}/{endpoint}", value)
        # Still on the legacy protocol: probe again, in case the start-up
        # probe was lost. JSON firmware will answer and switch us over.
        await self._async_probe()

    @property
    def percentage(self) -> int | None:
        """Возвращает текущую скорость в процентах."""
        return self._percentage

    @property
    def speed_count(self) -> int:
        """Возвращает количество поддерживаемых скоростей."""
        return len(OPENAIR_SPEED_LIST)

    @property
    def preset_mode(self) -> str | None:
        """Возвращает текущий пресет режима работы."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Возвращает все пресеты режимов работы."""
        return self._preset_modes

    async def async_set_percentage(
        self,
        percentage: int,  # pylint: disable=redefined-outer-name
    ) -> None:
        """Установка скорости работы вентиляции в процентах."""
        if self._preset_mode == PRESET_MOD_SUPER_AUTO:
            return self.async_write_ha_state()

        self._prev_percentage = self.percentage
        if percentage == 0:
            await self.async_send(
                {JSON_SPEED: OPENAIR_SPEED_00}, [(SPEED_ENDPOINT, OPENAIR_SPEED_00)]
            )
            return self.async_write_ha_state()

        speed: decimal.Decimal = percentage_to_ordered_list_item(
            OPENAIR_SPEED_LIST,
            percentage,
        )
        if not self._state:
            await self.async_turn_on(percentage)
        else:
            await self.async_send({JSON_SPEED: speed}, [(SPEED_ENDPOINT, speed)])

        return self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Переключение режима работы на основе пресета."""
        if self.preset_modes and preset_mode not in self.preset_modes:
            raise ValueError(f"Неизвестный режим: {preset_mode}")

        self._prev_preset_mode = self._preset_mode

        # self._preset_mode = preset_mode
        if preset_mode in PRESET_MOD_GATES:
            capabilities: dict[str, Any] = {}
            legacy: list[tuple[str, Any]] = []
            if self._preset_mode == PRESET_MOD_SUPER_AUTO:
                """Если текущий режим - SMART. Тогда делаем Manual."""
                capabilities[JSON_MODE] = OPENAIR_WORKMODE_MANUAL
                legacy.append((WORKMODE_ENDPOINT, OPENAIR_WORKMODE_MANUAL))

            if (
                preset_mode != PRESET_MOD_GATE_04
                and self._percentage != OPENAIR_SPEED_00
            ):
                """Если заслонка не в положении "Полностью открыта", то устанавливаем скорость 0"""
                capabilities[JSON_SPEED] = OPENAIR_SPEED_00
                legacy.append((SPEED_ENDPOINT, OPENAIR_SPEED_00))
                self._percentage = 0

            capabilities[JSON_GATE] = PRESET_MOD_GATES[preset_mode]
            legacy.append((GATE_ENDPOINT, PRESET_MOD_GATES[preset_mode]))
            await self.async_send(capabilities, legacy)
            self._preset_mode = preset_mode
        elif preset_mode == PRESET_MOD_SUPER_AUTO:
            await self.async_send(
                {JSON_MODE: OPENAIR_WORKMODE_SUPERAUTO},
                [(WORKMODE_ENDPOINT, OPENAIR_WORKMODE_SUPERAUTO)],
            )
            self._preset_mode = preset_mode

        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,  # pylint: disable=redefined-outer-name
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Включение вентиляционной системы."""
        await self.async_send(
            {JSON_ON_OFF: OPENAIR_STATE_ON}, [(STATE_ENDPOINT, OPENAIR_STATE_ON)]
        )
        # Mark as on before setting the speed, otherwise async_set_percentage
        # would call async_turn_on again.
        self._state = True

        # Получение именованой скорости.
        if percentage is None:
            if self._prev_percentage is not None:
                percentage = self._prev_percentage
                self._prev_percentage = None
            else:
                percentage = ordered_list_item_to_percentage(
                    OPENAIR_SPEED_LIST, OPENAIR_SPEED_01
                )

        if preset_mode is None:
            if self._prev_preset_mode is not None:
                preset_mode = self._prev_preset_mode
                self._prev_preset_mode = None
            else:
                preset_mode = PRESET_MOD_GATE_04

        # Gate first, then speed: the device resets the speed to 0 whenever
        # the gate is set, so the opposite order always ended at speed 0.
        await self.async_set_preset_mode(preset_mode)
        await self.async_set_percentage(percentage)

        self._state = True
        self._attr_is_on = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Выключение устройства."""
        await self.async_send(
            {JSON_ON_OFF: OPENAIR_STATE_OFF}, [(STATE_ENDPOINT, OPENAIR_STATE_OFF)]
        )
        self._state = False
        self._attr_is_on = False
        self._percentage = None
        self._preset_mode = None

        self.async_write_ha_state()

    @callback
    def _handle_state_message(self, msg):
        """Handle new state messages."""
        self._state = msg.payload.lower() == "on"
        self._attr_is_on = self._state
        if not self._state:
            self._prev_percentage = self._percentage
            self._percentage = None
            self._prev_preset_mode = self._preset_mode
            self._preset_mode = None
        self.async_write_ha_state()

    @callback
    def _handle_speed_message(self, msg):
        """Handle new speed messages."""
        try:
            speed: int | None = int(msg.payload)
            if (
                speed is None or speed > len(OPENAIR_SPEED_LIST)
            ) and self._percentage is not None:
                self._percentage = None
                return
            if speed is None or speed is False:
                return
            if speed == 0:
                self._percentage = 0
                self.async_write_ha_state()
                return

            speed -= 1
            named_speed = OPENAIR_SPEED_LIST[speed]
            new_speed_percentage = ordered_list_item_to_percentage(
                OPENAIR_SPEED_LIST, named_speed
            )

            self._percentage = new_speed_percentage

            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error("Invalid speed value received: %s", msg.payload)
        except IndexError:
            self._percentage = 100
            self.async_write_ha_state()

    @callback
    def _handle_gate_message(self, msg):
        """Handle new gate messages."""
        try:
            gate_value = int(msg.payload)

            if gate_value != OPENAIR_GATE_04:
                self._percentage = 0

            for name, value in PRESET_MOD_GATES.items():
                if value == gate_value:
                    self._preset_mode = name
                    break

            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error("Invalid gate value received: %s", msg.payload)

    @callback
    def _handle_workmode_message(self, msg):
        """Handle new gate messages."""
        try:
            workmode_value = msg.payload.lower()
            if workmode_value == OPENAIR_WORKMODE_SUPERAUTO:
                self._preset_mode = PRESET_MOD_SUPER_AUTO

            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error("Invalid gate value received: %s", msg.payload)

    @callback
    def _handle_json_message(self, msg):
        """Handle JSON messages from firmware >= 1.1.0.

        "{prefix}/response" answers every JSON command, and
        "device/{prefix}/openair/mode" carries the full state on connect.
        Both report what the device actually did, not what was requested.
        """
        try:
            data = json.loads(msg.payload)
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict):
            return

        if not self._json_protocol:
            _LOGGER.debug(
                "Vakio OpenAir '%s' speaks JSON, switching protocol", self._prefix
            )
        self._json_protocol = True

        capabilities = data.get(JSON_CAPABILITIES)
        if not isinstance(capabilities, dict):
            return

        if JSON_ON_OFF in capabilities:
            self._state = str(capabilities[JSON_ON_OFF]).lower() == OPENAIR_STATE_ON
            self._attr_is_on = self._state

        speed = capabilities.get(JSON_SPEED)
        if isinstance(speed, int) and 0 <= speed <= len(OPENAIR_SPEED_LIST):
            self._percentage = (
                0
                if speed == 0
                else ordered_list_item_to_percentage(
                    OPENAIR_SPEED_LIST, OPENAIR_SPEED_LIST[speed - 1]
                )
            )

        mode = str(capabilities.get(JSON_MODE, "")).lower()
        gate = capabilities.get(JSON_GATE)
        if mode == OPENAIR_WORKMODE_SUPERAUTO:
            self._preset_mode = PRESET_MOD_SUPER_AUTO
        elif isinstance(gate, int):
            for name, value in PRESET_MOD_GATES.items():
                if value == gate:
                    self._preset_mode = name
                    break

        if not self._state:
            self._prev_percentage = self._percentage
            self._percentage = None
            self._prev_preset_mode = self._preset_mode
            self._preset_mode = None

        self.async_write_ha_state()
