"""Validated controller/account actions. No network calls occur until an action is invoked."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from homeassistant.exceptions import HomeAssistantError

from .controls import require_success
from .const import build_builtin_presets_from_effects
from . import validation as v

# Required fields and their broad types. Detailed bounds and relationships are checked below.
ACTION_FIELDS = {
    "list_devices": {}, "list_groups": {}, "get_backup": {}, "request_live_state": {}, "sync_clock": {},
    "rename_device": {"name": str}, "configure_controller": {"settings": dict},
    "rename_preset": {"effect_id": int, "name": str},
    "duplicate_preset": {"effect_id": int, "name": str},
    "update_preset": {"effect_id": int, "changes": dict}, "delete_preset": {"effect_id": int},
    "set_overlays": {"overlays": list}, "create_backup": {"timezone": str},
    "restore_backup": {"backup_key": str},
    "create_group": {"name": str, "master_device": str, "devices": list},
    "update_group": {"group_id": str, "master_device": str, "devices": list},
    "rename_group": {"group_id": str, "name": str}, "delete_group": {"group_id": str},
    "sync_group": {"group_id": str},
}
READ_ACTIONS = {"list_devices", "list_groups", "get_backup"}


class ManagementController:
    def __init__(self, runtime):
        self.runtime = runtime
        self.api = runtime.api

    async def checked(self, awaitable) -> dict:
        result = await awaitable
        require_success(result)
        return result

    async def detail(self) -> dict:
        result = await self.checked(self.api.get_device_detail())
        payload = result.get("payload")
        if not isinstance(payload, dict) or not payload:
            raise HomeAssistantError("The controller returned no device details")
        return payload

    async def refresh(self, result: dict) -> dict:
        try:
            await self.runtime.coordinator.async_request_refresh()
        except Exception:
            # The write already succeeded. Do not turn a failed read into a retryable write error.
            result = dict(result, refresh_pending=True)
        return result

    def publish_effect(self, effect: dict | None, deleted_id: int | None = None) -> None:
        state = dict(self.runtime.coordinator.data or {})
        target = deleted_id if effect is None else effect["id"]
        for field in ("effects", "custom_effects"):
            rows = [p for p in (state.get(field) or []) if p.get("id") != target]
            if effect is not None and (field == "effects" or effect.get("category") in (1, 2)):
                rows.append(deepcopy(effect))
            state[field] = rows
        self.runtime.custom_cache = deepcopy(state["custom_effects"])
        if effect is not None and effect.get("category") == 0:
            self.runtime.builtins = build_builtin_presets_from_effects(state["effects"])
        self.runtime.coordinator.async_set_updated_data(state)

    async def execute(self, action: str, data: dict) -> dict:
        if action not in ACTION_FIELDS:
            raise HomeAssistantError("Unknown Trimlight action")
        if set(data) != set(ACTION_FIELDS[action]):
            raise HomeAssistantError("Provide exactly the fields documented for this action")
        try:
            async with self.runtime.management_lock:
                return await self._execute(action, data)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def _execute(self, action: str, data: dict) -> dict:
        if action == "list_devices":
            return await self.checked(self.api.get_devices(page=0))
        if action == "list_groups":
            return await self.checked(self.api.get_groups(page=0))
        if action == "get_backup":
            result = await self.checked(self.api.get_backup())
            self.runtime.backup_metadata = deepcopy(result.get("payload") or {})
            self.runtime.coordinator.async_update_listeners()
            return result
        if action == "request_live_state":
            return await self.refresh(await self.checked(self.api.notify_update_shadow()))
        if action == "sync_clock":
            return await self.refresh(await self.checked(self.api.sync_datetime()))
        if action == "rename_device":
            result = await self.checked(self.api.update_device({"name": v.text(data["name"])}))
            return await self.refresh(result)
        if action == "configure_controller":
            result = await self.checked(self.api.update_device(v.controller_settings(data["settings"])))
            return await self.refresh(result)
        if action == "create_backup":
            stamp = v.backup_time(data["timezone"], datetime.now(timezone.utc))
            return await self.checked(self.api.backup_device(stamp))
        if action == "restore_backup":
            key = v.text(data["backup_key"], "Backup key", 1024)
            backup = await self.checked(self.api.get_backup())
            if (backup.get("payload") or {}).get("backupKey") != key:
                raise ValueError("The backup key does not match this controller's current backup")
            return await self.refresh(await self.checked(self.api.restore_backup(key)))
        if action in {"rename_preset", "duplicate_preset", "update_preset", "delete_preset"}:
            eid = v.effect_id(data["effect_id"])
            payload = await self.detail()
            original = next((p for p in payload.get("effects", []) if p.get("id") == eid), None)
            if original is None:
                raise ValueError("The saved preset ID does not exist on this controller")
            if action == "delete_preset":
                referenced = any(p.get("effectId") == eid for p in payload.get("daily", []) + payload.get("calendar", []))
                referenced |= eid in (payload.get("combinedEffect") or {}).get("effectIds", [])
                referenced |= any(p.get("targetEffect") == eid for p in payload.get("overlayEffects", []))
                if referenced:
                    raise ValueError("Remove this preset from schedules, playlists and overlays before deleting it")
                result = await self.checked(self.api.delete_effect(eid))
                self.publish_effect(None, deleted_id=eid)
                return result
            duplicate = action == "duplicate_preset"
            changes = data["changes"] if action == "update_preset" else {"name": data["name"]}
            effect = v.patched_effect(original, changes, duplicate=duplicate)
            if duplicate and len(payload.get("effects") or []) >= 60:
                raise ValueError("The controller already stores 60 presets")
            result = await self.checked(self.api.save_effect(effect, effect["brightness"], speed=effect["speed"]))
            if duplicate:
                saved_id = (result.get("payload") or {}).get("id")
                if isinstance(saved_id, bool) or not isinstance(saved_id, int) or not 0 <= saved_id <= 59:
                    raise HomeAssistantError("Save accepted without a valid new ID; refresh before retrying to avoid duplicate copies")
                effect = dict(effect, id=saved_id)
            self.publish_effect(effect)
            return dict(result, effect_id=effect["id"])
        if action == "set_overlays":
            overlays = v.overlays(data["overlays"])
            if overlays:
                payload = await self.detail()
                saved_ids = {p.get("id") for p in payload.get("effects", [])}
                if any(row["targetEffect"] not in saved_ids for row in overlays):
                    raise ValueError("Overlay targets must be saved presets on this controller")
            return await self.refresh(await self.checked(self.api.set_overlays(overlays)))
        if action in {"create_group", "update_group", "rename_group", "delete_group", "sync_group"}:
            params = {}
            if action != "create_group":
                params["groupId"] = v.text(data["group_id"], "Group ID", 256)
                groups = await self.checked(self.api.get_groups(page=0))
                group = next((g for g in (groups.get("payload") or {}).get("data", [])
                              if g.get("groupId") == params["groupId"]), None)
                if group is None:
                    raise ValueError("The group does not exist in this Trimlight account")
                if action == "sync_group":
                    devices = await self.checked(self.api.get_devices(page=0))
                    master = (group.get("masterDevice") or {}).get("deviceId")
                    if not any(d.get("deviceId") == master and d.get("connectivity") == 1
                               for d in (devices.get("payload") or {}).get("data", [])):
                        raise ValueError("The group's master controller must be online")
            if action in {"create_group", "rename_group"}:
                params["name"] = v.text(data["name"])
            if action in {"create_group", "update_group"}:
                params.update(v.group_members(data["master_device"], data["devices"]))
                account = await self.checked(self.api.get_devices(page=0))
                known = {p.get("deviceId") for p in (account.get("payload") or {}).get("data", [])}
                if not set(params["devices"]) <= known:
                    raise ValueError("Group members must belong to this Trimlight account")
            operation = {"create_group": "add", "update_group": "update", "rename_group": "rename",
                         "delete_group": "delete", "sync_group": "sync"}[action]
            return await self.checked(self.api.group_command(operation, params))
        raise HomeAssistantError("Action is not implemented")
