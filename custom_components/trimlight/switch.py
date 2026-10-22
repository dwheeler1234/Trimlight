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
from .editor import PatternEditorEntity
from .scheduling import SchedulingController


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = get_data(hass, entry.entry_id)
    async_add_entities([
        TrimlightReverseSwitch(hass, entry.entry_id, data.coordinator),
        PatternDisabledSwitch(hass, entry.entry_id, data.coordinator),
        *[TrimlightDailyScheduleSwitch(hass, entry.entry_id, data.coordinator, slot) for slot in range(2)],
    ])


class TrimlightDailyScheduleSwitch(TrimlightEntity, SwitchEntity):
    def __init__(self, hass, entry_id, coordinator, slot):
        super().__init__(hass, entry_id, coordinator)
        self.slot = slot
        self._attr_name = f"Trimlight Daily Schedule {slot + 1}"
        self._attr_unique_id = f"{entry_id}_daily_schedule_{slot}"

    @property
    def is_on(self):
        verifier = self._data.daily_verifier
        pending = verifier.pending.get(self.slot) if verifier else None
        if pending:
            return pending["target"]
        daily = ((self.coordinator.data or {}).get("payload") or {}).get("daily") or []
        record = next((p for p in daily if p.get("id") == self.slot), None)
        return record.get("enable") if record else None

    @property
    def assumed_state(self):
        verifier = self._data.daily_verifier
        return bool(verifier and self.slot in verifier.pending)

    @property
    def extra_state_attributes(self):
        verifier = self._data.daily_verifier
        if verifier is None:
            return {"verification_status": "reported"}
        pending = verifier.pending.get(self.slot)
        return {"verification_status": verifier.status.get(self.slot, "reported"),
                "pending_enabled": pending["target"] if pending else None,
                "reported_enabled": verifier.reported(self.slot)}

    async def async_turn_on(self, **kwargs):
        await SchedulingController(self._data).execute("enable_daily_schedule", {"schedule_id": self.slot, "enabled": True})

    async def async_turn_off(self, **kwargs):
        await SchedulingController(self._data).execute("enable_daily_schedule", {"schedule_id": self.slot, "enabled": False})


class PatternDisabledSwitch(PatternEditorEntity, SwitchEntity):
    _attr_name = "Trimlight Pattern Entry Disabled"

    def __init__(self, hass, entry_id, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_pattern_entry_disabled"

    @property
    def is_on(self) -> bool:
        return self.draft.selected_pixel["disable"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.draft.selected_pixel["disable"] = True
        self.notify_draft()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.draft.selected_pixel["disable"] = False
        self.notify_draft()


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
