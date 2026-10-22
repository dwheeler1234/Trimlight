"""Bounded background readback for accepted daily-schedule enable writes."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)
_DELAYS = (2, 4, 8)


class DailyScheduleVerification:
    def __init__(self, hass, coordinator):
        self.hass = hass
        self.coordinator = coordinator
        self.pending = {}
        self.status = {}
        self._generation = 0
        self._handle = None
        self._task = None
        self._closed = False

    def reported(self, slot):
        rows = ((self.coordinator.data or {}).get('payload') or {}).get('daily') or []
        row = next((row for row in rows if row.get('id') == slot), None)
        return row.get('enable') if row else None

    def accept(self, slot, enabled):
        """Publish only after the API accepts the write; never retry a write."""
        if self._closed:
            return
        self._generation += 1
        self.pending[slot] = {'target': enabled, 'attempts': 0, 'generation': self._generation}
        self.status[slot] = 'pending'
        # Even if cached data already matches, require a new read after acceptance.
        self.coordinator.async_update_listeners()
        self._schedule()

    def _schedule(self):
        if self._closed or not self.pending or self._handle is not None or self._task is not None:
            return
        attempt = min(row['attempts'] for row in self.pending.values())
        self._handle = self.hass.loop.call_later(_DELAYS[min(attempt, len(_DELAYS)-1)], self._start)

    def _start(self):
        self._handle = None
        if self._closed or not self.pending:
            return
        self._task = self.hass.async_create_task(self._verify())

    async def _verify(self):
        snapshot = {slot: row['generation'] for slot, row in self.pending.items()}
        ok = False
        try:
            # Runs outside management_lock. One read verifies both slots.
            await self.coordinator.async_refresh()
            ok = self.coordinator.last_update_success
        except Exception:  # read failures must not turn an accepted write into a retry
            _LOGGER.debug('Daily schedule verification read failed', exc_info=True)
        finally:
            if not self._closed:
                for slot, generation in snapshot.items():
                    row = self.pending.get(slot)
                    if row is None or row['generation'] != generation:
                        continue
                    row['attempts'] += 1
                    if ok and self.reported(slot) is row['target']:
                        self.status[slot] = 'confirmed'
                        self.pending.pop(slot)
                    elif row['attempts'] >= len(_DELAYS):
                        self.status[slot] = 'not_confirmed' if ok else 'read_failed'
                        self.pending.pop(slot)
                        _LOGGER.warning('Daily schedule %s enable change was not confirmed after %s reads', slot + 1, len(_DELAYS))
                self.coordinator.async_update_listeners()
            self._task = None
            self._schedule()

    def close(self):
        self._closed = True
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self.pending.clear()
