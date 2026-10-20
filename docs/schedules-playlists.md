# Controller schedules and playlists

This branch is stacked on controller management, which is stacked on the color
and pattern-editor branch. Install the full integration from this branch and
restart Home Assistant. The custom card JavaScript does not need changing.

The controller stores these schedules, so Home Assistant does not need to fire
each individual scheduled transition. The controller/cloud still require working
configuration. Saving a schedule does not turn the lights on or change the
controller's operating mode. Select **Timer** in **Trimlight Operating Mode** when
you want controller schedules to take control.

## Native entities

- **Daily Schedule 1** and **Daily Schedule 2** switches enable/disable the matching
  controller slot while preserving its reported times, effect and repetition.
- **Daily Schedules** sensor counts definitions and exposes them in `schedules`.
- **Calendar Schedules** sensor counts annual definitions and exposes them in
  `schedules`. It is a configuration sensor, not a Home Assistant Calendar entity.
- **Playlist** sensor reports the number of combined effects, with `effect_ids`
  and `interval_minutes` attributes. Its count does not mean it is currently running.

## Actions

Each action requires the explicit `config_entry_id` from the integration-entry
picker in **Developer Tools > Actions**. Schedule configuration writes require an
administrator. Reading schedules and running an existing playlist use normal
service permissions. Optional `response_variable` receives the result.

| Action | Additional fields |
| --- | --- |
| `trimlight.get_schedules` | None; returns daily/calendar/playlist configuration |
| `trimlight.set_daily_schedule` | `schedule_id` 0 or 1, `enabled`, `effect_id`, `repetition`, `start_time`, `end_time` |
| `trimlight.enable_daily_schedule` | `schedule_id`, `enabled` |
| `trimlight.save_calendar_schedule` | `schedule_id` 0-59, `effect_id`, `start_date`, `end_date`, `start_time`, `end_time` |
| `trimlight.delete_calendar_schedule` | `schedule_id` 0-59 |
| `trimlight.set_playlist` | `effect_ids` (1-5 saved IDs), `interval` (positive minutes) |
| `trimlight.run_playlist` | None; enters Manual mode and runs fixed combined-effect ID 200 |

### Daily schedules

```yaml
action: trimlight.set_daily_schedule
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  schedule_id: 0
  enabled: true
  effect_id: 7
  repetition: weekend
  start_time: {hours: 18, minutes: 1}
  end_time: {hours: 23, minutes: 59}
```

Repetition values: `today_only`, `everyday`, `weekdays`, `weekend`. Enabled effects
must exist on the controller. Use `effect_id: 200` for a configured combined-effect
playlist. Disabling an existing daily definition is allowed even if its former
effect was deleted; enabling it requires a valid saved effect again.

### Important vendor time-format ambiguity

The reference's schedule-time table explicitly gives **hours 1-24, minutes 1-60**,
while its controller-clock table uses **hours 0-23, minutes 0-59**. It does not
explain an offset or how those schedule values map to ordinary wall time. New
schedule actions therefore accept the documented raw schedule objects, do not
silently add/subtract one, and reject values outside the published schedule
bounds. The example above sends the shown values verbatim; it is not a guarantee
of an interpreted civil time. Confirm behavior in the Trimlight app/controller
before enabling a new schedule. This is why the actions use object fields rather
than a misleading Home Assistant time picker.

Enable/disable actions preserve existing controller-reported times, including
zero fields, without reinterpreting them. The daily request's `currentDate` uses
Home Assistant's configured timezone and the documented month/day format.
No next-run calculation or inferred physical power state is fabricated.

### Calendar schedules

```yaml
action: trimlight.save_calendar_schedule
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  schedule_id: 3
  effect_id: 7
  start_date: {month: 12, day: 20}
  end_date: {month: 1, day: 2}
  start_time: {hours: 18, minutes: 1}
  end_time: {hours: 23, minutes: 59}
```

Calendar schedules are annual month/day ranges. A range may wrap from December
into January. Dates must be real calendar dates, with February 29 allowed for an
annual definition. Saving an occupied slot replaces it; select the slot
intentionally. Up to 60 slots (0-59) are supported. Overnight time ordering is not
rejected locally, but its runtime semantics still need controller verification.

### Combined-effect playlists

```yaml
action: trimlight.set_playlist
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  effect_ids: [7, 8, 9]
  interval: 5
```

This stores the playlist without starting it. Each ID must identify a saved
effect, not a built-in preview mode. There may be 1-5 entries; repeated saved
effects are allowed, and the playlist cannot contain itself (200). Use
`trimlight.run_playlist` to start it manually, or refer to 200 from a daily or
calendar schedule. Manual playback cancels old preset-reapply callbacks so they
cannot replace the requested playlist.

## Validation

`python tools/test_scheduling.py` checks payloads, limits, dates/year wrapping,
effect references, failed writes, manual playback, and preservation on enable/
disable. Existing feature, pattern, management and discovery suites remain
applicable. These are offline tests with mock HA interfaces/API responses.
Controller compatibility, schedule-time interpretation, and full Home Assistant
loading remain unverified; no physical device commands were sent during development.
