"""Offline checks for HACS packaging and asynchronous static registration."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]

class FrontendTests(unittest.TestCase):
    def test_download_contains_card_and_serves_it_without_cloud_access(self):
        modules = {}
        for name in ('homeassistant', 'homeassistant.components', 'homeassistant.components.http', 'homeassistant.core'):
            modules[name] = ModuleType(name)
        modules['homeassistant.core'].HomeAssistant = object
        modules['homeassistant.components.http'].StaticPathConfig = lambda url, path, cache: SimpleNamespace(url_path=url, path=path, cache_headers=cache)
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('trimlight_frontend_test', ROOT/'custom_components/trimlight/frontend.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = AsyncMock()
            coro = module.async_setup_frontend(SimpleNamespace(http=SimpleNamespace(async_register_static_paths=register)))
            with self.assertRaises(StopIteration):
                coro.send(None)
            configs = register.call_args.args[0]
            self.assertEqual(len(configs), 4)
            self.assertEqual({c.url_path for c in configs}, {
                '/trimlight/trimlight-pattern-card.js', '/trimlight/trimlight-control-card.js',
                '/trimlight/trimlight-timer-card.js', '/trimlight/trimlight-schedule-row.js'})
            for registered in configs:
                self.assertEqual(Path(registered.path).read_bytes(), (ROOT/'www'/Path(registered.path).name).read_bytes())
            config = configs[0]
            self.assertEqual(config.url_path, '/trimlight/trimlight-pattern-card.js')
            self.assertFalse(config.cache_headers)
            self.assertEqual(Path(config.path).read_bytes(), (ROOT/'www/trimlight-pattern-card.js').read_bytes())
            self.assertIn('custom_components/trimlight/frontend', Path(config.path).as_posix())

    def test_http_dependency_and_setup_before_authentication(self):
        manifest = json.loads((ROOT/'custom_components/trimlight/manifest.json').read_text())
        self.assertIn('http', manifest['dependencies'])
        source = (ROOT/'custom_components/trimlight/__init__.py').read_text()
        setup = source[source.index('async def async_setup('):source.index('async def async_setup_entry(')]
        self.assertIn('await async_setup_frontend(hass)', setup)
        self.assertNotIn('get_device_detail', setup)

if __name__ == '__main__':
    unittest.main()
