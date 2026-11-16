# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] – 2026-11-16

### Added
- `print_guard.py`: camera snapshot → Obico model → smoothed score → webhook alert
- Annotated alert images with layer, exact Z height (from cached G-code) and last good layer
- Live view (`live.jpg`) and `sensor.print_guard_score` for the dashboard
- Docker Compose setup (Obico ML container built from the official repository)
- Native installer for Debian / Proxmox LXC and optional Proxmox start/stop controller
- Home Assistant blueprints: failure alert, Pause/Resume buttons; example dashboard view
- Unit tests and CI
