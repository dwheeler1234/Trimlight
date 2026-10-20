from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import TrimlightApi, TrimlightCredentials
from .controls import require_success
from .const import (
    CONF_COMMIT_CUSTOM_PRESET,
    CONF_DEBUG_LOGGING,
    CONF_DEVICE_ID,
    DEFAULT_COMMIT_CUSTOM_PRESET,
    DEFAULT_DEBUG_LOGGING,
    DOMAIN,
)


class TrimlightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TrimlightOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._credentials = {
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
            }
            device_id = (user_input.get(CONF_DEVICE_ID) or "").strip()
            if device_id:
                return await self._async_finish(device_id)
            creds = TrimlightCredentials(
                client_id=user_input[CONF_CLIENT_ID],
                client_secret=user_input[CONF_CLIENT_SECRET],
                device_id="",
            )
            api = TrimlightApi(async_get_clientsession(self.hass), creds, clock=dt_util.now)
            try:
                result = await api.get_devices(page=0)
                require_success(result)
                devices = (result.get("payload") or {}).get("data") or []
                self._device_choices = {d["deviceId"]: f"{d.get('name') or 'Trimlight'} ({d['deviceId']})"
                                        for d in devices if isinstance(d, dict) and d.get("deviceId")}
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                if self._device_choices:
                    return await self.async_step_device()
                errors["base"] = "no_devices"

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
                vol.Optional(CONF_DEVICE_ID, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_device(self, user_input=None):
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            if device_id not in self._device_choices:
                return self.async_abort(reason="device_not_found")
            return await self._async_finish(device_id)
        return self.async_show_form(step_id="device", data_schema=vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In(self._device_choices),
        }))

    async def _async_finish(self, device_id):
        for entry in self._async_current_entries():
            if entry.data.get(CONF_DEVICE_ID) == device_id:
                return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()
        creds = TrimlightCredentials(device_id=device_id,
            client_id=self._credentials[CONF_CLIENT_ID], client_secret=self._credentials[CONF_CLIENT_SECRET])
        api = TrimlightApi(async_get_clientsession(self.hass), creds, clock=dt_util.now)
        try:
            result = await api.get_device_detail()
            require_success(result)
            if not isinstance(result.get("payload"), dict) or not result["payload"]:
                raise ValueError("Missing controller details")
        except Exception:
            return self.async_show_form(step_id="user", errors={"base": "cannot_connect"}, data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID): str, vol.Required(CONF_CLIENT_SECRET): str,
                vol.Optional(CONF_DEVICE_ID, default=device_id): str,
            }))
        return self.async_create_entry(title=f"Trimlight {device_id[-6:]}",
                                       data={**self._credentials, CONF_DEVICE_ID: device_id})


class TrimlightOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_COMMIT_CUSTOM_PRESET,
                    default=options.get(
                        CONF_COMMIT_CUSTOM_PRESET, DEFAULT_COMMIT_CUSTOM_PRESET
                    ),
                ): bool,
                vol.Optional(
                    CONF_DEBUG_LOGGING,
                    default=options.get(CONF_DEBUG_LOGGING, DEFAULT_DEBUG_LOGGING),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

