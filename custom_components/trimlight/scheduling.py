"""Controller-stored schedules and combined-effect playlists."""
from __future__ import annotations

from datetime import date

from .management import ManagementController
from .pattern import bounded_int

REPETITIONS = {"today_only": 0, "everyday": 1, "weekdays": 2, "weekend": 3}
SCHEDULE_FIELDS = {
    "get_schedules": {},
    "set_daily_schedule": {"schedule_id": int, "enabled": bool, "effect_id": int,
                           "repetition": str, "start_time": dict, "end_time": dict},
    "enable_daily_schedule": {"schedule_id": int, "enabled": bool},
    "save_calendar_schedule": {"schedule_id": int, "effect_id": int, "start_date": dict,
                               "end_date": dict, "start_time": dict, "end_time": dict},
    "create_calendar_schedule": {"schedule_id": int, "effect_id": int, "start_date": dict,
                                 "end_date": dict, "start_time": dict, "end_time": dict},
    "delete_calendar_schedule": {"schedule_id": int},
    "set_playlist": {"effect_ids": list, "interval": int}, "run_playlist": {},
}


def schedule_time(value, *, reported=False) -> dict:
    # The vendor schedule-time table differs from the datetime API: preserve its
    # documented 1..24 / 1..60 ranges verbatim rather than silently adding offsets.
    if not isinstance(value, dict) or set(value) != {"hours", "minutes"}:
        raise ValueError("Schedule time requires hours and minutes")
    low = 0 if reported else 1
    return {"hours": bounded_int(value["hours"], low, 24, "Schedule hours"),
            "minutes": bounded_int(value["minutes"], low, 60, "Schedule minutes")}


def schedule_date(value) -> dict:
    if not isinstance(value, dict) or set(value) != {"month", "day"}:
        raise ValueError("Schedule date requires month and day")
    month = bounded_int(value["month"], 1, 12, "Month")
    day = bounded_int(value["day"], 1, 31, "Day")
    date(2000, month, day)  # Annual definitions may include February 29.
    return {"month": month, "day": day}


def schedule_effect(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in {*range(60), 200}:
        raise ValueError("Schedule effect must be a saved preset ID 0-59 or playlist ID 200")
    return value


def require_effect(payload: dict, eid: int) -> None:
    if eid == 200:
        if not (payload.get("combinedEffect") or {}).get("effectIds"):
            raise ValueError("Configure a combined-effect playlist before scheduling or running it")
    elif not any(p.get("id") == eid for p in payload.get("effects") or []):
        raise ValueError("The selected saved preset does not exist on this controller")


class SchedulingController(ManagementController):
    fields = SCHEDULE_FIELDS

    async def _execute(self, action, data):
        if action == "get_schedules":
            payload = await self.detail()
            return {"daily": payload.get("daily") or [], "calendar": payload.get("calendar") or [],
                    "playlist": payload.get("combinedEffect") or {}, "switch_state": payload.get("switchState")}
        if action in {"set_daily_schedule", "enable_daily_schedule"}:
            sid = bounded_int(data["schedule_id"], 0, 1, "Daily schedule ID")
            if action == "set_daily_schedule" and self.runtime.daily_verifier and sid in self.runtime.daily_verifier.pending:
                raise ValueError("Wait for this timer's enable-state verification before saving its definition")
            if not isinstance(data["enabled"], bool):
                raise ValueError("Enabled must be true or false")
            payload = await self.detail()
            if action == "enable_daily_schedule":
                saved = next((p for p in payload.get("daily") or [] if p.get("id") == sid), None)
                if saved is None:
                    raise ValueError("Define this daily schedule before enabling/disabling it")
                daily = {"id": sid, "enable": data["enabled"], "effectId": schedule_effect(saved.get("effectId")),
                         "repetition": bounded_int(saved.get("repetition"), 0, 3, "Repetition"),
                         "startTime": schedule_time(saved.get("startTime"), reported=True), "endTime": schedule_time(saved.get("endTime"), reported=True)}
            else:
                if data["repetition"] not in REPETITIONS:
                    raise ValueError("Choose today_only, everyday, weekdays, or weekend")
                daily = {"id": sid, "enable": data["enabled"], "effectId": schedule_effect(data["effect_id"]),
                         "repetition": REPETITIONS[data["repetition"]],
                         "startTime": schedule_time(data["start_time"], reported=True), "endTime": schedule_time(data["end_time"], reported=True)}
            if data["enabled"]:
                require_effect(payload, daily["effectId"])
            now = self.api._current_date_payload()
            daily["currentDate"] = {"month": now["month"], "day": now["day"]}
            result = await self.checked(self.api.save_daily_schedule(daily))
            if action == "enable_daily_schedule":
                # Return after acceptance. Do not hold management_lock during readback.
                self.runtime.daily_verifier.accept(sid, data["enabled"])
                return dict(result, confirmation_pending=True)
            return await self.refresh(result)
        if action in {"save_calendar_schedule", "create_calendar_schedule"}:
            calendar = {"id": bounded_int(data["schedule_id"], 0, 59, "Calendar slot"),
                        "effectId": schedule_effect(data["effect_id"]),
                        "startDate": schedule_date(data["start_date"]), "endDate": schedule_date(data["end_date"]),
                        "startTime": schedule_time(data["start_time"], reported=True), "endTime": schedule_time(data["end_time"], reported=True)}
            payload = await self.detail()
            if action == "create_calendar_schedule" and any(row.get("id") == calendar["id"] for row in payload.get("calendar") or []):
                raise ValueError("This calendar slot is already occupied. Refresh and create the event again.")
            require_effect(payload, calendar["effectId"])
            return await self.refresh(await self.checked(self.api.save_calendar_schedule(calendar)))
        if action == "delete_calendar_schedule":
            sid = bounded_int(data["schedule_id"], 0, 59, "Calendar slot")
            payload = await self.detail()
            if not any(p.get("id") == sid for p in payload.get("calendar") or []):
                raise ValueError("This calendar slot does not exist on the controller")
            return await self.refresh(await self.checked(self.api.delete_calendar_schedule(sid)))
        if action == "set_playlist":
            ids = data["effect_ids"]
            if not isinstance(ids, list) or not 1 <= len(ids) <= 5:
                raise ValueError("A playlist requires 1 to 5 saved preset IDs")
            ids = [schedule_effect(eid) for eid in ids]
            if 200 in ids:
                raise ValueError("A playlist cannot contain itself")
            interval = bounded_int(data["interval"], 1, 2147483647, "Interval in minutes")
            payload = await self.detail()
            for eid in ids:
                require_effect(payload, eid)
            return await self.refresh(await self.checked(self.api.save_playlist(ids, interval)))
        if action == "run_playlist":
            payload = await self.detail()
            require_effect(payload, 200)
            await self.checked(self.api.set_switch_state(1))
            self.cancel_pending()
            # Only report controller state after the API accepts the playlist.
            try:
                result = await self.checked(self.api.run_effect(200))
            except Exception:
                await self.refresh({"code": 0})
                raise
            return await self.refresh(result)
        raise ValueError("Unknown scheduling action")
