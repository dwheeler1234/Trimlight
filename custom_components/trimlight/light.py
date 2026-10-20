from __future__ import annotations

import time
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FORCED_ON_GRACE_SECONDS
from .controller import apply_effect_update
from .controls import require_success, solid_rgb
from .data import get_data
from .debug import async_log_event
from .entity import TrimlightEntity
from .editor import PatternEditorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = get_data(hass, entry.entry_id)
    coordinator = data.coordinator
    async_add_entities([
        TrimlightLight(hass, entry.entry_id, coordinator),
        PatternColorLight(hass, entry.entry_id, coordinator),
    ])


class PatternColorLight(PatternEditorEntity, LightEntity):
    """A local color-picker entity for the selected draft entry."""
    _attr_name = "Trimlight Pattern Entry Color"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, hass, entry_id, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_pattern_entry_color"

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        color = self.draft.selected_pixel["color"]
        return color >> 16, (color >> 8) & 255, color & 255

    @property
    def brightness(self) -> int:
        return self.draft.brightness

    @property
    def is_on(self) -> bool:
        return not self.draft.selected_pixel["disable"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_RGB_COLOR in kwargs:
            self.edit_draft("set_rgb", kwargs[ATTR_RGB_COLOR])
        if ATTR_BRIGHTNESS in kwargs:
            self.edit_draft("set_number", "brightness", kwargs[ATTR_BRIGHTNESS])
        self.draft.selected_pixel["disable"] = False
        self.notify_draft()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.draft.selected_pixel["disable"] = True
        self.notify_draft()


class TrimlightLight(TrimlightEntity, LightEntity):
    _attr_name = "Trimlight"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_light"

    @property
    def is_on(self) -> bool | None:
        return self._is_effectively_on()

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return solid_rgb((self.coordinator.data or {}).get("current_effect") or {})

    @property
    def brightness(self) -> int | None:
        data = self.coordinator.data or {}
        brightness = data.get("brightness")
        if brightness is None:
            return self._data.last_brightness
        return int(brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        data = self._data
        api = data.api
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb = kwargs.get(ATTR_RGB_COLOR)

        switch_resp = await api.set_switch_state(1)
        require_success(switch_resp)

        # Optimistic UI update: mark on immediately
        coord_data = self.coordinator.data or {}
        optimistic = dict(coord_data)
        optimistic["switch_state"] = 1
        self.coordinator.async_set_updated_data(optimistic)
        # Grace window to keep UI on while controller catches up
        data.forced_on_until = time.monotonic() + FORCED_ON_GRACE_SECONDS
        data.forced_off_until = None

        if rgb is not None:
            brightness = int(brightness if brightness is not None else self.brightness or data.last_brightness)
            color = (int(rgb[0]) << 16) | (int(rgb[1]) << 8) | int(rgb[2])
            try:
                response = await api.preview_solid(f"{color:06X}", brightness)
                require_success(response)
            except Exception:
                self._schedule_verification_refresh()
                raise
            self._cancel_pending_followups()
            self._clear_pending_transition()
            data.last_brightness = brightness
            data.last_speed = 0
            data.last_selected_preset = None
            data.last_selected_custom_preset = None
            data.last_selected_custom_mode = None
            data.last_known_preset = None
            data.last_known_builtin_preset = None
            data.last_known_custom_preset = None
            effect = {
                "id": -1, "category": 1, "mode": 0, "speed": 0,
                "brightness": brightness,
                "pixels": [{"index": 0, "count": 60, "color": color, "disable": False}],
            }
            data.last_known_custom_pixels = effect["pixels"]
            optimistic.update(
                current_effect=effect, current_effect_id=-1,
                current_effect_category=1, brightness=brightness,
            )
            self.coordinator.async_set_updated_data(optimistic)
        elif brightness is not None:
            data.last_brightness = int(brightness)
            await apply_effect_update(
                api, data, self.coordinator.data or {}, brightness=int(brightness)
            )

        await async_log_event(
            self._hass,
            data,
            "light_turn_on",
            coordinator_data=optimistic,
            requested_brightness=brightness,
            requested_rgb=rgb,
            switch_response=switch_resp,
        )

        self._schedule_verification_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        data = self._data
        api = data.api
        switch_resp = await api.set_switch_state(0)
        require_success(switch_resp)
        self._cancel_pending_followups()
        self._clear_pending_transition()
        coord_data = self.coordinator.data or {}
        optimistic = dict(coord_data)
        optimistic["switch_state"] = 0
        optimistic["current_effect"] = {}
        optimistic["current_effect_id"] = None
        optimistic["current_effect_category"] = None
        self.coordinator.async_set_updated_data(optimistic)
        # Grace window to keep UI off while controller catches up
        data.forced_off_until = time.monotonic() + FORCED_ON_GRACE_SECONDS
        data.forced_on_until = None
        # Clear last-selected preset context when lights turn off
        data.last_selected_preset = None
        data.last_selected_custom_preset = None
        data.last_selected_custom_mode = None
        await async_log_event(
            self._hass,
            data,
            "light_turn_off",
            coordinator_data=optimistic,
            switch_response=switch_resp,
        )
        self._schedule_verification_refresh()

