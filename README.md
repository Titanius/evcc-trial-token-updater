# evcc Trial Token Updater

<div align="center">

![evcc Trial Token Updater](https://github.com/Titanius/evcc-trial-token-updater/raw/main/README-logo.png)

**Automatic renewal of the official evcc trial token for Home Assistant.**

</div>

[![Open your Home Assistant instance and show the HACS repository dialog](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Titanius&repository=evcc-trial-token-updater&category=integration)
[![Open your Home Assistant instance and show the add integration dialog](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=evcc_trial_token_updater)

| Version | Status | Home Assistant | evcc |
|---|---|---|---|
| **1.0.0** | **Stable release** | **2026.3+ recommended** | Current API |

> **Purpose:** automate the same workflow you normally perform manually in evcc: obtain the new official trial token → save it through evcc → verify it → optionally restart evcc.

## What this integration does

The integration checks the official evcc trial-token source, compares the published token with the token currently stored by evcc, and only performs a write when a different valid token is available.

It is designed for the normal evcc **database / web-UI configuration model**.

**It does not edit `evcc.yaml`.**

## Recommended evcc setup

Configure evcc normally through its web interface. Add your charger, meters, PV, vehicle and loadpoint through evcc's configuration UI so that the configuration remains in evcc's database.

Do not add `sponsortoken:` to `evcc.yaml` when you want to manage the sponsorship token through evcc's UI/API.

The integration only requires a reachable evcc instance and an authenticated evcc API.

## Installation

### HACS (recommended)

1. Open **HACS → Integrations**.
2. Add **evcc Trial Token Updater** as an Integration repository if it is not already available.
3. Download/install it.
4. Restart Home Assistant when HACS requests it.
5. Go to **Settings → Devices & services → Add Integration**.
6. Search for **evcc Trial Token Updater** and complete the setup.

The badge at the top of this README opens the HACS repository dialog directly in Home Assistant.

### Manual installation

Copy the single integration directory:

```text
custom_components/evcc_trial_token_updater/
```

into your Home Assistant configuration directory:

```text
custom_components/
```

Then restart Home Assistant and add the integration from **Settings → Devices & services**.

No particular Home Assistant installation method is required.

## Configuration

During setup enter:

- **evcc URL** — for example `http://<evcc-host>:7070`
- **evcc API key**
- **Background check interval**
- **Scheduled update time**, e.g. `02:00`
- **Updater enabled**
- **Restart evcc after a successful update**
- **Do not update while the car is charging**

The schedule and safety settings can be changed later through the integration's **Configure / Options** dialog.

### Creating an evcc API key

The integration uses an evcc API key for authenticated access to the local evcc instance. In the evcc web interface, create one as follows:

1. Open evcc.
2. Open **More**.
3. Select **Configuration**.
4. Open **Security**.
5. Find **API Keys**.
6. Click **Create New**.
7. Copy the generated API key and enter it in the **evcc API key** field of this integration.

Keep the API key private. It is used to authenticate the updater against evcc.

### Time zones

The scheduled time follows the **Home Assistant local time zone**. For example, setting `02:00` means the update is attempted at 02:00 in the time zone configured for Home Assistant. You can choose any valid 24-hour time such as `03:00`.

## Automatic update sequence

```text
Official evcc trial token
        │
        ▼
Validate JWT + expiry
        │
        ▼
Compare with current evcc token
        │
        ├── same → nothing changes
        │
        └── different
              │
              ▼
        Check charging state
              │
              ├── charging → defer
              │
              └── idle
                    │
                    ▼
          POST /api/config/sponsortoken
                    │
                    ▼
          Verify persisted token
                    │
                    ▼
          Record Last Change
                    │
                    ▼
          Optional evcc restart
```

If the charging state cannot be read reliably, the scheduled operation fails closed and does **not** restart evcc.

## Send New Token Now

The **Send New Token Now** button performs the same safe update path immediately.

It does not blindly restart evcc:

1. Retrieve the official token.
2. Validate the JWT and expiration.
3. Send the token through evcc's configuration API as the JSON value expected by the handler.
4. Read the persisted token back and verify its fingerprint.
5. Record the change only after successful verification.
6. Restart evcc only after verification when automatic restart is enabled.

## Charging protection

By default, **Skip While Charging** is enabled.

If evcc reports an actively charging loadpoint at the scheduled time, the token is not changed and evcc is not restarted. The next scheduled run can try again.

## Home Assistant entities

The device provides status and diagnostic entities including:

- **Status**
- **Update Available**
- **Current Token Fingerprint**
- **Current Token Valid Until**
- **Current Token Location**
- **evcc Sponsorship**
- **Official Token Fingerprint**
- **Official Trial Token Valid Until**
- **Last Check**
- **Last Change**
- **Diagnostic Detail**
- **Update Time**
- **Skip While Charging**
- **Updater**
- **Send New Token Now**

The actual JWT is deliberately never exposed as a Home Assistant entity.

## API paths used

Authenticated requests are limited to the functions required for this workflow:

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | Read evcc state and charging status |
| `GET /api/db/backup` | Verify the persisted sponsor token without exposing it as a HA entity |
| `POST /api/config/sponsortoken` | Save the new token through evcc's configuration handler |
| `POST /api/system/shutdown` | Request an evcc restart after a verified update |

The integration does **not** write directly into evcc's SQLite database.

## Why the JSON request matters

Earlier development builds sent the JWT as raw request text. evcc's current sponsorship-token handler expects a JSON object with a `token` field. Sending a raw JWT, or a JSON string instead of the required object, produced the characteristic HTTP 400 errors:

```text
HTTP 400: invalid character 'e' looking for beginning of value
```

The current implementation sends a JSON object with `Content-Type: application/json`:

```json
{"token":"<JWT>"}
```

## Security

- The evcc API key is stored in the Home Assistant config entry.
- The actual trial JWT is not exposed as an entity state.
- Logs contain fingerprints and diagnostics, not the token itself.
- The updater never creates or modifies JWT signatures.
- `evcc.yaml` is never rewritten.
- A failed token write does not intentionally trigger a restart.
- The new token is verified before `Last Change` is recorded and before an automatic restart is requested.

## Branding

The integration includes Home Assistant brand assets under:

```text
custom_components/evcc_trial_token_updater/brand/
├── icon.png
├── icon@2x.png
├── logo.png
└── logo@2x.png
```

Home Assistant can use these local brand assets in supported current versions. HACS may display repository artwork separately from the Home Assistant device/integration artwork.

## Release status

**Version 1.0.0 — Stable release.**

This release marks the first stable version after end-to-end testing of the token write, verification and restart workflow. The integration is designed to automate the same token change that can be performed in the evcc web interface. 

This is an independent Home Assistant community integration and is not an official evcc product.

## Official references

- evcc Sponsorship / Trial Token: https://docs.evcc.io/en/sponsorship/
- evcc State API: https://docs.evcc.io/en/reference/state/
- evcc REST API: https://docs.evcc.io/en/integrations/rest-api/
- Home Assistant integration brand images: https://developers.home-assistant.io/docs/core/integration/brand_images/
- HACS integration publishing requirements: https://www.hacs.xyz/docs/publish/integration/

## License

See `LICENSE`.
