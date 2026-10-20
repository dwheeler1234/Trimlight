"""Downloadable diagnostics without account credentials or backup restore keys."""
from copy import deepcopy

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data[DOMAIN][entry.entry_id]
    raw = (runtime.coordinator.data or {}).get("payload") or {}
    payload = {key: deepcopy(raw[key]) for key in (
        "connectivity", "switchState", "state", "colorOrder", "ic", "ports", "fwVersionName",
        "currentDatetime", "currentEffect", "effects", "daily", "calendar", "overlayEffects",
    ) if key in raw}
    # Preset names and colors may be personal; diagnostics need counts and technical state only.
    effects = payload.pop("effects", [])
    current = payload.get("currentEffect")
    if isinstance(current, dict):
        current.pop("name", None)
        current.pop("pixels", None)
    for key in ("daily", "calendar", "overlayEffects"):
        value = payload.get(key)
        if isinstance(value, list):
            payload[key] = {"count": len(value)}
    return {"controller": payload, "saved_effect_count": len(effects),
            "last_update_success": runtime.coordinator.last_update_success,
            "backup_available": bool(runtime.backup_metadata.get("backupKey"))}
