# Two daily timer editor

The [Trimlight daily schedule tutorial](https://www.youtube.com/watch?v=wJmcU61zu84&t=132s)
shows two independent daily schedules, each with enable, repetition, Library,
start/off times and Save. The `custom:trimlight-timer-card` mirrors that workflow
using the controller's two daily slots (UI Timer 1/2 map to API IDs 0/1).
The reference was reviewed visually at its Daily Schedule chapter; video audio
and full transcript were not used as proof of API encoding.

## Install

1. Redownload the integration through HACS and restart Home Assistant (beta.19 or newer).
2. Add `/trimlight/trimlight-timer-card.js?v=0.2.0-beta.19` as a **JavaScript module**
   resource. Keep the pattern-editor and compact-control resources as separate entries.
3. Add a Manual dashboard card:

```yaml
type: custom:trimlight-timer-card
title: Trimlight Timers
entity: sensor.not_assigned_trimlight_daily_schedules
```

The operating mode entity is inferred from the sensor prefix. For renamed
sensors, provide `operating_mode_entity: select.YOUR_OPERATING_MODE`.
The card resolves the sensor's Trimlight config entry through HA's entity registry.
If your account cannot read it, provide `config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID`
explicitly. Use the same controller as the configured sensor and mode entity.
Schedule writes use the existing admin-only action, so the user must be an administrator.

## Use

- Each timer has Enabled, Today only / Every day / Weekdays / Weekend, a saved
  pattern or configured combined-effect playlist, Start time, Off time and Save.
- Only saved controller presets (IDs 0-59) and a configured playlist (ID 200)
  can be scheduled; unsaved pattern-editor drafts are not schedule definitions.
- Editing Enabled is local until **Save Timer 1/2** is pressed. Each save changes
  that timer only. Errors retain the edited values; writes are not retried automatically.
- **Reload timer** discards that timer's unsaved edits and reloads the latest
  sensor data. It does not issue a new cloud read. Incoming HA updates preserve
  edited forms. A changed controller definition blocks saving until reloaded.
- **Use Timer mode** is a separate explicit action. Saving never changes the
  operating mode. Existing calendar schedules may also affect Timer-mode behavior.
- Times follow the controller's clock. These timers are stored on the controller;
  they are not Home Assistant automation triggers. Check correct execution in the
  Trimlight app after the first save, particularly across midnight.

## Time compatibility

The older PDF says schedule hours 1-24 and minutes 1-60. Actual controller data
provided by the user reports Timer 1 at `{hours:19,minutes:0}` to
`{hours:22,minutes:30}` and Timer 2 at `{hours:0,minutes:2}` to
`{hours:0,minutes:3}`. The daily-save action now accepts zero values, preserving
raw reported values up to the existing documented 24/60 bounds for compatibility.
Calendar validation is unchanged.

By default, HTML clock inputs use 0-23 hours and 0-59 minutes and send those
values without offset. Unchanged fields reuse the original reported values.
`time_encoding: one_based` is an explicit compatibility override for a controller
confirmed to encode both fields with a +1 offset; the card never infers that
conversion from positive values alone. Do not select this override without
confirming the app/controller mapping. Unsupported reported clock values are not
silently clamped. We have validated payloads and UI behavior in simulation, not
physical execution times on this controller.

## Validation

Backend tests cover midnight/whole-hour payloads and saved preset choices.
Headless Edge tests use the reported schedules, independently save Timer 2,
check midnight, repetition, playlist selection, dirty-form preservation, stale
edit rejection, failed saves, explicit Timer-mode selection, offline behavior and
phone-width layout. They send no commands to the user's controller.

## Separate timer cards

Use the same resource for both cards and add `timer: 1` or `timer: 2` to their
YAML. Titles default to Trimlight Timer 1 / Trimlight Timer 2, and each instance
edits and saves only that timer. You can position them independently on your
dashboard. The Use Timer mode buttons both affect the same controller mode.
An existing configuration without `timer` continues to show both forms.
