from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import logging
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_KEY,
    CONF_EVCC_URL,
    CONF_AUTO_RESTART,
    CONF_ENABLED,
    CONF_UPDATE_TIME,
    CONF_SKIP_WHILE_CHARGING,
    DOC_URL,
    DOMAIN,
    DB_BACKUP_PATH,
    SPONSOR_TOKEN_PATH,
    SHUTDOWN_PATH,
    STATE_PATH,
    STATUS_STARTING,
    STATUS_ALREADY_CURRENT,
    STATUS_UPDATE_AVAILABLE,
    STATUS_UPDATED,
    STATUS_UPDATED_RESTART_REQUESTED,
    STATUS_CURRENT_UNKNOWN,
    STATUS_SKIPPED_CHARGING,
    STATUS_ERROR,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


def normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if "://" not in value:
        value = "http://" + value
    p = urlsplit(value)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("Invalid evcc URL")
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip("/"), "", ""))


def jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT")
    raw = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def token_exp(token: str) -> datetime:
    return datetime.fromtimestamp(int(jwt_payload(token)["exp"]), timezone.utc)


def extract_sqlite(data: bytes) -> bytes:
    if data.startswith(b"SQLite format 3\x00"):
        return data
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
        if data.startswith(b"SQLite format 3\x00"):
            return data
    if data.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    raw = z.read(name)
                    if raw.startswith(b"SQLite format 3\x00"):
                        return raw
    raise ValueError("evcc DB backup does not contain a recognized SQLite database")


def read_sponsor_token(db_bytes: bytes) -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        f.write(db_bytes)
        f.flush()
        con = sqlite3.connect(f.name)
        try:
            rows = con.execute("SELECT key, value FROM settings").fetchall()
        finally:
            con.close()
    for key, value in rows:
        if str(key).lower() == "sponsortoken":
            return str(value).strip() if value else None
    return None


class EvccTrialCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self.hass = hass
        self.evcc_url = normalize_url(entry.data[CONF_EVCC_URL])
        self.api_key = entry.data[CONF_API_KEY]
        settings = {**entry.data, **entry.options}
        self.enabled = bool(settings.get(CONF_ENABLED, True))
        self.auto_restart = bool(settings.get(CONF_AUTO_RESTART, True))
        self.update_time = settings.get(CONF_UPDATE_TIME, "02:00")
        self.skip_while_charging = bool(
            settings.get(CONF_SKIP_WHILE_CHARGING, True)
        )
        self.interval_hours = int(settings.get("interval_hours", 12))

        self.last_check = None
        self.last_change = None

        self.status = STATUS_STARTING
        self.detail = None
        self.current_token_fp = None
        self.current_exp = None
        self.current_location = None
        self.evcc_sponsorship = None
        self.official_token_fp = None
        self.official_exp = None
        self.update_available = False
        self.remove_schedule_listener = None
        self.remove_options_listener = None
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.json")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=self.interval_hours),
        )

    async def async_load_persistent_state(self):
        stored = await self.store.async_load()
        if not stored:
            return
        value = stored.get("last_change")
        if value:
            try:
                self.last_change = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                self.last_change = None

    async def _save_last_change(self, value):
        await self.store.async_save({"last_change": value.isoformat()})

    def _headers(self):
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def _request(self, method, path, data=None, content_type=None):
        timeout = aiohttp.ClientTimeout(total=30)
        headers = self._headers()
        if content_type:
            headers["Content-Type"] = content_type
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                self.evcc_url + path,
                headers=headers,
                data=data,
            ) as response:
                return response.status, await response.read()

    async def _official_token(self):
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                DOC_URL,
                headers={"User-Agent": f"Home-Assistant evcc Trial Token Updater/{VERSION}"},
            ) as response:
                response.raise_for_status()
                text = await response.text()

        import re
        candidates = []
        for token in re.findall(
            r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            text,
        ):
            try:
                p = jwt_payload(token)
                if p.get("iss") == "evcc.io" and p.get("sub") == "trial":
                    candidates.append(
                        (token, int(p["exp"]), int(p.get("iat", 0)))
                    )
            except Exception:
                continue
        if not candidates:
            raise UpdateFailed("No valid official trial token found")
        return max(candidates, key=lambda x: (x[1], x[2]))

    async def _state(self):
        status, body = await self._request("GET", STATE_PATH)
        if status != 200:
            raise UpdateFailed(f"evcc state API unavailable (HTTP {status})")
        try:
            payload = json.loads(body)
            # Current evcc REST responses wrap state in a `result` object.
            return payload.get("result", payload)
        except Exception as err:
            raise UpdateFailed("Invalid JSON returned by evcc state API") from err

    async def _sponsor_state(self):
        state = await self._state()
        sponsor = state.get("sponsor") or {}
        status = sponsor.get("status") or {}
        return {
            "source": sponsor.get("yamlSource"),
            "expires_at": status.get("expiresAt"),
            "name": status.get("name"),
        }

    async def _current_token(self):
        status, body = await self._request("GET", DB_BACKUP_PATH)
        if status != 200:
            raise UpdateFailed(f"evcc DB backup unavailable (HTTP {status})")
        return read_sponsor_token(extract_sqlite(body))

    async def _save_token(self, token):
        if not token or not token.startswith("eyJ"):
            raise UpdateFailed("Safety abort: invalid or empty token")

        # evcc's current handler JSON-decodes the request body into a struct:
        #     {"token": "<JWT>"}
        # Sending the JWT itself, or a JSON string containing the JWT, is
        # rejected by the handler. The UI/API contract requires the object.
        payload = json.dumps({"token": token}, ensure_ascii=False).encode("utf-8")
        status, body = await self._request(
            "POST",
            SPONSOR_TOKEN_PATH,
            data=payload,
            content_type="application/json",
        )
        if status < 200 or status >= 300:
            text = body.decode("utf-8", errors="replace")[:500]
            raise UpdateFailed(
                f"evcc rejected the new token (HTTP {status}): {text}"
            )

    async def _verify_saved(self, expected):
        current = await self._current_token()
        if not current:
            raise UpdateFailed("Token was not found in evcc after saving")
        if fingerprint(current) != fingerprint(expected):
            raise UpdateFailed("evcc does not contain the expected token after saving")
        return current

    async def _is_charging(self) -> bool:
        try:
            state = await self._state()
        except UpdateFailed:
            # If the safety state cannot be read, fail closed: do not restart
            # evcc at an arbitrary time. The next scheduled run can retry.
            return True

        for loadpoint in state.get("loadpoints") or []:
            if bool(loadpoint.get("charging")):
                return True
        return False

    async def _restart(self):
        status, body = await self._request("POST", SHUTDOWN_PATH)
        if status not in (200, 202, 204):
            text = body.decode("utf-8", errors="replace")[:300]
            raise UpdateFailed(f"evcc restart was rejected (HTTP {status}): {text}")

    def _publish(self):
        self.async_set_updated_data(
            {
                "status": self.status,
                "last_check": self.last_check,
                "last_change": self.last_change,
                "current_token_fp": self.current_token_fp,
                "current_exp": self.current_exp,
                "current_location": self.current_location,
                "evcc_sponsorship": self.evcc_sponsorship,
                "official_token_fp": self.official_token_fp,
                "official_exp": self.official_exp,
                "update_available": self.update_available,
                "detail": self.detail,
                "enabled": self.enabled,
                "auto_restart": self.auto_restart,
                "update_time": self.update_time,
                "skip_while_charging": self.skip_while_charging,
            }
        )

    async def _check(self):
        official, off_exp, _ = await self._official_token()
        self.official_token_fp = fingerprint(official)
        self.official_exp = datetime.fromtimestamp(off_exp, timezone.utc)

        sponsor = await self._sponsor_state()
        current = await self._current_token()

        # evcc normally exposes yamlSource as "db" or "file".  Some
        # responses omit yamlSource even though the token is stored in the
        # database.  In that case the authenticated DB backup is the reliable
        # fallback: a readable sponsortoken there means the current token is
        # database-backed.
        source = str(sponsor.get("source") or "").strip().lower()
        if source in {"db", "database"}:
            self.current_location = "db"
        elif source in {"file", "yaml", "yml"}:
            self.current_location = "yaml"
        elif current:
            self.current_location = "db"
        else:
            self.current_location = "unknown"

        self.evcc_sponsorship = bool(sponsor.get("expires_at") or sponsor.get("name"))
        if not current:
            self.current_token_fp = None
            self.current_exp = None
            self.update_available = False
            self.status = STATUS_CURRENT_UNKNOWN
            return official

        self.current_token_fp = fingerprint(current)
        try:
            expires_at = sponsor.get("expires_at")
            self.current_exp = (
                datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expires_at
                else token_exp(current)
            )
        except Exception:
            self.current_exp = token_exp(current)
        self.update_available = fingerprint(current) != fingerprint(official)

        self.status = (
            STATUS_UPDATE_AVAILABLE if self.update_available else STATUS_ALREADY_CURRENT
        )
        return official

    async def _async_update_data(self):
        self.last_check = datetime.now(timezone.utc)
        self.detail = None
        try:
            await self._check()
            self._publish()
            return self.hass.data[DOMAIN][self.entry.entry_id].data
        except Exception as err:
            self.status = STATUS_ERROR
            self.detail = str(err)
            self._publish()
            raise UpdateFailed(str(err)) from err

    async def _write_and_verify(self, official):
        now = datetime.now(timezone.utc)
        await self._save_token(official)
        verified = await self._verify_saved(official)

        self.current_token_fp = fingerprint(verified)
        self.current_exp = token_exp(verified)
        try:
            sponsor = await self._sponsor_state()
            source = str(sponsor.get("source") or "").strip().lower()
            if source in {"db", "database"}:
                self.current_location = "db"
            elif source in {"file", "yaml", "yml"}:
                self.current_location = "yaml"
            else:
                # The just-verified token was persisted through evcc's
                # sponsorship configuration API, so when evcc omits
                # yamlSource we can safely report the active location as DB.
                self.current_location = "db"
            self.evcc_sponsorship = bool(sponsor.get("expires_at") or sponsor.get("name"))
            if sponsor.get("expires_at"):
                self.current_exp = datetime.fromisoformat(
                    sponsor["expires_at"].replace("Z", "+00:00")
                )
        except Exception:
            pass
        self.last_change = now
        await self._save_last_change(now)
        self.update_available = False
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, "last_change": now.isoformat()},
        )
        return verified

    async def async_force_token_update(self):
        self.last_check = datetime.now(timezone.utc)
        self.detail = None
        try:
            official, off_exp, _ = await self._official_token()
            self.official_token_fp = fingerprint(official)
            self.official_exp = datetime.fromtimestamp(off_exp, timezone.utc)

            await self._write_and_verify(official)

            self.status = STATUS_UPDATED
            self.detail = "New official trial token was sent and verified."

            if self.auto_restart:
                await self._restart()
                self.status = STATUS_UPDATED_RESTART_REQUESTED
                self.detail = (
                    "New official trial token was sent, verified, and evcc restart was requested."
                )

            self._publish()
        except Exception as err:
            self.status = STATUS_ERROR
            self.detail = str(err)
            self._publish()
            _LOGGER.error("Forced evcc Trial Token update failed: %s", err)
            raise

    async def async_scheduled_update(self):
        if not self.enabled:
            return

        self.last_check = datetime.now(timezone.utc)
        try:
            official = await self._check()
            if not self.update_available:
                self._publish()
                return

            if self.skip_while_charging and await self._is_charging():
                self.status = STATUS_SKIPPED_CHARGING
                self.detail = "Update deferred because evcc is actively charging."
                self._publish()
                return

            await self._write_and_verify(official)
            self.status = STATUS_UPDATED
            self.detail = "Scheduled token update was sent and verified."

            if self.auto_restart:
                await self._restart()
                self.status = STATUS_UPDATED_RESTART_REQUESTED
                self.detail = (
                    "Scheduled token update was sent, verified, and evcc restart was requested."
                )

            self._publish()
        except Exception as err:
            self.status = STATUS_ERROR
            self.detail = str(err)
            self._publish()
            _LOGGER.error("Scheduled evcc Trial Token update failed: %s", err)

