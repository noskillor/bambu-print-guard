# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Docker image now based on `python:3.15-slim`, Pillow ≥ 13.0, GitHub Actions updated (Dependabot).
- CI tests Python 3.11 – 3.15 and runs with a read-only token.

### Added
- Security policy, code of conduct, pull request template, issue template config, Dependabot config.

## [1.3.1] – 2026-11-16

### Fixed
- The end-of-print summary no longer starts from zero when the guard restarts during a print:
  statistics are saved per print (`data/stats.json`) and resumed for the same G-code / task.

## [1.3.0] – 2026-11-16

### Added
- Watchdog blueprint: warning when the printer prints but the guard is silent.
- End-of-print summary (`summary_webhook_id`) + summary blueprint.
- Feedback: "False alarm" / "Real failure" notification buttons, counters, scripts, blueprint.
- Chamber-light blueprint.
- `retention_days`: daily cleanup of alert images and history in the guard; daily cleanup of
  `/media/print-guard` in Home Assistant (core package).
- `homeassistant/packages/print_guard_core.yaml`.
- `docs/multiple-printers.md`.
- Screenshots in the README.

### Changed
- The score is now sent via webhook (`score_webhook_id`) to a trigger-based template sensor –
  the guard no longer needs an admin token. **Breaking:** `score_entity` was removed; install
  the core package to get `sensor.print_guard_score` again.

## [1.2.2] – 2026-11-16

### Changed
- Example dashboard: slider help uses a definition list, descriptions are indented under each name,
  with a blank line between entries.

## [1.2.1] – 2026-11-16

### Changed
- Example dashboard: slider explanation is now a compact help ("What do the sliders mean?"), expanded by default, collapsible and always visible (not only in edit mode).

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
