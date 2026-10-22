# Calendar event editor

The `custom:trimlight-calendar-card` edits the controller's 60 annual calendar
slots. It is a dashboard editor, not a Home Assistant Calendar entity.

## Setup

1. Redownload Trimlight beta.24 or newer through HACS and restart Home Assistant.
2. **Add** `/trimlight/trimlight-calendar-card.js?v=0.2.0-beta.24` as a JavaScript
   module resource. Do not replace the existing timer/progress-row/control/editor resources.
3. Add a Manual card:

```yaml
type: custom:trimlight-calendar-card
title: Trimlight Calendar
entity: sensor.not_assigned_trimlight_calendar_schedules
```

The card resolves the config entry through the sensor's entity-registry record.
For restricted accounts or registry failures, set `config_entry_id` explicitly to
that controller's entry ID. Calendar writes use administrator-only actions.

## Editing

- New event selects the first free controller slot after a sensor refresh. The
  new `trimlight.create_calendar_schedule` action also checks current API data
  and rejects an occupied slot rather than replacing it.
- The event dropdown identifies saved events by month/day range, pattern and slot.
  Select one to load and edit it. Save changes that event's slot.
- Library contains saved pattern IDs 0-59 and combined playlist ID 200 when
  configured. Unsaved pattern drafts cannot be scheduled.
- Start/end dates are month/day values and repeat annually. End before start
  represents a range across New Year. Month/day validation includes leap day;
  actual execution on non-leap years is firmware-dependent and unverified.
- Start/off times use the controller clock. Normal inputs use 0-23 hours and
  0-59 minutes, including midnight and whole hours. Backend validation accepts
  zero-valued calendar fields for compatibility with ordinary clock input, just
  as for observed daily schedules; calendar execution still needs live checking.
  Unchanged device values are preserved. A `time_encoding: one_based` override
  exists only for controllers explicitly confirmed to need a +1 offset.
- Create/save refreshes sensor data first; edits with changed reported definitions
  are rejected. This is not an atomic cross-client compare-and-swap API: avoid
  editing the same slot simultaneously in the app and HA.
- Delete event opens inline confirmation. Cancel sends no delete action. Confirm
  refreshes and checks the selected reported definition before deleting it.
- Accepted saves/deletes stay pending until matching sensor data returns. While
  pending, further writes are disabled; use Refresh for another read. No writes
  are retried automatically. After a timeout, inspect the app/list before trying
  creation again because the controller may have applied the request.
- Reload event discards local edits. Refresh requests cloud data while keeping
  edited fields. Full capacity blocks new creation without changing existing slots.
- Offline and rejected actions are shown as errors. Saving does not change the
  operating mode. Use the separate Operating Mode card to select Timer mode.
  Calendar/daily precedence is controlled by Trimlight firmware, not this card.

## Backend actions

`trimlight.create_calendar_schedule` uses the same fields as
`trimlight.save_calendar_schedule` and refuses an occupied slot. The existing
save action keeps its upsert semantics for compatibility. Delete uses
`trimlight.delete_calendar_schedule`. Each requires explicit `config_entry_id`.
The calendar sensor now provides `presets` and `playlist_available` attributes.

## Validation

Simulated Edge tests cover creation into a free slot, December/January wrapping,
midnight, editing saved events, playlist selection, stale edits, delete cancel and
confirmation, invalid dates, failed writes, delayed readback, full capacity,
offline state and phone-width layout. Backend tests cover the create guard and
zero-valued times. No real controller events were created, edited or deleted.

## Saved events list

Beta.26 adds a separate read-only card in the same calendar JavaScript resource.
Update its existing URL to `/trimlight/trimlight-calendar-card.js?v=0.2.0-beta.26`;
keep the other dashboard resources and the existing calendar editor.

```yaml
type: custom:trimlight-calendar-events-card
title: Trimlight Calendar Events
entity: sensor.not_assigned_trimlight_calendar_schedules
```

The list shows controller-reported patterns (or an ID fallback), month/day ranges,
start/off times in 24-hour format, annual recurrence and ranges crossing New Year.
Slots are displayed from 1 to 60. Refresh requests a sensor update; no schedule
writes are sent. Missing/unavailable data is shown separately from an empty list.
Pending editor drafts are not included. Use the same `time_encoding` override as
the editor if the controller has been confirmed to need it.

Live issue: the user's CHRISTMAS event (October 22, 16:15–16:20) was accepted by
the API but absent from both controller readback and the app. Calendar writes
remain failing/unconfirmed; this display card does not fix that save issue.
