# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/).

## [1.2.1] – 2026-11-16

### Changed
- Example dashboard: slider explanation is now a compact, collapsible help ("What do the sliders mean?").

## [1.2.0] – 2026-11-16

### Added
- `homeassistant/packages/print_guard_tuning.yaml`: tuning sliders, Edit switch with
  3-minute auto-lock, Undo (6 steps) and Defaults scripts.

### Changed
- Example dashboard: sensitivity shown as read-only tiles until *Edit* is tapped in the heading;
  in edit mode a table explains every slider.
- Example dashboard redesigned: two columns, AI image while monitoring / normal camera otherwise,
  status tiles, only the matching Pause or Resume button, success/info hints.

## [1.1.0] – 2026-11-16

### Added
- `ha_settings`: tune thresholds live from Home Assistant number helpers (read before every
  frame, no restart). Example helpers, docs and a "Sensitivity" card in the example dashboard.

## [1.0.0] – 2026-11-16

### Added
- `print_guard.py`: camera snapshot → Obico model → smoothed score → webhook alert
- Annotated alert images with layer, exact Z height (from cached G-code) and last good layer
- Live view (`live.jpg`) and `sensor.print_guard_score` for the dashboard
- Docker Compose setup (Obico ML container built from the official repository)
- Native installer for Debian / Proxmox LXC and optional Proxmox start/stop controller
- Home Assistant blueprints: failure alert, Pause/Resume buttons; example dashboard view
- Unit tests and CI
