from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import build_builtin_presets_from_effects, build_builtin_presets_static
from .data import get_data
from .debug import async_log_event
from .entity import TrimlightEntity
from .editor import PatternEditorEntity
from .management import ManagementController


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = get_data(hass, entry.entry_id)
    coordinator = data.coordinator
    async_add_entities([
        TrimlightRefreshButton(hass, entry.entry_id, coordinator),
        TrimlightLiveStateButton(hass, entry.entry_id, coordinator),
        *[PatternButton(hass, entry.entry_id, coordinator, action, label)
          for action, label in (("new_pattern", "New Pattern"),
                                ("load_current_pattern", "Load Current Pattern"),
                                ("preview_pattern", "Preview Pattern"),
                                ("save_new_pattern", "Save New Pattern"))],
    ])


class TrimlightLiveStateButton(TrimlightEntity, ButtonEntity):
    _attr_name = "Trimlight Request Live State"

    def __init__(self, hass, entry_id, coordinator):
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_request_live_state"

    async def async_press(self):
        await ManagementController(self._data).execute("request_live_state", {})
        self._schedule_verification_refresh()


class PatternButton(PatternEditorEntity, ButtonEntity):
    def __init__(self, hass, entry_id, coordinator, action, label) -> None:
        super().__init__(hass, entry_id, coordinator)
        self.action = action
        self._attr_name = f"Trimlight {label}"
        self._attr_unique_id = f"{entry_id}_{action}"

    @property
    def available(self) -> bool:
        return self.action not in ("preview_pattern", "save_new_pattern") or self.coordinator.last_update_success

    async def async_press(self) -> None:
        if self.action in ("preview_pattern", "save_new_pattern"):
            await getattr(self, self.action)()
        else:
            getattr(self, self.action)()


class TrimlightRefreshButton(TrimlightEntity, ButtonEntity):
    _attr_name = "Trimlight Refresh Presets"

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator) -> None:
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_refresh_presets"

    async def async_press(self) -> None:
        data = self._data
        await async_log_event(
            self._hass,
            data,
            "refresh_presets_button_pressed",
            coordinator_data=data.coordinator.data or {},
        )

        if not data.builtins_refreshed:
            effects = (data.coordinator.data or {}).get("effects") or []
            builtins = build_builtin_presets_from_effects(effects)
            if not builtins:
                builtins = build_builtin_presets_static()
            if builtins:
                data.builtins = builtins
                data.builtins_refreshed = True

        await data.coordinator.async_refresh()
        await async_log_event(
            self._hass,
            data,
            "refresh_presets_button_completed",
            coordinator_data=data.coordinator.data or {},
            builtins_count=len(data.builtins),
            custom_count=len((data.coordinator.data or {}).get("custom_effects") or data.custom_cache),
        )

