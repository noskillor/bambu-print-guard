# Troubleshooting

**Run one cycle by hand** (while printing):
`python print_guard.py --config config.json --once` – prints status, smoothed score and
how many layers have a Z height.

| Symptom | Check |
|---|---|
| `Cannot read sensor.…` | wrong entity ID in `config.json`; copy it from *Developer tools → States* |
| `401 Unauthorized` | token wrong/expired; file must contain only the token |
| `Cycle failed: … 3333` | ML container not running: `docker ps`, `docker logs print-guard-ml` (native) / `docker compose logs ml` |
| ML returns `Failed to get image` | `frame_base_url` not reachable **from the ML container** (Docker: `http://guard:8098`; native with `--network host`: `http://127.0.0.1:8098`) |
| Notification without image | HA cannot reach `public_url`; open `http://GUARD_IP:8098/live.jpg` from another device; Downloader directory must be `/media` |
| No notification at all | Webhook ID differs between config and blueprint; check the automation trace |
| Pause button does nothing | Wrong button entity in the Pause/Resume blueprint; in LAN-only mode the printer needs **Developer mode** so Home Assistant may send commands |
| `Z ?` in the notification | `gcode_sensor`/`gcode_url_path` not set or file not cached yet – see docs/home-assistant.md §6 |
| Many false alarms | see [configuration.md → Tuning](configuration.md#tuning) |
| Live camera "unavailable" | guard stopped (normal between prints with the Proxmox controller) |

**Score sensor missing after a Home Assistant restart:** it is published by the guard
and reappears with the next analysed frame.
