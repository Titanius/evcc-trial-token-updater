from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN, CONF_UPDATE_TIME

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


def _parse_hhmm(value: str):
    hour, minute = value.split(":")
    return int(hour), int(minute)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .coordinator import EvccTrialCoordinator

    coordinator = EvccTrialCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_load_persistent_state()

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    settings = {**entry.data, **entry.options}
    hour, minute = _parse_hhmm(settings.get(CONF_UPDATE_TIME, "02:00"))

    async def scheduled_update(now):
        await coordinator.async_scheduled_update()

    remove_listener = async_track_time_change(
        hass, scheduled_update, hour=hour, minute=minute, second=0
    )
    coordinator.remove_schedule_listener = remove_listener

    async def _options_updated(hass, updated_entry):
        if updated_entry.options != entry.options:
            await hass.config_entries.async_reload(updated_entry.entry_id)

    coordinator.remove_options_listener = entry.add_update_listener(_options_updated)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator and getattr(coordinator, "remove_schedule_listener", None):
        coordinator.remove_schedule_listener()
    if coordinator and getattr(coordinator, "remove_options_listener", None):
        coordinator.remove_options_listener()

    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return ok
