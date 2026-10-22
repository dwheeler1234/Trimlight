# Feature status register

Baseline: `main`, integration `0.2.0-beta.14`, reviewed 2026-10-22.

This is the authoritative feature inventory. Implementation and live validation are separate.
Automated checks use mocked HA/API or simulated browser state; they do not establish hardware success.
No feature is marked live verified merely because its PR merged.

## Status values

- Implementation: **Implemented**, **In progress**, **Backlog**, **Blocked**.
- Validation: **Not tested**, **Automated**, **Observed**, **Verified**, **Retest needed**, **Failing**, **Not applicable**.
- **Observed** means an entity/UI/value was seen, without full end-to-end verification.
- **Verified** requires explicit user/device evidence; **Retest needed** means the latest relevant change needs live confirmation.

Tracking checklist: [GitHub issue #17](https://github.com/dwheeler1234/Trimlight/issues/17).

## Working process

1. Pick an ID below and open a **Feature status / test report** issue.
2. Record installed version, resource URL, HA version, firmware, browser/device, steps and actual result.
3. Link the issue and feature ID in the fix PR. Update this register in the same PR.
4. After merging, use **Retest needed**, not **Verified**, until the user confirms the installed build.
5. On confirmation, update the row and link the issue/evidence. Check the corresponding tracking-issue item.
6. Reopen failures with **Failing**; close a test issue only after acceptance or a documented decision.

Priority retests: iPhone scrolling, X dragging, zero-count colors, Security pattern loading at 76/49/56, saved-pattern dropdown population.
Schedule writes also need vendor time-format confirmation. Port bounds need comparison with the app.

## Installation and connection

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-001 | HACS custom repository installation | Implemented | Observed | User installed integration and bundled card. |
| TL-002 | HACS updates and beta versioning | Implemented | Observed | Updates published through beta.14; latest phone behavior needs confirmation. |
| TL-003 | Bundled JavaScript card and static URL | Implemented | Verified | User screenshot and working editor. |
| TL-004 | Credentials and manual device ID setup | Implemented | Observed | Controller telemetry received; earlier connection failure not conclusively diagnosed. |
| TL-005 | Account controller discovery | Implemented | Not tested | Leave device ID blank; test discovery and selection. |
| TL-006 | Duplicate controller prevention | Implemented | Not tested | Test duplicate setup rejection. |
| TL-007 | Multiple controllers and explicit action targeting | Implemented | Not tested | Check isolation and renamed/suffixed entities. |
| TL-008 | Polling and API error handling | Implemented | Observed | Connectivity and controller clock observed; error/recovery paths need testing. |
| TL-009 | Home Assistant timezone in date payloads | Implemented | Not tested | Verify controller clock after sync. |
| TL-010 | Local preset cache and refresh button | Implemented | Not tested | Check refresh, restart persistence, and stale entries. |

## Lighting and native controls

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-011 | Power on/off | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |
| TL-012 | Brightness | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |
| TL-013 | Temporary solid RGB color | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |
| TL-014 | Built-in preset selection | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |
| TL-015 | Saved custom preset selection | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |
| TL-016 | Custom effect mode selection | Implemented | Not tested | Verify supported modes. |
| TL-017 | Effect speed slider | Implemented | Not tested | Value observed; physical effect not confirmed. |
| TL-018 | Built-in effect length | Implemented | Not tested | 1-90; requires suitable active built-in effect. |
| TL-019 | Reverse animation | Implemented | Not tested | Requires suitable active built-in effect. |
| TL-020 | Off/Manual/Timer mode selector | Implemented | Verified | User confirmed all Operating Mode controls (Off, Manual, Timer) work on 2026-10-22; recorded in tracking issue #17. |
| TL-021 | Current preset tracking and Timer unknown-power handling | Implemented | Observed | Timer state observed; transitions need testing. |

## Pattern editor

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-022 | 30-slot draft and expanded/collapsed grid | Implemented | Observed | Editor works with user entity overrides. |
| TL-023 | New drafts with black slot colors | Implemented | Retest needed | Added beta.12; restart/New required. |
| TL-024 | Per-slot light counts 0-99 | Implemented | Retest needed | beta.13 fixes PDF limit; Security counts 76/49/56 tested offline. |
| TL-025 | Stored colors visible at zero count | Implemented | Retest needed | beta.11; confirm on device. |
| TL-026 | RGB color editing by palette click | Implemented | Verified | User confirmed clicking slot then color changes color. |
| TL-027 | Fixed palette colors including warm white/black | Implemented | Observed | RGB approximations; no dedicated white channel. |
| TL-028 | 16 editable custom palette colors and browser persistence | Implemented | Not tested | Two custom row-2 slots at right, plus rows 3/4. |
| TL-029 | Three visible palette rows and expandable fourth row | Implemented | Observed | Confirm expanded state on phone. |
| TL-030 | Click slot to open count dialog | Implemented | Retest needed | Restored beta.9; browser test passes. |
| TL-031 | Color drag-and-drop onto slot | Implemented | Retest needed | Earlier failures fixed; later live success not explicitly confirmed. |
| TL-032 | Color drops preserve zero and populated counts | Implemented | Retest needed | beta.10; browser test passes. |
| TL-033 | Click X to disable selected slot | Implemented | Verified | User explicitly confirmed this works. |
| TL-034 | Drag X to disable a target slot | Implemented | Retest needed | Pointer-based fix beta.8; browser test passes. |
| TL-035 | Pattern source dropdown combines live/cached saved custom patterns | Implemented | Retest needed | beta.12; built-ins lack editable pixel definitions. |
| TL-036 | Load saved pattern colors/counts/mode/speed/brightness | Implemented | Retest needed | Security loading hit 60 limit; beta.13 raises to 99. |
| TL-037 | Load current pattern button | Implemented | Not tested | Loads a local copy without running lights. |
| TL-038 | Pattern animation dropdown (17 modes) | Implemented | Not tested | Verify all modes supported by firmware. |
| TL-039 | Pattern brightness and speed sliders | Implemented | Not tested | Test draft and explicit preview behavior. |
| TL-040 | New button prompts for pattern name | Implemented | Not tested | Confirm cancel and validation. |
| TL-041 | Save New prompts for name and saves separate preset | Implemented | Not tested | No overwrite; verify controller copy and returned ID. |
| TL-042 | Preview draft on controller | Implemented | Not tested | Requires explicit button; verify physical output. |
| TL-043 | Theme backgrounds and responsive layout | Implemented | Observed | Screenshot shows themed card; verify dark/light/phone widths. |
| TL-044 | Entity ID overrides | Implemented | Verified | User confirmed not_assigned_trimlight overrides work. |
| TL-045 | iPhone touch scroll containment on controls | Implemented | Retest needed | beta.14; actual iPhone verification outstanding. |
| TL-046 | Draft isolation from saved presets and other controllers | Implemented | Not tested | Drafts are in memory; restart/reload resets them. |

## Controller and preset management actions

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-047 | List account controllers | Implemented | Not tested | trimlight.list_devices |
| TL-048 | Rename controller | Implemented | Not tested | trimlight.rename_device |
| TL-049 | Configure RGB color order | Implemented | Not tested | trimlight.configure_controller |
| TL-050 | Configure IC type | Implemented | Not tested | UCS1903/DMX512; verify firmware. |
| TL-051 | Configure port ranges | Implemented | Not tested | API range implementation needs comparison with app port limits. |
| TL-052 | Rename preset | Implemented | Not tested | trimlight.rename_preset |
| TL-053 | Duplicate preset | Implemented | Not tested | trimlight.duplicate_preset |
| TL-054 | Update saved preset | Implemented | Not tested | trimlight.update_preset |
| TL-055 | Delete preset and reference checks | Implemented | Not tested | Check daily/calendar/playlist/overlay references. |
| TL-056 | Lightning/snow overlays and clear assignments | Implemented | Not tested | trimlight.set_overlays; firmware dependent. |
| TL-057 | Request fresh cloud shadow | Implemented | Not tested | Button/action; documented GET with JSON body needs hardware check. |
| TL-058 | Controller clock synchronization | Implemented | Not tested | trimlight.sync_clock |
| TL-059 | Create cloud backup | Implemented | Not tested | trimlight.create_backup |
| TL-060 | Read backup metadata | Implemented | Not tested | trimlight.get_backup |
| TL-061 | Restore matching controller backup | Implemented | Not tested | trimlight.restore_backup; controlled hardware validation required. |

## Groups

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-062 | List groups | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |
| TL-063 | Create group | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |
| TL-064 | Update group membership/master | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |
| TL-065 | Rename group | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |
| TL-066 | Delete group | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |
| TL-067 | Synchronize group | Implemented | Not tested | Native account group action; GET-with-body compatibility needs hardware testing. |

## Schedules and playlists

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-068 | Read daily/calendar/playlist configuration | Implemented | Observed | Sensors show two daily schedules, zero calendar schedules and two playlist entries. |
| TL-069 | Create/update daily schedule | Implemented | Not tested | Two slots; vendor schedule-time interpretation unresolved. |
| TL-070 | Enable/disable daily schedule switches/actions | Implemented | Observed | On/off values reported; actual toggle writes unverified. |
| TL-071 | Create/update annual calendar schedule | Implemented | Not tested | 60 slots; month/day and year-wrap validation. |
| TL-072 | Delete calendar schedule | Implemented | Not tested | trimlight.delete_calendar_schedule |
| TL-073 | Configure combined-effect playlist | Implemented | Not tested | 1-5 saved effects and interval in minutes. |
| TL-074 | Run combined-effect playlist | Implemented | Not tested | Manual mode, fixed ID 200. |
| TL-075 | Schedule/playlist configuration sensors | Implemented | Observed | Reported configuration seen; not proof of execution. |

## Diagnostics and developer support

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-076 | Cloud connectivity sensor | Implemented | Verified | User confirmed Status card readings work on 2026-10-22; tracking issue #17. |
| TL-077 | Firmware sensor | Implemented | Verified | User confirmed Status card readings work on 2026-10-22; tracking issue #17. |
| TL-078 | Controller state sensor | Implemented | Verified | User confirmed Status card readings work on 2026-10-22; tracking issue #17. |
| TL-079 | Controller clock sensor | Implemented | Verified | User confirmed Status card readings work on 2026-10-22; tracking issue #17. |
| TL-080 | Redacted downloadable diagnostics | Implemented | Not tested | Allowlist; inspect actual download before sharing. |
| TL-081 | Optional structured debug logging | Implemented | Not tested | Redact user logs before attaching issues. |
| TL-082 | Explicit config-entry actions and admin restrictions | Implemented | Not tested | Service registration tested offline; real permissions require testing. |
| TL-083 | Offline backend regression suite | Implemented | Automated | Mock HA/API tests; not full HA installation testing. |
| TL-084 | Native browser drag/count regression suite | Implemented | Automated | Headless Edge with simulated HA; not iPhone/device execution. |
| TL-085 | Standalone simulated preview builder | Implemented | Automated | Preview is simulated; use actual HA for acceptance. |

## Backlog and gaps

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-086 | Automatic card resource registration | Backlog | Not applicable | Resource is still a one-time manual setup. |
| TL-087 | Automatic controller/entity resolution in card | Backlog | Not applicable | Current workaround uses entity overrides. |
| TL-088 | Persist unsaved editor drafts across restart | Backlog | Not applicable | Current drafts reset on reload/restart. |
| TL-089 | Native Home Assistant Calendar entity | Backlog | Not applicable | Current calendar support is actions and sensors. |
| TL-090 | Local LAN control | Backlog | Not applicable | Current transport is Trimlight cloud. |
| TL-091 | Independent port/zone light entities | Backlog | Not applicable | Port configuration does not create independently addressable lights. |


## Compact control card

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-092 | Separate compact control card: power, horizontal brightness, RGB picker, shared palette and combined saved/built-in pattern dropdown | Implemented | Verified | User confirmed all compact control card features work on 2026-10-22: power, horizontal brightness, RGB picker/palette and saved/built-in pattern selection; tracking issue #17. |

## Integration update status

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-093 | Trimlight update status entity (HACS) | Implemented | Verified | User confirmed the Trimlight update indicator (`update.trimlight_update`) works on 2026-10-22. This tracks integration updates, not controller firmware installation; tracking issue #17. |

## Control card expansion

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-094 | Control card one-row palette expands to all four rows | Implemented | Retest needed | beta.16; Edge verifies 7 collapsed/28 expanded slots. Earlier control-card features remain verified under TL-092. |
| TL-095 | Control card Effect dropdown, Effect Speed slider and Reverse Animation toggle | Implemented | Retest needed | beta.17 removes Length from this card. Simulated Edge verifies remaining controls and no Length slider. Needs physical-controller/iPhone acceptance; the native Length entity remains available separately (TL-018). |

## Two daily timer editor

| ID | Feature | Implementation | Validation | Evidence / next check |
| --- | --- | --- | --- | --- |
| TL-096 | Timer editor cards: individual Timer 1/2 or combined view, enable, repetition, saved pattern/playlist, start/off times, save/reload and explicit Timer mode | Implemented | Retest needed | beta.20: user reported enabling failed after Save. Enabled now writes immediately; actual readback is shown, with pending/error feedback and Refresh controller. Simulated tests pass; live enable/execution retest needed. |
| TL-097 | Daily timer midnight and whole-hour compatibility | Implemented | Retest needed | Accept and preserve zero-valued hours/minutes reported by the user's controller, without automatic offset. Calendar raw bounds unchanged. Backend payload tests pass. |
