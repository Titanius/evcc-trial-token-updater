from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ENABLED, VERSION


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UpdaterSwitch(coordinator, entry)])


class UpdaterSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Updater"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="evcc Trial Token Updater",
            manufacturer="evcc",
            model="Trial Token Updater",
            sw_version=VERSION,
        )

    @property
    def is_on(self):
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs):
        self.coordinator.enabled = True
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_ENABLED: True},
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.coordinator.enabled = False
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_ENABLED: False},
        )
        self.async_write_ha_state()
