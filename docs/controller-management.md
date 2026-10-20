# Controller management

This branch extends the color/pattern-editor branch. Install the full integration
from this branch, restart Home Assistant, and keep the existing dashboard resource.
These capabilities use the documented EDGE cloud API; they do not provide local
LAN control or independently addressable port/zone light entities.

## Native controls and diagnostics

- **Operating Mode** select: Off, Manual, Timer. Timer enables controller schedules;
  its physical light power is unknown because the API returns the last effect
  even outside scheduled hours. The current-preset sensor reports `Timer`.
- **Connectivity** binary sensor: online/offline according to the cloud payload.
- **Firmware**, **Controller State**, and **Controller Clock** sensors. State is
  Normal or Upgrading. The clock is controller wall time, not a UTC timestamp.
- **Request Live State** button asks the controller to update its cloud shadow,
  refreshes, and schedules the existing verification read. Reporting is asynchronous;
  the immediate response is not proof of fresh physical state.
- Downloadable diagnostics omit credentials, device/preset names, pixel colors,
  and backup restore keys. Preset tracking uses the actual registered entities for
  each config entry, including renamed/suffixed entities.

During setup, leave Device ID blank to select a controller from the account list.
Manual device IDs remain supported. Duplicate controllers are rejected.
Date/time API payloads use Home Assistant's configured timezone.

## Actions

Find the `Trimlight` actions in **Developer Tools > Actions**. Each action requires
`config_entry_id`, selected with the integration-entry picker. There is no default
controller, so adding another controller does not redirect existing automations.
Configuration-writing actions require an administrator; list/get actions,
live-state requests, and group synchronization use normal service permissions.
All actions can optionally return their API result with `response_variable`.
Nonzero API codes raise an error instead of returning a successful action.

| Action | Additional fields |
| --- | --- |
| `trimlight.list_devices` | None; returns all account controllers |
| `trimlight.list_groups` | None; returns all native account groups |
| `trimlight.rename_device` | `name` |
| `trimlight.configure_controller` | `settings` object, described below |
| `trimlight.rename_preset` | `effect_id`, `name` |
| `trimlight.duplicate_preset` | `effect_id`, `name`; saves a new ID |
| `trimlight.update_preset` | `effect_id`, `changes` object |
| `trimlight.delete_preset` | `effect_id` |
| `trimlight.request_live_state` | None |
| `trimlight.sync_clock` | None |
| `trimlight.set_overlays` | `overlays` list; replaces all assignments |
| `trimlight.create_group` | `name`, `master_device`, `devices` list |
| `trimlight.update_group` | `group_id`, `master_device`, `devices` list |
| `trimlight.rename_group` | `group_id`, `name` |
| `trimlight.delete_group` | `group_id` |
| `trimlight.sync_group` | `group_id`; the master must be online |
| `trimlight.create_backup` | `timezone` abbreviation |
| `trimlight.get_backup` | None; returns `payload.backupKey` and `payload.backupTime` |
| `trimlight.restore_backup` | `backup_key`; must match this controller's current backup |

### Controller settings

```yaml
action: trimlight.configure_controller
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  settings:
    color_order: GRB
    ic: UCS1903
    ports:
      - id: 0
        start: 1
        end: 1024
```

Provide any of `color_order`, `ic`, `ports`. Color orders: RGB, RBG, GRB, GBR,
BRG, BGR. ICs: UCS1903, DMX512. Ports use unique IDs 0-3 and start/end 1-2048,
with start no greater than end. Only supplied settings are changed.

### Preset editing

```yaml
action: trimlight.update_preset
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  effect_id: 7
  changes:
    name: Evening
    speed: 100
    brightness: 180
```

Supported fields are `name`, `mode`, `speed`, `brightness`, and either built-in
`pixelLen`/`reverse` or custom `pixels`. Speed/brightness are 0-255. Custom pixels
use the documented `index`, `count`, `color`, `disable` fields and modes 0-16.
Preset edits validate a fresh saved definition before writing it. Renaming/editing
does not intentionally run the effect. Duplicate creates a copy, and errors or
missing returned IDs never create a fabricated local preset. At most 60 saved
effects are supported. Deletion is rejected while the preset is referenced by a
daily/calendar schedule, combined-effect playlist, or overlay; remove references first.
The API does not promise transactionality against simultaneous app edits.

### Overlays and groups

```yaml
action: trimlight.set_overlays
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  overlays:
    - type: snow
      effect_id: 7
```

Overlay types are `lightning` and `snow`; targets must be saved effect IDs.
Use `overlays: []` to clear all overlays. These assignments require API/firmware
support for the API 1.4 endpoint.

Groups are native Trimlight groups, separate from Home Assistant light groups.
Their device IDs must belong to the configured account; membership must include
the master and may not contain duplicates. The reference uses GET requests with
JSON bodies for group mutations and shadow updates; compatibility through proxies
and physical controllers still requires testing.

### Backup and restore

```yaml
action: trimlight.create_backup
data:
  config_entry_id: YOUR_TRIMLIGHT_ENTRY_ID
  timezone: CDT
```

Backup timezone labels are HST, AKST, PST, MST, CST, EST, HDT, AKDT, PDT, MDT, CDT,
EDT. The backup timestamp is converted to the fixed UTC offset represented by the
selected abbreviation; choose the correct seasonal label. Backup creation is a
controller/cloud request, not a downloaded full JSON export. `get_backup` returns
the current restore key and timestamp. Restore checks that key against the same
controller's current backup metadata before issuing the restore request.

Writes are not automatically retried. After a timeout or an accepted save with
no new ID, refresh before retrying to avoid duplicate writes. A read failure after
a successful settings write returns `refresh_pending: true`; it does not falsely
report that the accepted write failed.

## Validation status

Run the existing feature/pattern suites plus `python tools/test_management.py` and
`python tools/test_discovery_services.py`. They test actual action/validation/flow
code with mocked Home Assistant interfaces and API transport; they do not establish
physical-controller compatibility or full Home Assistant loading. No controller
commands are executed by these tests. Hardware testing is needed before merging.
