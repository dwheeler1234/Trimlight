"""Offline flow and service registration checks using minimal HA interfaces."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
import importlib.util
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

import test_management as m
f = m.f


class Schema:
    def __init__(self, schema):
        self.schema = schema
    def __call__(self, value):
        if set(value) != set(self.schema):
            raise ValueError("Required or unexpected action field")
        for key, kind in self.schema.items():
            if not isinstance(value[key], kind):
                raise ValueError("Incorrect field type")
        return value


f.module("voluptuous", Schema=Schema, Required=lambda key, **kwargs:key,
         Optional=lambda key, **kwargs:key, In=lambda choices:choices)


class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
    def __init__(self):
        self.hass = object()
        self.entries = []
        self.async_set_unique_id = AsyncMock()
        self._abort_if_unique_id_configured = Mock()
    def _async_current_entries(self):
        return self.entries
    def async_show_form(self, **kwargs):
        return dict(type="form", **kwargs)
    def async_abort(self, **kwargs):
        return dict(type="abort", **kwargs)
    def async_create_entry(self, **kwargs):
        return dict(type="create_entry", **kwargs)


f.module("homeassistant.config_entries", ConfigFlow=Flow, OptionsFlow=object, ConfigEntry=object)
sys.modules["homeassistant"].config_entries = sys.modules["homeassistant.config_entries"]
f.module("homeassistant.const", CONF_CLIENT_ID="client_id", CONF_CLIENT_SECRET="client_secret")
f.module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass:None)
f.module("homeassistant.util")
f.module("homeassistant.util.dt", now=lambda:datetime(2026, 10, 20, 12, tzinfo=timezone.utc))

class Credentials:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

api = SimpleNamespace(get_devices=AsyncMock(), get_device_detail=AsyncMock())
api_factory = Mock(return_value=api)
f.module("trimlight_feature_test.api", TrimlightApi=api_factory, TrimlightCredentials=Credentials)
flow_module = importlib.import_module("trimlight_feature_test.config_flow")
sys.modules["homeassistant.core"].SupportsResponse = SimpleNamespace(OPTIONAL="optional")
f.module("homeassistant.helpers.service", async_register_admin_service=lambda hass, domain, action, handler, **kwargs:
         hass.services.records.update({action: (handler, kwargs, True)}))
services = importlib.import_module("trimlight_feature_test.services")


class DiscoveryTests(unittest.TestCase):
    async def test_discovery_offers_account_devices_and_validates_selection(self):
        api.get_devices.return_value = {"code":0, "payload":{"data":[{"deviceId":"a", "name":"Roof"}, {"deviceId":"b", "name":"Garage"}]}}
        api.get_device_detail.return_value = {"code":0, "payload":{"name":"Roof"}}
        flow = flow_module.TrimlightConfigFlow()
        result = await flow.async_step_user({"client_id":"user", "client_secret":"secret"})
        self.assertEqual(result["step_id"], "device")
        result = await flow.async_step_device({"device_id":"a"})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["device_id"], "a")
        flow.async_set_unique_id.assert_awaited_once_with("a")

    async def test_manual_device_path_and_duplicate_prevention(self):
        api.get_device_detail.return_value = {"code":0, "payload":{"name":"Roof"}}
        api.get_devices.reset_mock()
        flow = flow_module.TrimlightConfigFlow()
        result = await flow.async_step_user({"client_id":"user", "client_secret":"secret", "device_id":"a"})
        self.assertEqual(result["type"], "create_entry")
        api.get_devices.assert_not_awaited()
        flow.entries = [SimpleNamespace(data={"device_id":"a"})]
        result = await flow.async_step_user({"client_id":"user", "client_secret":"secret", "device_id":"a"})
        self.assertEqual(result["reason"], "already_configured")

    async def test_empty_discovery_and_api_error_remain_in_form(self):
        for result, error in [({"code":0, "payload":{"data":[]}}, "no_devices"), ({"code":10002}, "cannot_connect")]:
            api.get_devices.return_value = result
            flow = flow_module.TrimlightConfigFlow()
            response = await flow.async_step_user({"client_id":"user", "client_secret":"secret"})
            self.assertEqual(response["errors"]["base"], error)

    async def test_manual_detail_error_does_not_create_entry(self):
        api.get_device_detail.return_value = {"code":10002}
        flow = flow_module.TrimlightConfigFlow()
        response = await flow.async_step_user({"client_id":"user", "client_secret":"secret", "device_id":"a"})
        self.assertEqual(response["type"], "form")

    async def test_service_registration_routing_and_unloaded_entry(self):
        _, runtime, runtime_api, _ = m.runtime()
        records = {}
        registry = SimpleNamespace(records=records, async_register=lambda domain, action, handler, **kwargs: records.update({action:(handler, kwargs, False)}))
        hass = SimpleNamespace(services=registry, data={"trimlight":{"entry":runtime}})
        services.register_services(hass)
        self.assertEqual(set(records), set(m.management.ACTION_FIELDS))
        handler, config, admin_only = records["rename_device"]
        self.assertTrue(admin_only)
        params = config["schema"]({"config_entry_id":"entry", "name":"Roof"})
        response = await handler(SimpleNamespace(data=params, return_response=True))
        self.assertEqual(response["code"], 0)
        runtime_api.update_device.assert_awaited_with({"name":"Roof"})
        with self.assertRaises(f.HomeAssistantError):
            await handler(SimpleNamespace(data={"config_entry_id":"unloaded", "name":"Roof"}, return_response=False))
        self.assertFalse(records["list_devices"][2])
        with self.assertRaises(ValueError):
            config["schema"]({"config_entry_id":"entry", "name":"Roof", "device_id":"other"})

    async def test_actual_api_clock_uses_injected_timezone(self):
        class ClientResponseError(Exception):
            pass
        f.module("aiohttp", ClientSession=object, ClientResponseError=ClientResponseError, ContentTypeError=type("ContentTypeError", (Exception,), {}))
        f.module("async_timeout")
        path = Path(__file__).parents[1] / "custom_components/trimlight/api.py"
        spec = importlib.util.spec_from_file_location("trimlight_feature_test.clock_api", path)
        actual_api = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = actual_api
        spec.loader.exec_module(actual_api)
        clock = lambda:datetime(2026, 10, 20, 12, 15, 1, tzinfo=timezone.utc)
        instance = actual_api.TrimlightApi(None, actual_api.TrimlightCredentials("u", "s", "d"), clock=clock)
        self.assertEqual(instance._current_date_payload(), {"year":26, "month":10, "day":20, "weekday":3, "hours":12, "minutes":15, "seconds":1})

    async def test_scheduling_registration_uses_explicit_entry_and_admin_writes(self):
        scheduling = importlib.import_module("trimlight_feature_test.scheduling")
        _, runtime, _, _ = m.runtime()
        records = {}
        registry = SimpleNamespace(records=records, async_register=lambda domain, action, handler, **kwargs: records.update({action:(handler, kwargs, False)}))
        hass = SimpleNamespace(services=registry, data={"trimlight":{"entry":runtime}})
        services.register_action_set(hass, scheduling.SCHEDULE_FIELDS, scheduling.SchedulingController, {"get_schedules", "run_playlist"})
        self.assertEqual(set(records), set(scheduling.SCHEDULE_FIELDS))
        self.assertTrue(records["set_daily_schedule"][2])
        self.assertFalse(records["get_schedules"][2])
        result = await records["get_schedules"][0](SimpleNamespace(data={"config_entry_id":"entry"}, return_response=True))
        self.assertEqual(result["daily"], [])


for name, method in list(vars(DiscoveryTests).items()):
    if name.startswith("test_") and inspect.iscoroutinefunction(method):
        setattr(DiscoveryTests, name, f.offline_async_test(method))

if __name__ == "__main__":
    unittest.main(verbosity=2)
