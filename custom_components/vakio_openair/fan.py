"""Fan platform."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import decimal
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    DOMAIN,
    OPENAIR_GATE_LIST,
    OPENAIR_SPEED_00,
    OPENAIR_SPEED_01,
    OPENAIR_SPEED_LIST,
    OPENAIR_STATE_OFF,
    OPENAIR_WORKMODE_MANUAL,
    OPENAIR_WORKMODE_SUPERAUTO,
)
from .vakio import Coordinator

percentage = ordered_list_item_to_percentage(OPENAIR_SPEED_LIST, OPENAIR_SPEED_01)
named_speed = percentage_to_ordered_list_item(OPENAIR_SPEED_LIST, 20)

FULL_SUPPORT = (
    FanEntityFeature.SET_SPEED
    | FanEntityFeature.DIRECTION
    | FanEntityFeature.OSCILLATE
    | FanEntityFeature.PRESET_MODE
)
LIMITED_SUPPORT = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
PRESET_MOD_GATE_01 = "Gate 1"
PRESET_MOD_GATE_02 = "Gate 2"
PRESET_MOD_GATE_03 = "Gate 3"
PRESET_MOD_GATE_04 = "Gate 4"
PRESET_MOD_SUPER_AUTO = "Super Auto"

PRESET_MOD_GATES = {
    PRESET_MOD_GATE_01: OPENAIR_GATE_LIST[0],
    PRESET_MOD_GATE_02: OPENAIR_GATE_LIST[1],
    PRESET_MOD_GATE_03: OPENAIR_GATE_LIST[2],
    PRESET_MOD_GATE_04: OPENAIR_GATE_LIST[3],
}

PRESET_MODS = [
    PRESET_MOD_GATE_01,
    PRESET_MOD_GATE_02,
    PRESET_MOD_GATE_03,
    PRESET_MOD_GATE_04,
    PRESET_MOD_SUPER_AUTO,
]


async def async_setup_entry(
    hass: HomeAssistant, conf: ConfigEntry, entities: AddEntitiesCallback
) -> None:
    """Register settings of device."""
    await async_setup_platform(hass, conf, entities)  # type: ignore


async def async_setup_platform(
    hass: HomeAssistant,
    conf: ConfigType,
    entities: AddEntitiesCallback,
    info: DiscoveryInfoType | None = None,
) -> None:
    """Установка платформы в hass."""
    topic = conf.data["topic"]  # type: ignore
    openair = VakioOpenAirFan(
        hass, topic, "OpenAir", conf.entry_id, LIMITED_SUPPORT, PRESET_MODS  # type: ignore
    )
    entities([openair])
    coordinator: Coordinator = hass.data[DOMAIN][conf.entry_id]  # type: ignore
    await coordinator.async_login()
    async_track_time_interval(
        hass,
        coordinator._async_update,  # pylint: disable=protected-access
        timedelta(seconds=1),
    )
    async_track_time_interval(
        hass,
        openair._async_update,  # pylint: disable=protected-access
        timedelta(seconds=1),
    )


class VakioOpenAirFanBase(FanEntity):
    """Base class for VakioOperAirFan."""

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
        """Функция иниципализации."""
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
        """Return unique id."""
        return self._unique_id

    @property
    def current_direction(self) -> str | None:
        """Currnt direction of fan."""
        return self._direction

    @property
    def oscillating(self) -> bool | None:
        """Current oscillating."""
        return self._oscillating


class VakioOpenAirFan(VakioOpenAirFanBase, FanEntity):
    """Программное представления устройства для связи с hass."""

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
        self, percentage: int  # pylint: disable=redefined-outer-name
    ) -> None:
        """Установка скорости работы вентиляции в процентах."""
        current_workmode = self.coordinator.get_workmode()

        if current_workmode == OPENAIR_WORKMODE_SUPERAUTO:
            self._percentage = self.coordinator.get_speed()
            return self.async_write_ha_state()

        self._percentage = percentage
        if percentage == 0:
            await self.coordinator.speed(0)
            return self.update_all_options()

        await self.coordinator.turn_on()
        # Получение именованой скорости.
        speed: decimal.Decimal = percentage_to_ordered_list_item(
            OPENAIR_SPEED_LIST, percentage  # type: ignore
        )

        await self.coordinator.speed(speed)  # type: ignore

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Переключение режима работы на основе пресета."""
        if self.preset_modes and preset_mode in self.preset_modes:
            self._preset_mode = preset_mode
        else:
            raise ValueError(f"Неизвестный режим: {preset_mode}")
        if (
            self._preset_mode
            in PRESET_MOD_GATES  # pylint: disable=consider-iterating-dictionary
        ):
            if self.coordinator.get_workmode() == OPENAIR_WORKMODE_SUPERAUTO:
                await self.coordinator.workmode(OPENAIR_WORKMODE_MANUAL)
            if self._preset_mode != PRESET_MOD_GATE_04:
                await self.coordinator.speed(OPENAIR_SPEED_00)
            await self.coordinator.gate(PRESET_MOD_GATES[self._preset_mode])
            return
        elif self._preset_mode == PRESET_MOD_SUPER_AUTO:
            await self.coordinator.workmode(OPENAIR_WORKMODE_SUPERAUTO)
            return

        self.update_all_options()

    async def async_turn_on(
        self,
        percentage: int | None = None,  # pylint: disable=redefined-outer-name
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Включение вентиляционной системы."""
        await self.coordinator.turn_on()
        # Получение именованой скорости.
        new_speed: decimal.Decimal = decimal.Decimal(0)
        if percentage is not None:
            new_speed = percentage_to_ordered_list_item(OPENAIR_SPEED_LIST, percentage)  # type: ignore
        else:
            new_speed = OPENAIR_SPEED_01  # type: ignore

        await self.coordinator.speed(new_speed)  # type: ignore
        self.update_all_options()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Выключение устройства."""
        await self.coordinator.turn_off()
        await self._async_update(datetime.now(UTC))
        self.schedule_update_ha_state()

    async def _async_update(self, now: datetime) -> None:
        """Async Update.

        Функция вызывается по таймеру.
        Выполняется сравнение параметров состояния устройства с параметрами записанными в классе.
        Если выявляется разница, тогда параметры класса обновляются.
        """
        is_update: bool = False
        if self.update_speed():
            is_update = True
        if self.update_preset_mode():
            is_update = True
        if self.update_on_off():
            is_update = True
        if is_update:
            self.update_all_options()

    def update_speed(self) -> bool:
        """Update Speed.

        Обновление текущей скорости работы устройства.
        Возвращается "истина" если было выполнено обновление.
        """
        speed: int | None = self.coordinator.get_speed()
        if (
            speed is None or speed > len(OPENAIR_SPEED_LIST)
        ) and self._percentage is not None:
            self._percentage = None
            return True
        if speed is None or speed is False:
            return False
        if speed == 0:
            self._percentage = 0
            return True

        speed -= 1
        named_speed = OPENAIR_SPEED_LIST[speed]  # pylint: disable=redefined-outer-name
        new_speed_percentage = ordered_list_item_to_percentage(
            OPENAIR_SPEED_LIST, named_speed
        )

        if self._percentage != new_speed_percentage:
            self._percentage = new_speed_percentage
            return True

        return False

    def update_preset_mode(self) -> bool:
        """Update Preset Mode.

        Обновление текущего предопределённого режима работы вентиляционной системы.
        Возвращается "истина" если было выполнено обновление.
        """
        current_gate = self.coordinator.get_gate()
        current_workmode = self.coordinator.get_workmode()
        mode = None
        if current_workmode == OPENAIR_WORKMODE_SUPERAUTO:
            mode = PRESET_MOD_SUPER_AUTO
        else:
            for key, value in PRESET_MOD_GATES.items():
                if value != current_gate:
                    continue
                mode = key
        if "mode" in locals() and mode != self._preset_mode:
            self._preset_mode = mode
            return True

        return False

    def update_on_off(self) -> bool:
        """Update On Off.

        Обновление текущего состояния включённости вентиляционной системы.
        Возвращается "истина" если было выполнено обновление.
        """
        is_on: bool | None = self.coordinator.is_on()
        if not bool(is_on):
            # Вентиляция выключена.
            if self._percentage is not None and self._percentage > 0:
                self._percentage = 0
                return True
        elif self._percentage is None or self._percentage == 0:
            # Вентиляция включена.
            if self._percentage is None:
                self._percentage = ordered_list_item_to_percentage(
                    OPENAIR_SPEED_LIST, OPENAIR_SPEED_01
                )
            if self._preset_mode == OPENAIR_STATE_OFF:
                self._preset_mode = None
            return True

        return False

    def update_all_options(self) -> None:
        """Update All Options.

        Обновление состояния всех индикаторов интеграции в соответствии
        с переключённым режимом работы вентиляционной системы.
        """
        self.schedule_update_ha_state()
