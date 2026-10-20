"""Register discoverable, instance-targeted Home Assistant actions."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service

from .const import DOMAIN
from .management import ACTION_FIELDS, READ_ACTIONS, ManagementController


def register_services(hass) -> None:
    for action, fields in ACTION_FIELDS.items():
        schema = vol.Schema({vol.Required("config_entry_id"): str,
                             **{vol.Required(key): kind for key, kind in fields.items()}})

        async def handle(call, action=action):
            entry_id = call.data["config_entry_id"]
            runtime = hass.data.get(DOMAIN, {}).get(entry_id)
            if runtime is None:
                raise HomeAssistantError("Select a loaded Trimlight configuration entry")
            params = {key: value for key, value in call.data.items() if key != "config_entry_id"}
            result = await ManagementController(runtime).execute(action, params)
            return result if call.return_response else None

        if action in READ_ACTIONS or action in {"request_live_state", "sync_group"}:
            hass.services.async_register(DOMAIN, action, handle, schema=schema,
                                         supports_response=SupportsResponse.OPTIONAL)
        else:
            service.async_register_admin_service(hass, DOMAIN, action, handle, schema=schema,
                                                  supports_response=SupportsResponse.OPTIONAL)
