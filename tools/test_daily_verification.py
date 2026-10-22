"""Offline bounded readback tests; never sends commands to a controller."""
import importlib
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
import test_feature_controls as f

verification = importlib.import_module('trimlight_feature_test.daily_verification')


def setup():
    entity, runtime, api = f.make_entity()
    coordinator = runtime.coordinator
    coordinator.data['payload'] = {'daily':[{'id':0,'enable':False},{'id':1,'enable':False}]}
    coordinator.async_update_listeners = Mock()
    coordinator.async_refresh = AsyncMock()
    handles = []
    def call_later(delay, callback):
        handle = Mock(delay=delay, callback=callback)
        handles.append(handle)
        return handle
    hass = SimpleNamespace(loop=SimpleNamespace(call_later=call_later), async_create_task=Mock())
    helper = verification.DailyScheduleVerification(hass, coordinator)
    runtime.daily_verifier = helper
    return entity, helper, coordinator, handles


async def step(helper):
    if helper._handle is not None:
        helper._handle.cancel()
        helper._handle = None
    await helper._verify()


class VerificationTests(unittest.TestCase):
    async def test_accept_is_pending_even_if_old_cache_matches_and_one_read_confirms_both(self):
        _, helper, coordinator, handles = setup()
        helper.accept(0, False)
        helper.accept(1, True)
        self.assertEqual(len(handles), 1)
        self.assertEqual(handles[0].delay, 2)
        self.assertEqual(helper.status[0], 'pending')
        self.assertEqual(helper.status[1], 'pending')
        coordinator.async_refresh.assert_not_awaited()
        coordinator.data['payload']['daily'][1]['enable'] = True
        await step(helper)
        coordinator.async_refresh.assert_awaited_once()
        self.assertEqual(helper.status, {0:'confirmed',1:'confirmed'})
        self.assertFalse(helper.pending)
        self.assertIsNone(helper._handle)

    async def test_stale_reads_stop_after_three_and_revert_switch_to_reported(self):
        entity, helper, coordinator, handles = setup()
        control = f.switch.TrimlightDailyScheduleSwitch(entity._hass, 'test', coordinator, 0)
        helper.accept(0, True)
        self.assertTrue(control.is_on)
        self.assertTrue(control.assumed_state)
        self.assertFalse(control.extra_state_attributes['reported_enabled'])
        for _ in range(3):
            await step(helper)
        self.assertEqual([h.delay for h in handles], [2,4,8])
        self.assertEqual(coordinator.async_refresh.await_count, 3)
        self.assertFalse(helper.pending)
        self.assertFalse(control.is_on)
        self.assertFalse(control.assumed_state)
        self.assertEqual(control.extra_state_attributes['verification_status'], 'not_confirmed')
        self.assertIsNone(helper._handle)

    async def test_failed_reads_stop_and_mark_read_failed(self):
        _, helper, coordinator, _ = setup()
        coordinator.async_refresh.side_effect = RuntimeError('cloud unavailable')
        helper.accept(0, True)
        for _ in range(3):
            await step(helper)
        self.assertEqual(helper.status[0], 'read_failed')
        self.assertFalse(helper.pending)

    async def test_newer_toggle_survives_an_inflight_older_read(self):
        _, helper, coordinator, _ = setup()
        helper.accept(0, True)
        async def during_read():
            helper.accept(0, False)
        coordinator.async_refresh.side_effect = during_read
        await step(helper)
        self.assertFalse(helper.pending[0]['target'])
        self.assertEqual(helper.pending[0]['attempts'], 0)
        coordinator.async_refresh.side_effect = None
        await step(helper)
        self.assertEqual(helper.status[0], 'confirmed')

    def test_timer_callback_starts_background_refresh_task(self):
        _, helper, _, handles = setup()
        helper.accept(0, True)
        handles[0].callback()
        helper.hass.async_create_task.assert_called_once()
        coroutine = helper.hass.async_create_task.call_args.args[0]
        self.assertIsNotNone(helper._task)
        helper.close()
        coroutine.close()

    def test_unload_cancels_timer_and_task_and_prevents_rescheduling(self):
        _, helper, _, handles = setup()
        helper.accept(0, True)
        task = Mock()
        helper._task = task
        helper.close()
        handles[0].cancel.assert_called_once()
        task.cancel.assert_called_once()
        self.assertFalse(helper.pending)
        helper.accept(1, True)
        self.assertFalse(helper.pending)
        self.assertEqual(len(handles), 1)


for name, method in list(vars(VerificationTests).items()):
    if name.startswith('test_') and inspect.iscoroutinefunction(method):
        setattr(VerificationTests, name, f.offline_async_test(method))

if __name__ == '__main__':
    unittest.main(verbosity=2)
