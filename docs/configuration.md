# Configuration

`config.json` overrides the defaults below. Path: `--config` or `PRINT_GUARD_CONFIG`.
The token comes from the `HA_TOKEN` environment variable or the file in `token_file`.

## Home Assistant

| Key | Default | Description |
|---|---|---|
| `ha_url` | `http://homeassistant.local:8123` | Home Assistant URL as seen from the guard |
| `token_file` | `/config/ha_token` | file with a long-lived access token |
| `camera` | `camera.p1s_camera` | printer camera entity |
| `status_sensor` | `sensor.p1s_print_status` | print status (`running`, `pause`, `finish`, …) |
| `layer_sensor` | `sensor.p1s_current_layer` | current layer |
| `total_layer_sensor` | `sensor.p1s_total_layer_count` | total layers |
| `progress_sensor` | `sensor.p1s_print_progress` | progress in % |
| `task_sensor` | `sensor.p1s_task_name` | name of the print |
| `gcode_sensor` | *(empty = off)* | sensor with the cached G-code file name, enables exact Z heights |
| `gcode_url_path` | `/local/media/ha-bambulab/YOUR_PRINTER_SERIAL/prints/` | where HA serves the cached G-code |
| `webhook_id` | `print_guard_alert` | webhook of the alert blueprint |
| `score_webhook_id` | `print_guard_score` | webhook of the score template sensor (package `print_guard_core.yaml`; empty = off) |
| `summary_webhook_id` | `print_guard_summary` | webhook for the end-of-print summary (blueprint; empty = off) |
| `running_states` | `["running"]` | states in which frames are analysed |
| `finished_states` | `["finish","failed","idle"]` | states that reset the job |

## Network

| Key | Docker default | Native default | Description |
|---|---|---|---|
| `ml_api` | `http://ml:3333/p/` | `http://127.0.0.1:3333/p/` | Obico ML endpoint |
| `frame_base_url` | `http://guard:8098` | `http://127.0.0.1:8098` | how the ML container reaches the guard |
| `public_url` | `http://DOCKER_HOST_IP:8098` | `http://LXC_IP:8098` | how **Home Assistant** reaches the guard |
| `http_port` | `8098` | `8098` | port of the guard's image server |
| `data_dir` | `/data` | `/opt/print-guard/data` | frames, alerts, `live.jpg`, `history.jsonl` |

## Tuning

| Key | Default | Description |
|---|---|---|
| `interval_s` | 10 | seconds between frames |
| `frame_score_min` | 0.25 | sum of box confidences at which a frame counts as suspicious |
| `ewm_alpha` | 0.3 | smoothing factor (higher = reacts faster) |
| `ewm_alert` | 0.40 | smoothed score needed for an alert |
| `hits_needed` / `hits_window` | 3 / 4 | suspicious frames needed within the last N frames |
| `cooldown_s` | 900 | minimum seconds between two alerts |
| `min_layer` | 3 | layers below this are not scored (first layer lines look like spaghetti) |
| `safety_layers` | 5 | "last good layer" = first detection minus this |
| `keep_frames` | 30 | frames kept on disk for later inspection |
| `retention_days` | 30 | alert images and history entries older than this are deleted daily (0 = keep forever) |

### Live tuning from Home Assistant (`ha_settings`)

Instead of editing the file you can map tuning keys to Home Assistant number helpers.
The guard reads them before every frame – no restart needed, and you can change them
while the guard is stopped (they apply with the next print).

```json
"ha_settings": {
  "ewm_alert":       {"entity": "input_number.print_guard_alert_threshold"},
  "frame_score_min": {"entity": "input_number.print_guard_frame_threshold"},
  "hits_needed":     {"entity": "input_number.print_guard_hits_needed", "int": true},
  "cooldown_s":      {"entity": "input_number.print_guard_cooldown", "factor": 60, "int": true},
  "min_layer":       {"entity": "input_number.print_guard_warmup_layers", "int": true},
  "safety_layers":   {"entity": "input_number.print_guard_safety_layers", "int": true}
}
```

`factor` multiplies the helper value (minutes → seconds above), `int` rounds it.
Tunable keys: `ewm_alert`, `frame_score_min`, `hits_needed`, `cooldown_s`, `min_layer`,
`safety_layers`, `ewm_alpha`, `interval_s`. If a helper is missing or `unavailable`, the
value from `config.json` stays in effect. Suggested helper ranges:

| Helper | Min | Max | Step |
|---|---|---|---|
| alert threshold | 0.2 | 1.5 | 0.05 |
| frame threshold | 0.1 | 1.0 | 0.05 |
| hits needed | 1 | 4 (= `hits_window`) | 1 |
| cooldown (min) | 5 | 60 | 5 |
| warm-up layers | 0 | 20 | 1 |
| safety layers | 0 | 20 | 1 |

Don't set an *initial value* on these helpers – Home Assistant would reset them on every restart.

**False alarms?** Raise `ewm_alert` (e.g. 0.6) or `hits_needed`. Typical causes: strong
reflections, the toolhead in front of the camera, support structures, purge lines.
**Missed failures?** Lower `frame_score_min` / `ewm_alert`; check the score graph of a failed print.
With `interval_s: 10` and `hits_needed: 3` an alert comes ~20–40 s after the failure is visible.
