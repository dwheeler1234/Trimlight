"""Local draft editing and explicit controller preview/save operations."""
from __future__ import annotations

from copy import deepcopy
import time

from homeassistant.exceptions import HomeAssistantError

from .const import FORCED_ON_GRACE_SECONDS
from .controls import require_success
from .entity import TrimlightEntity
from .pattern import PatternDraft


class PatternEditorEntity(TrimlightEntity):
    """Draft fields stay editable even if the cloud controller is unavailable."""

    @property
    def available(self) -> bool:
        return True

    @property
    def draft(self) -> PatternDraft:
        return self._data.pattern_draft

    def notify_draft(self) -> None:
        self.coordinator.async_update_listeners()

    def edit_draft(self, method: str, *args) -> None:
        try:
            getattr(self.draft, method)(*args)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc
        self.notify_draft()

    def new_pattern(self) -> None:
        self._data.pattern_draft = PatternDraft()
        self.notify_draft()

    def load_current_pattern(self) -> None:
        state = self.coordinator.data or {}
        if self._active_pending_transition() is not None:
            raise HomeAssistantError("Wait for preset selection to finish before loading it")
        effect = deepcopy(state.get("current_effect") or {})
        # A saved definition has a complete pixel map on controllers that omit it from currentEffect.
        if effect.get("category") in (1, 2) and state.get("current_effect_id") not in (None, -1):
            presets = state.get("custom_effects") or self._data.custom_cache
            saved = next((p for p in presets if p.get("id") == state["current_effect_id"]), None)
            if saved is not None:
                effect = deepcopy(saved)
        try:
            draft = PatternDraft.from_effect(effect)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc
        self._data.pattern_draft = draft
        self.notify_draft()

    def draft_effect(self) -> dict:
        try:
            return self.draft.effect()
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def preview_pattern(self) -> None:
        runtime = self._data
        async with runtime.pattern_lock:
            effect = self.draft_effect()
            require_success(await runtime.api.set_switch_state(1))
            # Cancel pending reapplications before they can replace the new preview.
            self._cancel_pending_followups()
            self._clear_pending_transition()
            try:
                response = await runtime.api.preview_effect(effect, effect["brightness"], speed=effect["speed"])
                require_success(response)
            except Exception:
                self._schedule_verification_refresh()
                raise
            runtime.last_brightness = effect["brightness"]
            runtime.last_speed = effect["speed"]
            runtime.last_selected_preset = None
            runtime.last_selected_custom_preset = None
            runtime.last_selected_custom_mode = None
            runtime.last_known_preset = None
            runtime.last_known_builtin_preset = None
            runtime.last_known_custom_preset = None
            runtime.last_known_custom_pixels = deepcopy(effect["pixels"])
            runtime.forced_on_until = time.monotonic() + FORCED_ON_GRACE_SECONDS
            runtime.forced_off_until = None
            updated = dict(self.coordinator.data or {})
            updated.update(current_effect=effect, current_effect_id=-1, current_effect_category=2,
                           brightness=effect["brightness"], switch_state=1)
            self.coordinator.async_set_updated_data(updated)
            self._schedule_verification_refresh()

    async def save_new_pattern(self) -> None:
        runtime = self._data
        async with runtime.pattern_lock:
            draft = self.draft
            effect = self.draft_effect()
            response = await runtime.api.save_effect(effect, effect["brightness"], speed=effect["speed"])
            require_success(response)
            effect_id = (response.get("payload") or {}).get("id")
            if isinstance(effect_id, bool) or not isinstance(effect_id, int) or effect_id < 0:
                # The write may have succeeded. Do not silently retry and create another copy.
                self._schedule_verification_refresh()
                raise HomeAssistantError("Save accepted but no preset ID was returned; refresh presets before saving again")
            saved = dict(effect, id=effect_id)
            draft.last_saved_id = effect_id
            runtime.custom_cache = [p for p in runtime.custom_cache if p.get("id") != effect_id] + [saved]
            updated = dict(self.coordinator.data or {})
            updated["custom_effects"] = [p for p in (updated.get("custom_effects") or []) if p.get("id") != effect_id] + [saved]
            updated["effects"] = [p for p in (updated.get("effects") or []) if p.get("id") != effect_id] + [saved]
            self.coordinator.async_set_updated_data(updated)
            self._schedule_verification_refresh()
