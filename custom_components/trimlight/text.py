"""Custom pattern draft name and inspectable pixel map."""
from homeassistant.components.text import TextEntity

from .data import get_data
from .editor import PatternEditorEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = get_data(hass, entry.entry_id)
    async_add_entities([PatternNameText(hass, entry.entry_id, data.coordinator)])


class PatternNameText(PatternEditorEntity, TextEntity):
    _attr_name = "Trimlight Pattern Name"
    _attr_native_min = 1
    _attr_native_max = 64

    def __init__(self, hass, entry_id, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_pattern_name"

    @property
    def native_value(self) -> str:
        return self.draft.name

    @property
    def extra_state_attributes(self) -> dict:
        from copy import deepcopy

        return {"pixels": deepcopy(self.draft.pixels), "mode": self.draft.mode,
                "speed": self.draft.speed, "brightness": self.draft.brightness,
                "selected_index": self.draft.selected_index, "last_saved_id": self.draft.last_saved_id}

    async def async_set_value(self, value: str) -> None:
        self.edit_draft("set_name", value)
