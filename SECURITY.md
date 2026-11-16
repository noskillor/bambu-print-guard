# Security Policy

## Supported versions

Only the **latest release** receives fixes. Please update before reporting.

| Version | Supported |
|---|---|
| latest release (see [Releases](https://github.com/noskillor/bambu-print-guard/releases)) | ✅ |
| older versions | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report it privately via GitHub:
**[Security → Report a vulnerability](https://github.com/noskillor/bambu-print-guard/security/advisories/new)**

Please include what is affected, how to reproduce it and the version you use. You will get an
answer as soon as possible; this is a hobby project, so please allow a few days. Accepted reports
are fixed in a new release and credited in the changelog unless you prefer otherwise.

## Scope

In scope: the code in this repository (`print_guard.py`, deploy scripts, Home Assistant
blueprints and packages).

Out of scope – please report to the respective project:

- the Obico detection model / ML service → [Obico](https://github.com/TheSpaghettiDetective/obico-server)
- the Home Assistant integration for Bambu printers → [ha-bambulab](https://github.com/greghesp/ha-bambulab)
- Home Assistant itself → [Home Assistant security](https://www.home-assistant.io/security/)

## Keeping your setup safe

- **Never post tokens, access codes or passwords** in issues, logs or screenshots. If a Home
  Assistant token was exposed, delete it under *Profile → Security* and create a new one.
- Use a **non-admin Home Assistant user** for the guard's token.
- Keep ports **3333** (model) and **8098** (images) inside your LAN – they have no authentication.
- The alert webhook is `local_only`; don't expose Home Assistant webhooks without remote access
  protection (e.g. Home Assistant Cloud).
