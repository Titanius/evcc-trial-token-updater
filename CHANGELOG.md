# Changelog

## 1.0.0 — Stable

- Verified end-to-end token replacement through evcc's sponsorship configuration API.
- Sends the required JSON object: `{"token":"<JWT>"}`.
- Verifies the persisted token before requesting an evcc restart.
- Adds scheduled updates with configurable Home Assistant local time.
- Adds charging protection and the **Send New Token Now** action.
- Detects the current token location and reports database-backed configuration as `db`.
- Adds the English API-key creation instructions.
- Adds local Home Assistant brand assets for Home Assistant 2026.3+.
- Uses the proper `translations/en.json` structure for a custom integration.
