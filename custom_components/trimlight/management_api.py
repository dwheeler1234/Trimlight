"""Documented EDGE 1.3/1.4 endpoints beyond basic light control."""
from __future__ import annotations


class ManagementApi:
    async def save_daily_schedule(self, schedule: dict) -> dict:
        return await self._device_command("daily/save", schedule)

    async def save_calendar_schedule(self, schedule: dict) -> dict:
        return await self._device_command("calendar/save", schedule)

    async def delete_calendar_schedule(self, schedule_id: int) -> dict:
        return await self._device_command("calendar/delete", {"id": schedule_id})

    async def save_playlist(self, effect_ids: list[int], interval: int) -> dict:
        return await self._device_command("combined-effect/save", {"effectIds": effect_ids, "interval": interval})

    @property
    def device_id(self) -> str:
        return self._creds.device_id

    async def _device_command(self, path: str, payload: dict) -> dict:
        return await self._request("POST", "/v1/oauth/resources/device/" + path,
                                   payload={"deviceId": self.device_id, "payload": payload})

    async def update_device(self, settings: dict) -> dict:
        return await self._device_command("update", settings)

    async def delete_effect(self, effect_id: int) -> dict:
        return await self._device_command("effect/delete", {"id": effect_id})

    async def notify_update_shadow(self) -> dict:
        return await self._request("GET", "/v1/oauth/resources/device/notify-update-shadow",
            payload={"deviceId": self.device_id, "currentDate": self._current_date_payload()})

    async def sync_datetime(self) -> dict:
        return await self._request("POST", "/v1/oauth/resources/device/datetime/sync",
            payload={"deviceId": self.device_id, "currentDate": self._current_date_payload()})

    async def set_overlays(self, overlay_effects: list[dict]) -> dict:
        return await self._device_command("effect/overlay", {"overlayEffects": overlay_effects})

    async def backup_device(self, backup_time: str) -> dict:
        return await self._device_command("data/backup", {"backupTime": backup_time})

    async def get_backup(self) -> dict:
        return await self._request("POST", "/v1/oauth/resources/device/data/backup/get",
                                   payload={"deviceId": self.device_id})

    async def restore_backup(self, backup_key: str) -> dict:
        return await self._device_command("data/backup/restore", {"backupKey": backup_key})

    async def get_groups(self, page: int = 0) -> dict:
        return await self._request("GET", "/v1/oauth/resources/groups", params={"page": page})

    async def group_command(self, action: str, payload: dict) -> dict:
        if action not in {"add", "update", "rename", "delete", "sync"}:
            raise ValueError("Unsupported group operation")
        # The vendor reference specifies GET with JSON request data for these operations.
        return await self._request("GET", "/v1/oauth/resources/group/" + action, payload=payload)
