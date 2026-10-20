"""Offline editor tests. Run directly with Python; never contacts a controller."""
from __future__ import annotations

from copy import deepcopy
import importlib
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import test_feature_controls as feature

feature.module("homeassistant.components.button", ButtonEntity=type("ButtonEntity", (), {}))
feature.module("homeassistant.components.text", TextEntity=type("TextEntity", (), {}))
feature.module("homeassistant.components.select", SelectEntity=type("SelectEntity", (), {}))
pattern = importlib.import_module("trimlight_feature_test.pattern")
editor = importlib.import_module("trimlight_feature_test.editor")
button = importlib.import_module("trimlight_feature_test.button")
text = importlib.import_module("trimlight_feature_test.text")
select = importlib.import_module("trimlight_feature_test.select")


def make_editor(cls=editor.PatternEditorEntity):
    entity, runtime, api = feature.make_entity(cls)
    entity.coordinator.async_update_listeners = Mock()
    api.save_effect.return_value = {"code": 0, "payload": {"id": 0}}
    return entity, runtime, api


class PatternTests(unittest.TestCase):
    def test_entry_limits_and_sparse_load(self):
        draft = pattern.PatternDraft.from_effect({"category": 1, "mode": 16,
            "pixels": [{"index": 29, "count": 60, "color": 0xFFFFFF, "disable": True}]})
        self.assertEqual(len(draft.pixels), 30)
        self.assertEqual(draft.pixels[0]["count"], 0)
        self.assertEqual(draft.pixels[29]["count"], 60)
        self.assertTrue(draft.pixels[29]["disable"])

    def test_drafts_are_independent_and_payload_is_copied(self):
        a, b = pattern.PatternDraft(), pattern.PatternDraft()
        payload = a.effect()
        payload["pixels"][0]["color"] = 123
        a.pixels[0]["count"] = 7
        self.assertEqual(a.pixels[0]["color"], 0xFFFFFF)
        self.assertEqual(b.pixels[0]["count"], 1)

    def test_invalid_fields_rejected(self):
        draft = pattern.PatternDraft()
        for key, value in [("selected_index", -1), ("selected_index", 30), ("count", 61),
                           ("count", 0.5), ("speed", 256), ("brightness", -1), ("mode", 17),
                           ("count", True), ("speed", float("nan"))]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                draft.set_number(key, value)
        for color in [(256, 0, 0), (0, -1, 0), (1, 2), "FF0000"]:
            with self.assertRaises(ValueError):
                draft.set_rgb(color)
        for name in ["", "  ", "a" * 65]:
            with self.assertRaises(ValueError):
                draft.set_name(name)

    def test_duplicate_and_invalid_controller_entries_rejected(self):
        pixel = {"index": 0, "count": 2, "color": 255}
        for pixels in [[pixel, pixel], [dict(pixel, index=30)], [dict(pixel, color=-1)],
                       [dict(pixel, disable="false")], [], [pixel] * 31]:
            with self.assertRaises(ValueError):
                pattern.PatternDraft.from_effect({"category": 1, "pixels": pixels})

    def test_all_disabled_or_zero_rejected(self):
        draft = pattern.PatternDraft()
        draft.pixels[0]["disable"] = True
        with self.assertRaises(ValueError):
            draft.effect()
        draft.pixels[0].update(count=0, disable=False)
        with self.assertRaises(ValueError):
            draft.effect()

    async def test_editing_draft_never_calls_controller(self):
        entity, _, api = make_editor()
        entity.edit_draft("set_number", "selected_index", 29)
        entity.edit_draft("set_number", "count", 60)
        entity.edit_draft("set_rgb", (255, 10, 20))
        entity.edit_draft("set_name", "Holiday")
        self.assertEqual(entity.draft.selected_pixel["color"], 0xFF0A14)
        entity.coordinator.async_set_updated_data.assert_not_called()
        for method in vars(api).values():
            method.assert_not_awaited()

    def test_load_saved_definition_is_a_copy(self):
        entity, runtime, _ = make_editor()
        saved = {"id": 7, "name": "Source", "category": 1, "mode": 3, "speed": 44,
                 "brightness": 55, "pixels": [{"index": 2, "count": 3, "color": 255}]}
        entity.coordinator.data.update(current_effect={"id": 7, "category": 1}, current_effect_id=7)
        runtime.custom_cache = [saved]
        entity.load_current_pattern()
        entity.draft.pixels[2]["color"] = 123
        self.assertEqual(saved["pixels"][0]["color"], 255)
        self.assertEqual(entity.draft.mode, 3)
        self.assertEqual(entity.draft.effect()["id"], -1)

    def test_invalid_load_preserves_existing_draft(self):
        entity, _, _ = make_editor()
        original = entity.draft
        with self.assertRaises(feature.HomeAssistantError):
            entity.load_current_pattern()
        self.assertIs(entity.draft, original)

    async def test_preview_uses_draft_and_never_saves(self):
        entity, runtime, api = make_editor()
        entity.draft.set_name("Red and green")
        entity.draft.set_rgb((255, 0, 0))
        entity.draft.set_number("selected_index", 1)
        entity.draft.set_number("count", 4)
        entity.draft.set_rgb((0, 255, 0))
        await entity.preview_pattern()
        effect = api.preview_effect.await_args.args[0]
        self.assertEqual(effect["pixels"][1]["color"], 65280)
        self.assertEqual(effect["id"], -1)
        self.assertEqual(entity.coordinator.data["switch_state"], 1)
        self.assertEqual(entity.coordinator.data["current_effect_id"], -1)
        self.assertEqual(runtime.last_brightness, 200)
        api.save_effect.assert_not_awaited()

    async def test_failed_preview_does_not_publish_draft(self):
        entity, _, api = make_editor()
        original = deepcopy(entity.coordinator.data)
        api.preview_effect.return_value = {"code": 10001}
        with self.assertRaises(feature.HomeAssistantError):
            await entity.preview_pattern()
        self.assertEqual(entity.coordinator.data, original)
        entity._schedule_verification_refresh.assert_called_once()

    async def test_rejected_power_never_previews(self):
        entity, _, api = make_editor()
        api.set_switch_state.return_value = {"code": 10002}
        with self.assertRaises(feature.HomeAssistantError):
            await entity.preview_pattern()
        api.preview_effect.assert_not_awaited()

    async def test_save_creates_copy_and_does_not_run_or_power_on(self):
        entity, runtime, api = make_editor()
        prior = deepcopy(entity.coordinator.data["current_effect"])
        await entity.save_new_pattern()
        saved_request = api.save_effect.await_args.args[0]
        self.assertEqual(saved_request["id"], -1)
        self.assertEqual(runtime.custom_cache[0]["id"], 0)
        self.assertEqual(entity.draft.last_saved_id, 0)
        self.assertEqual(entity.coordinator.data["current_effect"], prior)
        api.set_switch_state.assert_not_awaited()
        api.preview_effect.assert_not_awaited()

    async def test_failed_save_does_not_add_local_preset(self):
        entity, runtime, api = make_editor()
        api.save_effect.return_value = {"code": 10001}
        with self.assertRaises(feature.HomeAssistantError):
            await entity.save_new_pattern()
        self.assertEqual(runtime.custom_cache, [])
        self.assertIsNone(entity.draft.last_saved_id)
        entity.coordinator.async_set_updated_data.assert_not_called()

    async def test_missing_save_id_is_not_retried(self):
        entity, runtime, api = make_editor()
        api.save_effect.return_value = {"code": 0}
        with self.assertRaises(feature.HomeAssistantError):
            await entity.save_new_pattern()
        api.save_effect.assert_awaited_once()
        self.assertEqual(runtime.custom_cache, [])
        entity._schedule_verification_refresh.assert_called_once()

    async def test_empty_pattern_never_calls_api(self):
        entity, _, api = make_editor()
        entity.draft.selected_pixel["count"] = 0
        for action in (entity.save_new_pattern, entity.preview_pattern):
            with self.assertRaises(feature.HomeAssistantError):
                await action()
        api.save_effect.assert_not_awaited()
        api.set_switch_state.assert_not_awaited()

    async def test_color_picker_and_disable_only_change_draft(self):
        entity, _, api = make_editor(feature.light.PatternColorLight)
        await entity.async_turn_on(rgb_color=(10, 20, 30), brightness=125)
        self.assertEqual(entity.rgb_color, (10, 20, 30))
        self.assertEqual(entity.brightness, 125)
        await entity.async_turn_off()
        self.assertFalse(entity.is_on)
        api.preview_effect.assert_not_awaited()

    async def test_mode_selector_rejects_undocumented_modes(self):
        entity, _, _ = make_editor(select.PatternModeSelect)
        await entity.async_select_option("Chase Forward")
        self.assertEqual(entity.draft.mode, 1)
        with self.assertRaises(feature.HomeAssistantError):
            await entity.async_select_option("Firework")

    async def test_source_selector_loads_copy_without_running_lights(self):
        entity, runtime, api = make_editor(select.PatternSourceSelect)
        saved = {"id": 7, "name": "Game Day", "category": 1, "mode": 1,
                 "pixels": [{"index": 0, "count": 5, "color": 255}]}
        runtime.custom_cache = [saved]
        self.assertEqual(entity.options, ["New Pattern", "Game Day (id 7)"])
        await entity.async_select_option("Game Day (id 7)")
        self.assertEqual(entity.current_option, "Game Day (id 7)")
        self.assertEqual(entity.draft.source_id, 7)
        entity.draft.selected_pixel["count"] = 12
        self.assertEqual(saved["pixels"][0]["count"], 5)
        api.set_switch_state.assert_not_awaited()
        api.preview_effect.assert_not_awaited()
        await entity.async_select_option("New Pattern")
        self.assertIsNone(entity.draft.source_id)

    async def test_missing_source_does_not_discard_draft(self):
        entity, _, _ = make_editor(select.PatternSourceSelect)
        original = entity.draft
        with self.assertRaises(feature.HomeAssistantError):
            await entity.async_select_option("Missing (id 99)")
        self.assertIs(entity.draft, original)

    def test_draft_survives_poll_and_offline_editing(self):
        entity, _, _ = make_editor(text.PatternNameText)
        entity.draft.set_name("Keep draft")
        entity.coordinator.data = {"switch_state": 0}
        entity.coordinator.last_update_success = False
        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, "Keep draft")

    async def test_platform_setup_registers_editor_entities_with_unique_ids(self):
        entity, _, _ = make_editor()
        ids = []
        for platform in (feature.light, feature.number, feature.switch, button, text, select):
            registered = []
            await platform.async_setup_entry(entity._hass, SimpleNamespace(entry_id="test"), registered.extend)
            ids.extend(e._attr_unique_id for e in registered)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("test_pattern_entry_color", ids)
        self.assertIn("test_save_new_pattern", ids)


for name, method in list(vars(PatternTests).items()):
    if name.startswith("test_") and inspect.iscoroutinefunction(method):
        setattr(PatternTests, name, feature.offline_async_test(method))


if __name__ == "__main__":
    unittest.main(verbosity=2)
