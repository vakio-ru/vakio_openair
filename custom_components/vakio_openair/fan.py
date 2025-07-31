"""Fan platform."""

from __future__ import annotations

import decimal
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    CONF_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
    GATE_ENDPOINT,
    OPENAIR_GATE_04,
    OPENAIR_GATE_LIST,
    OPENAIR_SPEED_00,
    OPENAIR_SPEED_01,
    OPENAIR_SPEED_LIST,
    OPENAIR_STATE_OFF,
    OPENAIR_STATE_ON,
    OPENAIR_WORKMODE_MANUAL,
    OPENAIR_WORKMODE_SUPERAUTO,
    SPEED_ENDPOINT,
    STATE_ENDPOINT,
    WORKMODE_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

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

    async def async_publish(self, topic, payload):
        """Publish a message to MQTT."""
        await mqtt.async_publish(self.hass, topic, payload, 1)

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
            await self.async_publish(
                f"{self._prefix}/{SPEED_ENDPOINT}", OPENAIR_SPEED_00
            )
            return self.async_write_ha_state()

        speed: decimal.Decimal = percentage_to_ordered_list_item(
            OPENAIR_SPEED_LIST,
            percentage,
        )
        if not self._state:
            await self.async_turn_on(percentage)
        else:
            await self.async_publish(f"{self._prefix}/{SPEED_ENDPOINT}", speed)

        return self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Переключение режима работы на основе пресета."""
        if self.preset_modes and preset_mode not in self.preset_modes:
            raise ValueError(f"Неизвестный режим: {preset_mode}")

        self._prev_preset_mode = self._preset_mode

        # self._preset_mode = preset_mode
        if preset_mode in PRESET_MOD_GATES:
            if self._preset_mode == PRESET_MOD_SUPER_AUTO:
                """Если текущий режим - SMART. Тогда делаем Manual."""
                await self.async_publish(
                    f"{self._prefix}/{WORKMODE_ENDPOINT}", OPENAIR_WORKMODE_MANUAL
                )

            if (
                preset_mode != PRESET_MOD_GATE_04
                and self._percentage != OPENAIR_SPEED_00
            ):
                """Если заслонка не в положении "Полностью открыта", то устанавливаем скорость 0"""
                await self.async_publish(
                    f"{self._prefix}/{SPEED_ENDPOINT}", OPENAIR_SPEED_00
                )
                self._percentage = 0

            await self.async_publish(
                f"{self._prefix}/{GATE_ENDPOINT}", PRESET_MOD_GATES[preset_mode]
            )
            self._preset_mode = preset_mode
        elif preset_mode == PRESET_MOD_SUPER_AUTO:
            await self.async_publish(
                f"{self._prefix}/{WORKMODE_ENDPOINT}", OPENAIR_WORKMODE_SUPERAUTO
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
        await self.async_publish(f"{self._prefix}/{STATE_ENDPOINT}", OPENAIR_STATE_ON)

        # Получение именованой скорости.
        if percentage is None:
            if self._prev_percentage is not None:
                percentage = self._prev_percentage
                self._prev_percentage = None
            else:
                percentage = ordered_list_item_to_percentage(
                    OPENAIR_SPEED_LIST, OPENAIR_SPEED_01
                )

        await self.async_set_percentage(percentage)

        if preset_mode is None:
            if self._prev_preset_mode is not None:
                preset_mode = self._prev_preset_mode
                self._prev_preset_mode = None
            else:
                preset_mode = PRESET_MOD_GATE_04

        await self.async_set_preset_mode(preset_mode)

        self._state = True
        self._attr_is_on = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Выключение устройства."""
        await self.async_publish(f"{self._prefix}/{STATE_ENDPOINT}", OPENAIR_STATE_OFF)
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
