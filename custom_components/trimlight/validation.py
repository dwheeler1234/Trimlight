"""Strict validation of user-facing controller operations, independent of HA."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from .pattern import PatternDraft, bounded_int

COLOR_ORDERS = {"RGB": 0, "RBG": 1, "GRB": 2, "GBR": 3, "BRG": 4, "BGR": 5}
IC_TYPES = {"UCS1903": 0, "DMX512": 1}
SWITCH_MODES = {"Off": 0, "Manual": 1, "Timer": 2}
BACKUP_ZONES = {"HST": -10, "AKST": -9, "PST": -8, "MST": -7, "CST": -6, "EST": -5,
                "HDT": -9, "AKDT": -8, "PDT": -7, "MDT": -6, "CDT": -5, "EDT": -4}


def text(value, label="Name", maximum=64) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{label} must contain 1 to {maximum} characters")
    return value.strip()


def effect_id(value) -> int:
    return bounded_int(value, 0, 59, "Saved effect ID")


def controller_settings(data: dict) -> dict:
    allowed = {"color_order", "ic", "ports"}
    if not data or set(data) - allowed:
        raise ValueError("Provide color_order, ic, or ports")
    result = {}
    if "color_order" in data:
        if not isinstance(data["color_order"], str) or data["color_order"] not in COLOR_ORDERS:
            raise ValueError("Unknown color order")
        result["colorOrder"] = COLOR_ORDERS[data["color_order"]]
    if "ic" in data:
        if not isinstance(data["ic"], str) or data["ic"] not in IC_TYPES:
            raise ValueError("Unknown controller IC")
        result["ic"] = IC_TYPES[data["ic"]]
    if "ports" in data:
        ports = data["ports"]
        if not isinstance(ports, list) or not 1 <= len(ports) <= 4:
            raise ValueError("Provide 1 to 4 port definitions")
        result["ports"] = []
        seen = set()
        for port in ports:
            if not isinstance(port, dict) or set(port) != {"id", "start", "end"}:
                raise ValueError("Each port requires id, start and end")
            pid = bounded_int(port["id"], 0, 3, "Port ID")
            start = bounded_int(port["start"], 1, 2048, "Start pixel")
            end = bounded_int(port["end"], 1, 2048, "End pixel")
            if pid in seen or start > end:
                raise ValueError("Port IDs must be unique and start must not exceed end")
            seen.add(pid)
            result["ports"].append({"id": pid, "start": start, "end": end})
    return result


def patched_effect(original: dict, changes: dict, *, duplicate=False) -> dict:
    allowed = {"name", "mode", "speed", "brightness", "pixelLen", "reverse", "pixels"}
    if not isinstance(changes, dict) or not changes or set(changes) - allowed:
        raise ValueError("Provide supported preset fields only")
    updated = deepcopy(original)
    updated.update(deepcopy(changes))
    updated["name"] = text(updated.get("name"))
    category = updated.get("category")
    for field in ("speed", "brightness"):
        updated[field] = bounded_int(updated.get(field), 0, 255, field)
    if category == 0:
        updated["mode"] = bounded_int(updated.get("mode"), 0, 179, "Built-in mode")
        updated["pixelLen"] = bounded_int(updated.get("pixelLen"), 1, 90, "Effect length")
        if not isinstance(updated.get("reverse"), bool):
            raise ValueError("Reverse must be true or false")
        if "pixels" in changes:
            raise ValueError("Built-in effects do not accept a custom pixel map")
    elif category in (1, 2):
        if {"pixelLen", "reverse"} & set(changes):
            raise ValueError("Custom effects use pixels and mode instead of pixelLen/reverse")
        # Validates bounds, unique indexes, and the existence of an enabled entry.
        PatternDraft.from_effect(updated).effect()
    else:
        raise ValueError("Unsupported effect category")
    updated["id"] = -1 if duplicate else effect_id(original.get("id"))
    return updated


def group_members(master, devices) -> dict:
    master = text(master, "Master device ID", 256)
    if not isinstance(devices, list) or not devices:
        raise ValueError("Provide a nonempty list of device IDs")
    devices = [text(device, "Device ID", 256) for device in devices]
    if master not in devices or len(devices) != len(set(devices)):
        raise ValueError("Group devices must be unique and include the master")
    return {"masterDevice": master, "devices": devices}


def overlays(value) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Overlays must be a list (use [] to remove all)")
    result = []
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {"type", "effect_id"} or not isinstance(row["type"], str) or row["type"] not in {"lightning", "snow"}:
            raise ValueError("Each overlay requires type lightning/snow and effect_id")
        target = effect_id(row["effect_id"])
        pair = (row["type"], target)
        if pair in seen:
            raise ValueError("Duplicate overlay")
        seen.add(pair)
        result.append({"overlayType": 0 if row["type"] == "lightning" else 1, "targetEffect": target})
    return result


def backup_time(zone: str, now: datetime) -> str:
    if zone not in BACKUP_ZONES:
        raise ValueError("Choose a documented backup timezone abbreviation")
    if now.tzinfo is None:
        raise ValueError("Backup clock must include a timezone")
    local = now.astimezone(timezone(timedelta(hours=BACKUP_ZONES[zone])))
    return local.strftime("%Y-%m-%d %H:%M:%S ") + zone
