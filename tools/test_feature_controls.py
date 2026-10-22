"""Offline regression tests; no Home Assistant install or live controller needed.

Run directly: python tools/test_feature_controls.py
The small HA stand-ins test control logic, not Home Assistant compatibility.
"""
from __future__ import annotations

import inspect
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    sys.modules[name] = result
    return result


class HomeAssistantError(Exception):
    pass


class CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator


class Coordinator:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, **kwargs):
        self.hass = hass
        self.data = None
        self.last_update_success = True


module("homeassistant")
module("homeassistant.components")
module("homeassistant.components.light", ATTR_BRIGHTNESS="brightness", ATTR_RGB_COLOR="rgb_color",
       ColorMode=SimpleNamespace(RGB="rgb", BRIGHTNESS="brightness"), LightEntity=type("LightEntity", (), {}))
module("homeassistant.components.number", NumberEntity=type("NumberEntity", (), {}),
       NumberMode=SimpleNamespace(SLIDER="slider"))
module("homeassistant.components.switch", SwitchEntity=type("SwitchEntity", (), {}))
module("homeassistant.components.sensor", SensorEntity=type("SensorEntity", (), {}))
module("homeassistant.config_entries", ConfigEntry=object)
module("homeassistant.core", HomeAssistant=object)
module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
module("homeassistant.helpers")
module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
module("homeassistant.helpers.update_coordinator", CoordinatorEntity=CoordinatorEntity,
       DataUpdateCoordinator=Coordinator, UpdateFailed=HomeAssistantError)
module("homeassistant.helpers.storage", Store=object)

# Load source modules without executing the integration setup or importing network dependencies.
package = module("trimlight_feature_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "trimlight")]
module("trimlight_feature_test.api", TrimlightApi=object)
controls = importlib.import_module("trimlight_feature_test.controls")
light = importlib.import_module("trimlight_feature_test.light")
number = importlib.import_module("trimlight_feature_test.number")
switch = importlib.import_module("trimlight_feature_test.switch")
controller = importlib.import_module("trimlight_feature_test.controller")
coordinator_module = importlib.import_module("trimlight_feature_test.coordinator")
sensor = importlib.import_module("trimlight_feature_test.sensor")


def make_entity(cls=light.TrimlightLight, effect=None):
    effect = dict(effect or {"id": 7, "category": 0, "mode": 9, "speed": 42,
                             "brightness": 170, "pixelLen": 35, "reverse": False})
    state = {"switch_state": 1, "current_effect": effect,
             "current_effect_id": effect["id"], "current_effect_category": effect["category"],
             "brightness": effect["brightness"], "effects": [], "custom_effects": []}
    coord = SimpleNamespace(data=state, last_update_success=True)
    def update(value):
        coord.data = value
    coord.async_set_updated_data = Mock(side_effect=update)
    api = SimpleNamespace(**{name: AsyncMock(return_value={"code": 0}) for name in
                             ("preview_builtin", "preview_solid", "preview_effect", "save_effect", "set_switch_state")})
    data_class = importlib.import_module("trimlight_feature_test.data").TrimlightData
    data = data_class(api=api, coordinator=coord, store=None, debug_path="", debug_log_path="",
                      builtins=[], custom_cache=[], builtins_refreshed=True,
                      commit_custom_preset=True, debug_logging=False)
    data.last_brightness = 170
    hass = SimpleNamespace(data={"trimlight": {"test": data}})
    coord.hass = hass
    entity = cls(hass, "test", coord)
    entity._schedule_verification_refresh = Mock()
    return entity, data, api


class FeatureTests(unittest.TestCase):
    def test_api_rejection_description(self):
        with self.assertRaisesRegex(HomeAssistantError, "12006.*Access denied"):
            controls.require_success({"code": 12006, "desc": "Access denied"})
        for response in ({"code": 12006}, {"code": 12006, "desc": {}}, None):
            with self.assertRaisesRegex(HomeAssistantError, "rejected the request"):
                controls.require_success(response)
        controls.require_success({"code": 0, "desc": "success"})

    def test_error_description_redaction_and_bounds(self):
        value = controls.safe_error_description("key=secret token=token\n denied", ["secret", "token"])
        self.assertNotIn("secret", value)
        self.assertNotIn("token", value)
        self.assertNotIn("\n", value)
        self.assertEqual(len(controls.safe_error_description("x" * 500)), 240)
        self.assertEqual(controls.safe_error_description(None), "")

    async def test_rgb_replaces_effect_without_saving(self):
        entity, data, api = make_entity()
        await entity.async_turn_on(rgb_color=(255, 80, 0), brightness=123)
        api.preview_solid.assert_awaited_once_with("FF5000", 123)
        api.save_effect.assert_not_awaited()
        self.assertEqual(entity.rgb_color, (255, 80, 0))
        self.assertEqual(entity.coordinator.data["current_effect_id"], -1)
        self.assertEqual(data.last_speed, 0)

    async def test_rgb_uses_current_brightness(self):
        entity, _, api = make_entity()
        await entity.async_turn_on(rgb_color=(0, 0, 255))
        api.preview_solid.assert_awaited_once_with("0000FF", 170)

    async def test_rgb_failure_keeps_prior_effect(self):
        entity, _, api = make_entity()
        original = dict(entity.coordinator.data["current_effect"])
        api.preview_solid.return_value = {"code": 10001}
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_on(rgb_color=(0, 255, 0))
        self.assertEqual(entity.coordinator.data["current_effect"], original)
        entity._schedule_verification_refresh.assert_called_once()

    async def test_failed_power_does_not_preview_or_change_state(self):
        entity, _, api = make_entity()
        api.set_switch_state.return_value = {"code": 10002}
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_on(rgb_color=(0, 255, 0))
        api.preview_solid.assert_not_awaited()
        entity.coordinator.async_set_updated_data.assert_not_called()

    async def test_failed_off_preserves_state(self):
        entity, _, api = make_entity()
        api.set_switch_state.return_value = {"code": 10001}
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_off()
        entity.coordinator.async_set_updated_data.assert_not_called()

    async def test_preview_brightness_never_overwrites_matching_saved_preset(self):
        entity, data, api = make_entity()
        await entity.async_turn_on(rgb_color=(255, 0, 0))
        state = entity.coordinator.data
        data.custom_cache = [dict(state["current_effect"], id=10, name="Saved Red")]
        await controller.apply_effect_update(api, data, state, brightness=80)
        api.save_effect.assert_not_awaited()
        self.assertEqual(entity.coordinator.data["current_effect_id"], -1)
        self.assertEqual(entity.coordinator.data["brightness"], 80)

    async def test_length_preserves_other_parameters(self):
        entity, _, api = make_entity(number.TrimlightEffectLengthNumber)
        await entity.async_set_native_value(90)
        api.preview_builtin.assert_awaited_once_with(9, speed=42, brightness=170, pixel_len=90, reverse=False)
        self.assertEqual(entity.native_value, 90)

    async def test_reverse_preserves_other_parameters(self):
        entity, _, api = make_entity(switch.TrimlightReverseSwitch)
        await entity.async_turn_on()
        api.preview_builtin.assert_awaited_once_with(9, speed=42, brightness=170, pixel_len=35, reverse=True)
        self.assertTrue(entity.is_on)
        await entity.async_turn_off()
        self.assertFalse(entity.is_on)

    async def test_length_and_reverse_survive_subsequent_brightness(self):
        entity, data, api = make_entity()
        await controls.async_update_builtin(entity, pixel_len=55, reverse=True)
        await controller.apply_effect_update(api, data, entity.coordinator.data, brightness=99)
        self.assertEqual(api.preview_effect.await_args.args[0]["pixelLen"], 55)
        self.assertTrue(api.preview_effect.await_args.args[0]["reverse"])

    async def test_controls_reject_wrong_state_without_sending(self):
        for state, category, online in [(0, 0, True), (2, 0, True), (1, 1, True), (1, 0, False)]:
            with self.subTest(state=state, category=category, online=online):
                entity, _, api = make_entity()
                entity.coordinator.data["switch_state"] = state
                entity.coordinator.data["current_effect"]["category"] = category
                entity.coordinator.last_update_success = online
                with self.assertRaises(HomeAssistantError):
                    await controls.async_update_builtin(entity, reverse=True)
                api.preview_builtin.assert_not_awaited()

    async def test_invalid_length_rejected(self):
        for value in [0, 91, 2.5, float("nan")]:
            entity, _, api = make_entity(number.TrimlightEffectLengthNumber)
            with self.assertRaises(HomeAssistantError):
                await entity.async_set_native_value(value)
            api.preview_builtin.assert_not_awaited()

    async def test_failed_builtin_preview_does_not_publish(self):
        entity, _, api = make_entity()
        api.preview_builtin.return_value = {"code": 10001}
        with self.assertRaises(HomeAssistantError):
            await controls.async_update_builtin(entity, reverse=True)
        entity.coordinator.async_set_updated_data.assert_not_called()
        self.assertFalse(entity.coordinator.data["current_effect"]["reverse"])

    async def test_pending_preset_transition_blocks_builtin_edit(self):
        entity, data, api = make_entity()
        data.pending_transition = SimpleNamespace(expires_monotonic=float("inf"))
        self.assertFalse(controls.builtin_control_available(entity))
        with self.assertRaises(HomeAssistantError):
            await controls.async_update_builtin(entity, pixel_len=40)
        api.preview_builtin.assert_not_awaited()

    async def test_poll_rejects_api_error(self):
        api = SimpleNamespace(get_device_detail=AsyncMock(return_value={"code": 10002}))
        coord = coordinator_module.TrimlightCoordinator(None, api)
        with self.assertRaises(HomeAssistantError):
            await coord._async_update_data()

    async def test_solid_preview_sensor_label(self):
        entity, _, _ = make_entity()
        await entity.async_turn_on(rgb_color=(0, 255, 0))
        label = sensor.TrimlightCurrentPresetSensor(entity._hass, "test", entity.coordinator)
        self.assertEqual(label.native_value, "Solid Color")

    def test_rgb_not_reported_for_multicolor_disabled_or_animated_patterns(self):
        solid = {"category": 1, "mode": 0, "pixels": [{"count": 60, "color": 0x123456}]}
        self.assertEqual(controls.solid_rgb(solid), (18, 52, 86))
        for effect in [dict(solid, mode=1), dict(solid, category=0),
                       dict(solid, pixels=[{"count": 60, "color": 0, "disable": True}]),
                       dict(solid, pixels=[{"count": 1, "color": 0}, {"count": 1, "color": 255}])]:
            self.assertIsNone(controls.solid_rgb(effect))

    def test_missing_success_code_rejected(self):
        for response in [{}, {"code": None}, None]:
            with self.assertRaises(HomeAssistantError):
                controls.require_success(response)


def offline_async_test(method):
    """Drive mock-only coroutines without creating an event loop/local sockets."""
    def run(self):
        coroutine = method(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        self.fail("Offline test unexpectedly attempted real asynchronous I/O")
    return run


for name, method in list(vars(FeatureTests).items()):
    if name.startswith("test_") and inspect.iscoroutinefunction(method):
        setattr(FeatureTests, name, offline_async_test(method))


if __name__ == "__main__":
    unittest.main(verbosity=2)
