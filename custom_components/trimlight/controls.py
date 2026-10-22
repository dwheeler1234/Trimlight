"""Validated effect controls shared by the light, number and switch platforms."""
from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError


def safe_error_description(value: object, sensitive_values=()) -> str:
    """Keep a short, single-line server explanation without request credentials."""
    if not isinstance(value, str):
        return ""
    for secret in sorted({str(v) for v in sensitive_values if v}, key=len, reverse=True):
        value = value.replace(secret, "[redacted]")
    return " ".join(value.split())[:240]


def require_success(response: dict[str, Any]) -> None:
    """Reject API errors (which are returned with HTTP 200 as well)."""
    if not isinstance(response, dict) or response.get("code") != 0:
        code = response.get("code") if isinstance(response, dict) else None
        description = safe_error_description(response.get("desc")) if isinstance(response, dict) else ""
        suffix = f": {description}" if description else ""
        raise HomeAssistantError(f"Trimlight rejected the request (code {code}){suffix}")


def solid_rgb(effect: dict[str, Any]) -> tuple[int, int, int] | None:
    """Return a color only for a static custom pattern with one enabled color."""
    if effect.get("category") not in (1, 2) or effect.get("mode") != 0:
        return None
    pixels = effect.get("pixels") or []
    active = [p for p in pixels if p.get("count", 0) > 0]
    if not active or any(p.get("disable", False) for p in active):
        return None
    colors = {p.get("color") for p in active}
    if len(colors) != 1:
        return None
    color = colors.pop()
    if not isinstance(color, int) or not 0 <= color <= 0xFFFFFF:
        return None
    return (color >> 16, (color >> 8) & 255, color & 255)


def builtin_control_available(entity) -> bool:
    """Only edit a settled built-in effect running in manual mode."""
    state = entity.coordinator.data or {}
    return (
        entity.coordinator.last_update_success
        and state.get("switch_state") == 1
        and (state.get("current_effect") or {}).get("category") == 0
        and entity._active_pending_transition() is None
    )


async def async_update_builtin(entity, *, pixel_len: int | None = None, reverse: bool | None = None) -> None:
    """Preview a built-in parameter change without altering a saved preset."""
    if not builtin_control_available(entity):
        raise HomeAssistantError("Select a built-in preset in manual mode before changing its parameters")
    state = entity.coordinator.data or {}
    effect = dict(state.get("current_effect") or {})
    if effect.get("mode") is None:
        raise HomeAssistantError("The controller has not reported the built-in effect mode")
    if pixel_len is not None:
        if not 1 <= pixel_len <= 90:
            raise HomeAssistantError("Effect length must be between 1 and 90")
        effect["pixelLen"] = pixel_len
    if reverse is not None:
        effect["reverse"] = reverse
    runtime = entity._data
    response = await runtime.api.preview_builtin(
        effect["mode"],
        speed=effect.get("speed", runtime.last_speed),
        brightness=effect.get("brightness", runtime.last_brightness),
        pixel_len=effect.get("pixelLen", 30),
        reverse=effect.get("reverse", False),
    )
    require_success(response)
    entity._cancel_pending_followups()
    effect["id"] = -1
    updated = dict(state)
    updated.update(current_effect=effect, current_effect_id=-1, current_effect_category=0)
    entity.coordinator.async_set_updated_data(updated)
    entity._schedule_verification_refresh()
