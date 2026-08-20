from urllib.parse import urlsplit, urlunsplit

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    DOMAIN,
    CONF_EVCC_URL,
    CONF_API_KEY,
    CONF_INTERVAL,
    CONF_AUTO_RESTART,
    CONF_ENABLED,
    CONF_UPDATE_TIME,
    CONF_SKIP_WHILE_CHARGING,
    DEFAULT_INTERVAL,
    DEFAULT_AUTO_RESTART,
    DEFAULT_UPDATE_TIME,
    DEFAULT_SKIP_WHILE_CHARGING,
)


def normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if "://" not in value:
        value = "http://" + value
    p = urlsplit(value)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip("/"), "", ""))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                url = normalize_url(user_input[CONF_EVCC_URL])
            except Exception:
                errors["base"] = "invalid_url"
            else:
                try:
                    hour, minute = map(int, user_input[CONF_UPDATE_TIME].split(":"))
                    if not (0 <= hour <= 23 and 0 <= minute <= 59):
                        raise ValueError
                except Exception:
                    errors[CONF_UPDATE_TIME] = "invalid_time"
                if not errors:
                    await self.async_set_unique_id(url)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="evcc Trial Token Updater",
                        data={
                            CONF_EVCC_URL: url,
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_INTERVAL: int(user_input[CONF_INTERVAL]),
                            CONF_AUTO_RESTART: bool(user_input[CONF_AUTO_RESTART]),
                            CONF_ENABLED: bool(user_input[CONF_ENABLED]),
                            CONF_UPDATE_TIME: user_input[CONF_UPDATE_TIME],
                            CONF_SKIP_WHILE_CHARGING: bool(
                                user_input[CONF_SKIP_WHILE_CHARGING]
                            ),
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EVCC_URL,
                        default="http://homeassistant.local:7070",
                    ): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_INTERVAL, default=DEFAULT_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
                    vol.Optional(
                        CONF_UPDATE_TIME, default=DEFAULT_UPDATE_TIME
                    ): str,
                    vol.Optional(
                        CONF_ENABLED, default=True
                    ): bool,
                    vol.Optional(
                        CONF_AUTO_RESTART, default=DEFAULT_AUTO_RESTART
                    ): bool,
                    vol.Optional(
                        CONF_SKIP_WHILE_CHARGING,
                        default=DEFAULT_SKIP_WHILE_CHARGING,
                    ): bool,
                }
            ),
            errors=errors,
        )


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            try:
                hour, minute = map(int, user_input[CONF_UPDATE_TIME].split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
            except Exception:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(self._schema()),
                    errors={CONF_UPDATE_TIME: "invalid_time"},
                )
            return self.async_create_entry(title="", data={
                CONF_INTERVAL: int(user_input[CONF_INTERVAL]),
                CONF_AUTO_RESTART: bool(user_input[CONF_AUTO_RESTART]),
                CONF_ENABLED: bool(user_input[CONF_ENABLED]),
                CONF_UPDATE_TIME: user_input[CONF_UPDATE_TIME],
                CONF_SKIP_WHILE_CHARGING: bool(user_input[CONF_SKIP_WHILE_CHARGING]),
            })

        return self.async_show_form(step_id="init", data_schema=vol.Schema(self._schema()))

    def _schema(self):
        current = {**self.config_entry.data, **self.config_entry.options}
        return {
            vol.Optional(CONF_INTERVAL, default=int(current.get(CONF_INTERVAL, DEFAULT_INTERVAL))): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=168)
            ),
            vol.Optional(CONF_UPDATE_TIME, default=current.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)): str,
            vol.Optional(CONF_ENABLED, default=bool(current.get(CONF_ENABLED, True))): bool,
            vol.Optional(CONF_AUTO_RESTART, default=bool(current.get(CONF_AUTO_RESTART, DEFAULT_AUTO_RESTART))): bool,
            vol.Optional(CONF_SKIP_WHILE_CHARGING, default=bool(current.get(CONF_SKIP_WHILE_CHARGING, DEFAULT_SKIP_WHILE_CHARGING))): bool,
        }
