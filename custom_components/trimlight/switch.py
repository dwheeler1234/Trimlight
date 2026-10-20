"""Built-in animation direction control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controls import async_update_builtin, builtin_control_available
from .data import get_data
from .entity import TrimlightEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = get_data(hass, entry.entry_id)
    async_add_entities([TrimlightReverseSwitch(hass, entry.entry_id, data.coordinator)])


class TrimlightReverseSwitch(TrimlightEntity, SwitchEntity):
    _attr_name = "Trimlight Reverse Animation"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_reverse_animation"

    @property
    def available(self) -> bool:
        return builtin_control_available(self)

    @property
    def is_on(self) -> bool | None:
        return ((self.coordinator.data or {}).get("current_effect") or {}).get("reverse")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_update_builtin(self, reverse=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_update_builtin(self, reverse=False)
