from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    specs = [
        ("Current Token Fingerprint", "current_token_fp"),
        ("Current Token Valid Until", "current_exp"),
        ("Official Token Fingerprint", "official_token_fp"),
        ("Official Trial Token Valid Until", "official_exp"),
        ("Status", "status"),
        ("Update Available", "update_available"),
        ("Last Check", "last_check"),
        ("Last Change", "last_change"),
        ("Diagnostic Detail", "detail"),
        ("Current Token Location", "current_location"),
        ("evcc Sponsorship", "evcc_sponsorship"),
        ("Update Time", "update_time"),
        ("Skip While Charging", "skip_while_charging"),
    ]
    async_add_entities([EvccSensor(c, entry, name, key) for name, key in specs])


class EvccSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, name, key):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="evcc Trial Token Updater",
            manufacturer="evcc",
            model="Trial Token Updater",
            sw_version=VERSION,
        )

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self._key)
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        return bool(value) if self._key == "update_available" else value

    @property
    def device_class(self):
        if self._key in ("current_exp", "official_exp", "last_check", "last_change"):
            from homeassistant.components.sensor import SensorDeviceClass
            return SensorDeviceClass.TIMESTAMP
        return None
