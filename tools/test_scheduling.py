"""Offline schedule/playlist validation, service routing and transport tests."""
from copy import deepcopy
import importlib
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from pathlib import Path
import json
import re

import test_management as m
f = m.f
scheduling = importlib.import_module("trimlight_feature_test.scheduling")
switch = importlib.import_module("trimlight_feature_test.switch")


def setup():
    entity, runtime, api, _ = m.runtime()
    payload = api.get_device_detail.return_value["payload"]
    payload.update(daily=[{"id":0, "enable":True, "effectId":7, "repetition":1,
                          "startTime":{"hours":10,"minutes":1}, "endTime":{"hours":11,"minutes":1}}],
                   calendar=[{"id":0,"effectId":7}], combinedEffect={"effectIds":[7],"interval":5})
    api._current_date_payload = lambda:{"year":26,"month":10,"day":20}
    for name in ("save_daily_schedule", "save_calendar_schedule", "delete_calendar_schedule", "save_playlist", "run_effect"):
        setattr(api, name, AsyncMock(return_value={"code":0}))
    runtime.daily_verifier = Mock(pending={}, status={})
    return entity, runtime, api, scheduling.SchedulingController(runtime)


class ScheduleTests(unittest.TestCase):
    def test_daily_sensor_exposes_saved_pattern_choices_and_playlist(self):
        entity, runtime, api, _ = setup()
        entity.coordinator.data = {"payload": api.get_device_detail.return_value["payload"]}
        sensor = f.sensor.TrimlightScheduleSensor(entity._hass, "test", entity.coordinator, "daily", "Daily Schedules")
        attrs = sensor.extra_state_attributes
        self.assertTrue(attrs["playlist_available"])
        self.assertIn(7, [p["id"] for p in attrs["presets"]])
        self.assertNotIn("pixels", attrs["presets"][0])
        attrs["schedules"][0]["enable"] = False
        self.assertTrue(entity.coordinator.data["payload"]["daily"][0]["enable"])

    async def test_daily_payload_includes_local_current_date(self):
        _, _, api, controller = setup()
        await controller.execute("set_daily_schedule", {"schedule_id":1,"enabled":True,"effect_id":7,
            "repetition":"weekend","start_time":{"hours":22,"minutes":15},"end_time":{"hours":6,"minutes":30}})
        api.save_daily_schedule.assert_awaited_once_with({"id":1,"enable":True,"effectId":7,"repetition":3,
            "startTime":{"hours":22,"minutes":15},"endTime":{"hours":6,"minutes":30},"currentDate":{"month":10,"day":20}})
        api.set_switch_state.assert_not_awaited()

    async def test_daily_allows_midnight_and_whole_hours_verbatim(self):
        _, _, api, controller = setup()
        await controller.execute("set_daily_schedule", {"schedule_id":0,"enabled":True,"effect_id":7,
            "repetition":"everyday","start_time":{"hours":19,"minutes":0},"end_time":{"hours":0,"minutes":0}})
        saved = api.save_daily_schedule.await_args.args[0]
        self.assertEqual(saved["startTime"], {"hours":19,"minutes":0})
        self.assertEqual(saved["endTime"], {"hours":0,"minutes":0})
        api.set_switch_state.assert_not_awaited()

    async def test_toggle_preserves_existing_controller_times_even_zero(self):
        _, _, api, controller = setup()
        payload = api.get_device_detail.return_value["payload"]
        payload["daily"][0]["startTime"] = {"hours":0,"minutes":0}
        await controller.execute("enable_daily_schedule", {"schedule_id":0,"enabled":False})
        saved = api.save_daily_schedule.await_args.args[0]
        self.assertFalse(saved["enable"])
        self.assertEqual(saved["startTime"], {"hours":0,"minutes":0})
        self.assertEqual(saved["effectId"], 7)

    async def test_daily_rejects_bad_slot_boolean_and_new_time(self):
        for changed in [{"schedule_id":2}, {"enabled":1}, {"start_time":{"hours":25,"minutes":0}},
                        {"repetition":"weekly"}, {"effect_id":199}]:
            _, _, api, controller = setup()
            data = {"schedule_id":0,"enabled":True,"effect_id":7,"repetition":"everyday",
                    "start_time":{"hours":10,"minutes":1},"end_time":{"hours":11,"minutes":1}}
            data.update(changed)
            with self.assertRaises(f.HomeAssistantError):
                await controller.execute("set_daily_schedule", data)
            api.save_daily_schedule.assert_not_awaited()

    async def test_enabling_missing_effect_rejected_disabling_allowed(self):
        _, _, api, controller = setup()
        api.get_device_detail.return_value["payload"]["daily"][0]["effectId"] = 9
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("enable_daily_schedule", {"schedule_id":0,"enabled":True})
        await controller.execute("enable_daily_schedule", {"schedule_id":0,"enabled":False})
        api.save_daily_schedule.assert_awaited_once()

    async def test_toggle_returns_after_acceptance_without_blocking_readback(self):
        _, runtime, api, controller = setup()
        result = await controller.execute("enable_daily_schedule", {"schedule_id":0,"enabled":False})
        self.assertTrue(result["confirmation_pending"])
        api.get_device_detail.assert_awaited_once()
        api.save_daily_schedule.assert_awaited_once()
        runtime.coordinator.async_request_refresh.assert_not_awaited()
        runtime.daily_verifier.accept.assert_called_once_with(0, False)
        self.assertFalse(runtime.management_lock.locked())

    async def test_rejected_toggle_never_publishes_pending_state(self):
        _, runtime, api, controller = setup()
        api.save_daily_schedule.return_value = {"code":10001}
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("enable_daily_schedule", {"schedule_id":0,"enabled":False})
        runtime.daily_verifier.accept.assert_not_called()

    async def test_full_save_cannot_overwrite_pending_enable_state(self):
        _, runtime, api, controller = setup()
        runtime.daily_verifier.pending = {0: {"target": True}}
        with self.assertRaisesRegex(f.HomeAssistantError, "enable-state verification"):
            await controller.execute("set_daily_schedule", {"schedule_id":0,"enabled":False,"effect_id":7,
                "repetition":"everyday","start_time":{"hours":19,"minutes":0},"end_time":{"hours":22,"minutes":30}})
        api.get_device_detail.assert_not_awaited()
        api.save_daily_schedule.assert_not_awaited()

    async def test_calendar_allows_year_wrap_and_playlist_id(self):
        _, _, api, controller = setup()
        await controller.execute("save_calendar_schedule", {"schedule_id":59,"effect_id":200,
            "start_date":{"month":12,"day":31},"end_date":{"month":1,"day":1},
            "start_time":{"hours":18,"minutes":1},"end_time":{"hours":23,"minutes":59}})
        saved = api.save_calendar_schedule.await_args.args[0]
        self.assertEqual(saved["id"], 59)
        self.assertEqual(saved["effectId"], 200)
        api.set_switch_state.assert_not_awaited()

    def test_calendar_dates_validate_real_days_and_leap_day(self):
        self.assertEqual(scheduling.schedule_date({"month":2,"day":29}), {"month":2,"day":29})
        for value in [{"month":2,"day":30}, {"month":4,"day":31}, {"month":13,"day":1}, {"month":1}]:
            with self.assertRaises(ValueError):
                scheduling.schedule_date(value)

    async def test_calendar_delete_requires_existing_slot(self):
        _, _, api, controller = setup()
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("delete_calendar_schedule", {"schedule_id":1})
        api.delete_calendar_schedule.assert_not_awaited()
        await controller.execute("delete_calendar_schedule", {"schedule_id":0})
        api.delete_calendar_schedule.assert_awaited_once_with(0)

    async def test_playlist_limits_and_existing_presets(self):
        _, _, api, controller = setup()
        await controller.execute("set_playlist", {"effect_ids":[7],"interval":5})
        api.save_playlist.assert_awaited_once_with([7], 5)
        for ids, interval in [([],5), ([7]*6,5), ([200],5), ([9],5), ([True],5), ([7],0)]:
            with self.assertRaises(f.HomeAssistantError):
                await controller.execute("set_playlist", {"effect_ids":ids,"interval":interval})
        self.assertEqual(api.save_playlist.await_count, 1)

    async def test_run_playlist_uses_id_200_and_cancels_prior_reapply(self):
        _, runtime, api, controller = setup()
        handle = Mock()
        runtime.custom_reapply_handle = handle
        await controller.execute("run_playlist", {})
        api.set_switch_state.assert_awaited_once_with(1)
        api.run_effect.assert_awaited_once_with(200)
        handle.cancel.assert_called_once()
        self.assertIsNone(runtime.custom_reapply_handle)

    async def test_unconfigured_playlist_cannot_run_or_be_scheduled(self):
        _, _, api, controller = setup()
        api.get_device_detail.return_value["payload"]["combinedEffect"] = {}
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("run_playlist", {})
        api.set_switch_state.assert_not_awaited()

    async def test_schedule_rejection_does_not_publish_success(self):
        _, runtime, api, controller = setup()
        before = deepcopy(runtime.coordinator.data)
        api.save_playlist.return_value = {"code":10001}
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("set_playlist", {"effect_ids":[7],"interval":5})
        self.assertEqual(runtime.coordinator.data, before)
        runtime.coordinator.async_request_refresh.assert_not_awaited()

    async def test_run_failure_refreshes_after_accepted_power_change(self):
        _, runtime, api, controller = setup()
        api.run_effect.return_value = {"code":10001}
        with self.assertRaises(f.HomeAssistantError):
            await controller.execute("run_playlist", {})
        runtime.coordinator.async_request_refresh.assert_awaited_once()

    async def test_read_schedules_returns_data_without_writes(self):
        _, _, api, controller = setup()
        result = await controller.execute("get_schedules", {})
        self.assertEqual(len(result["daily"]), 1)
        self.assertEqual(result["playlist"]["effectIds"], [7])
        api.save_daily_schedule.assert_not_awaited()

    async def test_schedule_transport_payloads(self):
        api = m.ApiStub()
        for coroutine, path, payload in [
            (api.save_daily_schedule({"id":0}), "daily/save", {"id":0}),
            (api.save_calendar_schedule({"id":59}), "calendar/save", {"id":59}),
            (api.delete_calendar_schedule(3), "calendar/delete", {"id":3}),
            (api.save_playlist([7], 5), "combined-effect/save", {"effectIds":[7],"interval":5})]:
            await coroutine
            api._request.assert_awaited_with("POST", "/v1/oauth/resources/device/" + path,
                payload={"deviceId":"controller","payload":payload})

    async def test_native_daily_switch_routes_to_existing_schedule(self):
        entity, runtime, api, _ = setup()
        runtime.coordinator.data["payload"] = deepcopy(api.get_device_detail.return_value["payload"])
        control = switch.TrimlightDailyScheduleSwitch(entity._hass, "test", runtime.coordinator, 0)
        self.assertTrue(control.is_on)
        await control.async_turn_off()
        self.assertFalse(api.save_daily_schedule.await_args.args[0]["enable"])

    def test_action_metadata_matches_registration(self):
        root = Path(__file__).parents[1] / "custom_components/trimlight"
        descriptions = json.loads((root / "strings.json").read_text())["services"]
        fields = {**m.management.ACTION_FIELDS, **scheduling.SCHEDULE_FIELDS}
        yaml_actions = set(re.findall(r"^([a-z_]+):$", (root / "services.yaml").read_text(), re.M))
        self.assertEqual(yaml_actions, set(fields))
        self.assertEqual(set(descriptions), set(fields))
        for action, params in fields.items():
            self.assertEqual(set(descriptions[action]["fields"]), {"config_entry_id", *params})


for name, method in list(vars(ScheduleTests).items()):
    if name.startswith("test_") and inspect.iscoroutinefunction(method):
        setattr(ScheduleTests, name, f.offline_async_test(method))

if __name__ == "__main__":
    unittest.main(verbosity=2)
