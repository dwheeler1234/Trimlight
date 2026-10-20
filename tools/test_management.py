"""Offline tests of management actions, discovery, routing, and API request shapes."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib
import importlib.util
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

import test_feature_controls as f

management = importlib.import_module("trimlight_feature_test.management")
v = importlib.import_module("trimlight_feature_test.validation")
api_mixin = importlib.import_module("trimlight_feature_test.management_api")
f.module("homeassistant.components.select", SelectEntity=type("SelectEntity", (), {}))
f.module("homeassistant.components.binary_sensor", BinarySensorEntity=type("BinarySensorEntity", (), {}),
         BinarySensorDeviceClass=SimpleNamespace(CONNECTIVITY="connectivity"))
selectors = importlib.import_module("trimlight_feature_test.select")
binary = importlib.import_module("trimlight_feature_test.binary_sensor")
diagnostics = importlib.import_module("trimlight_feature_test.diagnostics")


def runtime():
    entity, data, api = f.make_entity()
    preset = {"id": 7, "name": "Original", "category": 1, "mode": 0, "speed": 50,
              "brightness": 120, "pixels": [{"index": 0, "count": 4, "color": 255, "disable": False}]}
    data.coordinator.data.update(effects=[deepcopy(preset)], custom_effects=[deepcopy(preset)])
    data.coordinator.async_request_refresh = AsyncMock()
    data.coordinator.async_update_listeners = Mock()
    payload = {"effects": [deepcopy(preset)], "daily": [], "calendar": [], "combinedEffect": {}, "overlayEffects": []}
    api.get_device_detail = AsyncMock(return_value={"code": 0, "payload": payload})
    api.get_devices = AsyncMock(return_value={"code": 0, "payload": {"data": [
        {"deviceId": "a", "connectivity": 1}, {"deviceId": "b", "connectivity": 1}]}})
    api.get_groups = AsyncMock(return_value={"code": 0, "payload": {"data": [
        {"groupId": "g", "masterDevice": {"deviceId": "a"}}]}})
    for name in ("update_device", "delete_effect", "notify_update_shadow", "sync_datetime", "set_overlays",
                 "backup_device", "restore_backup", "group_command"):
        setattr(api, name, AsyncMock(return_value={"code": 0}))
    api.get_backup = AsyncMock(return_value={"code": 0, "payload": {"backupKey": "key", "backupTime": "stamp"}})
    api.save_effect.return_value = {"code": 0, "payload": {"id": 8}}
    return entity, data, api, management.ManagementController(data)


class ApiStub(api_mixin.ManagementApi):
    def __init__(self):
        self._creds = SimpleNamespace(device_id="controller")
        self._request = AsyncMock(return_value={"code": 0})
    def _current_date_payload(self):
        return {"year": 26, "month": 10, "day": 20}


class ManagementTests(unittest.TestCase):
    async def test_preset_rename_preserves_pixels_and_saved_id(self):
        _, data, api, manager = runtime()
        await manager.execute("rename_preset", {"effect_id": 7, "name": "Renamed"})
        effect = api.save_effect.await_args.args[0]
        self.assertEqual(effect["id"], 7)
        self.assertEqual(effect["pixels"][0]["color"], 255)
        self.assertEqual(data.custom_cache[0]["name"], "Renamed")

    async def test_duplicate_creates_new_id_without_running_lights(self):
        _, data, api, manager = runtime()
        result = await manager.execute("duplicate_preset", {"effect_id": 7, "name": "Copy"})
        self.assertEqual(api.save_effect.await_args.args[0]["id"], -1)
        self.assertEqual(result["effect_id"], 8)
        api.set_switch_state.assert_not_awaited()
        self.assertEqual({p["id"] for p in data.custom_cache}, {7, 8})

    async def test_update_preset_validates_bounds_before_writing(self):
        _, _, api, manager = runtime()
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("update_preset", {"effect_id": 7, "changes": {"speed": 256}})
        api.save_effect.assert_not_awaited()
        await manager.execute("update_preset", {"effect_id": 7, "changes": {"speed": 0, "brightness": 255}})
        self.assertEqual(api.save_effect.await_args.args[0]["speed"], 0)

    async def test_delete_checks_all_reference_types(self):
        for field, reference in [("daily", [{"effectId": 7}]), ("calendar", [{"effectId": 7}]),
                                 ("combinedEffect", {"effectIds": [7]}),
                                 ("overlayEffects", [{"targetEffect": 7}])]:
            _, _, api, manager = runtime()
            api.get_device_detail.return_value["payload"][field] = reference
            with self.assertRaises(f.HomeAssistantError):
                await manager.execute("delete_preset", {"effect_id": 7})
            api.delete_effect.assert_not_awaited()

    async def test_delete_removes_cache_only_after_success(self):
        _, data, api, manager = runtime()
        api.delete_effect.return_value = {"code": 10001}
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("delete_preset", {"effect_id": 7})
        self.assertEqual(len(data.coordinator.data["effects"]), 1)
        api.delete_effect.return_value = {"code": 0}
        await manager.execute("delete_preset", {"effect_id": 7})
        self.assertEqual(data.coordinator.data["effects"], [])

    async def test_save_rejection_or_missing_id_never_fabricates_success(self):
        for response in [{"code": 10001}, {"code": 0}]:
            _, data, api, manager = runtime()
            api.save_effect.return_value = response
            before = deepcopy(data.coordinator.data)
            with self.assertRaises(f.HomeAssistantError):
                await manager.execute("duplicate_preset", {"effect_id": 7, "name": "Copy"})
            self.assertEqual(data.coordinator.data, before)
            api.save_effect.assert_awaited_once()

    async def test_configure_maps_color_order_ic_and_ports(self):
        _, _, api, manager = runtime()
        await manager.execute("configure_controller", {"settings": {"color_order": "GRB", "ic": "DMX512",
            "ports": [{"id": 0, "start": 1, "end": 2048}]}})
        api.update_device.assert_awaited_once_with({"colorOrder": 2, "ic": 1, "ports": [{"id": 0, "start": 1, "end": 2048}]})

    def test_configure_rejects_invalid_or_duplicate_port_ranges(self):
        for settings in [{"ports": [{"id": 0, "start": 5, "end": 4}]},
                         {"ports": [{"id": 4, "start": 1, "end": 2}]},
                         {"ports": [{"id": 0, "start": 1, "end": 2}] * 2},
                         {"color_order": "OTHER"}, {"arbitrary": "field"}]:
            with self.assertRaises(ValueError):
                v.controller_settings(settings)

    async def test_overlay_targets_are_validated_and_empty_clears(self):
        _, _, api, manager = runtime()
        await manager.execute("set_overlays", {"overlays": [{"type": "snow", "effect_id": 7}]})
        api.set_overlays.assert_awaited_with([{"overlayType": 1, "targetEffect": 7}])
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("set_overlays", {"overlays": [{"type": "snow", "effect_id": 9}]})
        await manager.execute("set_overlays", {"overlays": []})
        api.set_overlays.assert_awaited_with([])

    async def test_group_operations_and_membership(self):
        _, _, api, manager = runtime()
        for action, params, expected in [
            ("create_group", {"name": "House", "master_device": "a", "devices": ["a", "b"]}, "add"),
            ("update_group", {"group_id": "g", "master_device": "a", "devices": ["a", "b"]}, "update"),
            ("rename_group", {"group_id": "g", "name": "Roof"}, "rename"),
            ("sync_group", {"group_id": "g"}, "sync"), ("delete_group", {"group_id": "g"}, "delete")]:
            await manager.execute(action, params)
            self.assertEqual(api.group_command.await_args.args[0], expected)
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("create_group", {"name": "House", "master_device": "a", "devices": ["a", "unknown"]})

    async def test_group_sync_rejects_offline_master(self):
        _, _, api, manager = runtime()
        api.get_devices.return_value["payload"]["data"][0]["connectivity"] = 0
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("sync_group", {"group_id": "g"})
        api.group_command.assert_not_awaited()

    async def test_backup_restore_requires_this_controllers_key(self):
        _, _, api, manager = runtime()
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("restore_backup", {"backup_key": "wrong"})
        api.restore_backup.assert_not_awaited()
        await manager.execute("restore_backup", {"backup_key": "key"})
        api.restore_backup.assert_awaited_once_with("key")

    async def test_backup_time_uses_requested_zone(self):
        self.assertEqual(v.backup_time("CST", datetime(2026, 10, 20, 1, tzinfo=timezone.utc)), "2026-10-19 19:00:00 CST")
        _, _, api, manager = runtime()
        await manager.execute("create_backup", {"timezone": "CDT"})
        self.assertTrue(api.backup_device.await_args.args[0].endswith(" CDT"))
        with self.assertRaises(f.HomeAssistantError):
            await manager.execute("create_backup", {"timezone": "UTC"})

    async def test_reads_live_state_clock_and_rename(self):
        _, data, api, manager = runtime()
        for action in ("list_devices", "list_groups", "get_backup", "request_live_state", "sync_clock"):
            result = await manager.execute(action, {})
            self.assertEqual(result["code"], 0)
        await manager.execute("rename_device", {"name": "Roof"})
        api.update_device.assert_awaited_with({"name": "Roof"})
        self.assertEqual(data.backup_metadata["backupKey"], "key")

    async def test_failed_refresh_does_not_report_write_failed(self):
        _, data, api, manager = runtime()
        data.coordinator.async_request_refresh.side_effect = RuntimeError("offline")
        result = await manager.execute("rename_device", {"name": "Roof"})
        self.assertTrue(result["refresh_pending"])
        api.update_device.assert_awaited_once()

    async def test_unknown_or_extra_action_fields_rejected(self):
        _, _, _, manager = runtime()
        for action, data in [("unknown", {}), ("rename_device", {}), ("rename_device", {"name": "a", "deviceId": "other"})]:
            with self.assertRaises(f.HomeAssistantError):
                await manager.execute(action, data)

    async def test_transport_endpoint_payloads(self):
        api = ApiStub()
        cases = [
            (api.update_device({"name": "Roof"}), "POST", "update", {"name": "Roof"}),
            (api.delete_effect(7), "POST", "effect/delete", {"id": 7}),
            (api.set_overlays([]), "POST", "effect/overlay", {"overlayEffects": []}),
            (api.backup_device("stamp"), "POST", "data/backup", {"backupTime": "stamp"}),
            (api.restore_backup("key"), "POST", "data/backup/restore", {"backupKey": "key"}),
        ]
        for coroutine, method, endpoint, payload in cases:
            await coroutine
            api._request.assert_awaited_with(method, "/v1/oauth/resources/device/" + endpoint,
                payload={"deviceId": "controller", "payload": payload})
        await api.notify_update_shadow()
        api._request.assert_awaited_with("GET", "/v1/oauth/resources/device/notify-update-shadow",
            payload={"deviceId": "controller", "currentDate": api._current_date_payload()})
        await api.sync_datetime()
        self.assertEqual(api._request.await_args.args, ("POST", "/v1/oauth/resources/device/datetime/sync"))
        await api.get_backup()
        api._request.assert_awaited_with("POST", "/v1/oauth/resources/device/data/backup/get", payload={"deviceId": "controller"})
        await api.get_groups()
        api._request.assert_awaited_with("GET", "/v1/oauth/resources/groups", params={"page": 0})
        for action in ("add", "update", "rename", "delete", "sync"):
            await api.group_command(action, {"groupId": "g"})
            api._request.assert_awaited_with("GET", "/v1/oauth/resources/group/" + action, payload={"groupId": "g"})

    async def test_timer_mode_does_not_claim_physical_power(self):
        entity, _, _ = f.make_entity(selectors.TrimlightOperatingModeSelect)
        await entity.async_select_option("Timer")
        self.assertEqual(entity.current_option, "Timer")
        self.assertIsNone(entity._is_effectively_on())
        sensor = f.sensor.TrimlightCurrentPresetSensor(entity._hass, "test", entity.coordinator)
        self.assertEqual(sensor.native_value, "Timer")

    def test_connectivity_distinguishes_offline_from_failed_api(self):
        entity, _, _ = f.make_entity(binary.TrimlightConnectivity)
        entity.coordinator.data["payload"] = {"connectivity": 0}
        self.assertTrue(entity.available)
        self.assertFalse(entity.is_on)
        entity.coordinator.last_update_success = False
        self.assertFalse(entity.available)

    async def test_diagnostics_omit_credentials_and_personal_fields(self):
        entity, data, _, _ = runtime()
        entity.coordinator.data["payload"] = {"name": "Private roof", "client_secret": "secret",
            "backupKey": "key", "effects": [{"name": "Private preset"}], "connectivity": 1}
        result = await diagnostics.async_get_config_entry_diagnostics(entity._hass, SimpleNamespace(entry_id="test"))
        self.assertEqual(result["saved_effect_count"], 1)
        self.assertNotIn("secret", str(result))
        self.assertNotIn("Private", str(result))
        self.assertNotIn("backupKey", str(result))

    def test_related_select_lookup_uses_this_config_entry_unique_id(self):
        entity, _, _, _ = runtime()
        lookup = Mock(return_value="select.renamed_controller_custom")
        f.module("homeassistant.helpers.entity_registry", async_get=lambda hass:SimpleNamespace(async_get_entity_id=lookup))
        entity._hass.states = SimpleNamespace(get=Mock(return_value="correct controller state"))
        self.assertEqual(entity._related_select_state("custom_select"), "correct controller state")
        lookup.assert_called_once_with("select", "trimlight", "test_custom_select")


for name, method in list(vars(ManagementTests).items()):
    if name.startswith("test_") and inspect.iscoroutinefunction(method):
        setattr(ManagementTests, name, f.offline_async_test(method))


if __name__ == "__main__":
    unittest.main(verbosity=2)
