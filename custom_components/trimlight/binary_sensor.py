"""Controller connectivity reported independently of commanded power."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass

from .data import get_data
from .entity import TrimlightEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime = get_data(hass, entry.entry_id)
    async_add_entities([TrimlightConnectivity(hass, entry.entry_id, runtime.coordinator)])


class TrimlightConnectivity(TrimlightEntity, BinarySensorEntity):
    _attr_name = "Trimlight Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hass, entry_id, coordinator):
        super().__init__(hass, entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_connectivity"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def is_on(self):
        value = ((self.coordinator.data or {}).get("payload") or {}).get("connectivity")
        return None if value is None else value == 1
