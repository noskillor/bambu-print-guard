# Home Assistant setup

You need: the [ha-bambulab](https://github.com/greghesp/ha-bambulab) integration and the
Home Assistant Companion App on your phone.

## 1. Long-lived access token

Profile (bottom left) → **Security** → *Long-lived access tokens* → **Create token**.
Put it into `config/ha_token` (Docker) or `/opt/print-guard/ha_token` (native), `chmod 600`.

## 2. Helper

*Settings → Devices & services → Helpers → Create helper → Text*

| Field | Value |
|---|---|
| Name | `Print Guard last alert` → `input_text.print_guard_last_alert` |
| Max length | **255** |

**Optional – sliders for live tuning:** create six *Number* helpers
(`print_guard_alert_threshold`, `print_guard_frame_threshold`, `print_guard_hits_needed`,
`print_guard_cooldown`, `print_guard_warmup_layers`, `print_guard_safety_layers`) with the
ranges from [configuration.md → Live tuning](configuration.md#live-tuning-from-home-assistant-ha_settings)
and keep the `ha_settings` block in `config.json`. Remove the block if you don't want them.

## 3. Integrations

| Integration | Setting | Result |
|---|---|---|
| **Downloader** | Download directory `/media` | stores alert images under `/media/print-guard` |
| **Local File** | File path: any existing image, e.g. `/media/print-guard/placeholder.jpg` (create the folder/file once via *Media* or Samba) | camera for the latest alert image – rename it to `camera.print_guard_alert` |
| **Generic Camera** | Still image URL `http://GUARD_IP:8098/live.jpg`, frame rate 0.2, *Verify SSL* off | live view – rename to `camera.print_guard_live` |

The Local File integration needs `/media` (or the folder you use) in
[`allowlist_external_dirs`](https://www.home-assistant.io/integrations/homeassistant/#allowlist_external_dirs)
on some installations. Home Assistant OS allows `/media` by default.

## 4. Blueprints

Import both blueprints (buttons in the README or *Settings → Automations & scenes →
Blueprints → Import blueprint* with the GitHub URL), then create one automation from each:

**Print Guard – failure alert**

| Input | Example |
|---|---|
| Webhook ID | `print_guard_alert` (same as `webhook_id` in config.json) |
| Phone | your Companion App device |
| Last-alert helper | `input_text.print_guard_last_alert` |
| Alert image camera | `camera.print_guard_alert` |
| Media sub-folder | `print-guard` |
| Open on tap | `/lovelace/print-guard` (your dashboard path + `/print-guard`) |

**Print Guard – Pause / Resume buttons**

| Input | Typical ha-bambulab entity (German HA language in brackets) |
|---|---|
| Printer pause button | `button.<printer>_pause_printing` (`…_druckvorgang_anhalten`) |
| Printer resume button | `button.<printer>_resume_printing` (`…_druckvorgang_fortsetzen`) |
| Printer status sensor | `sensor.<printer>_print_status` (`…_druckstatus`) |
| Current layer sensor | `sensor.<printer>_current_layer` (`…_aktuelle_schicht`) |
| Task name sensor | `sensor.<printer>_task_name` (`…_name_der_aufgabe`) |

Entity names differ by printer name and language – pick them from the dropdowns.

## 5. Dashboard

Paste [`homeassistant/dashboard/print-guard-view.yaml`](../homeassistant/dashboard/print-guard-view.yaml)
as a new view (*Edit dashboard → ⋮ → Raw configuration editor*, add it under `views:`) and replace
the entity IDs marked with `# <-`.

## 6. Exact Z heights (optional)

ha-bambulab caches the G-code of each print under
`/config/www/media/ha-bambulab/<SERIAL>/prints/`, which Home Assistant serves at
`/local/media/ha-bambulab/<SERIAL>/prints/`. To use it, set in `config.json`:

```json
"gcode_sensor": "sensor.<printer>_gcode_filename_downloaded",
"gcode_url_path": "/local/media/ha-bambulab/<SERIAL>/prints/"
```

Pick the sensor that shows a file name ending in `.gcode` (German: `…_gcode_dateiname_heruntergeladen`).
Without it everything works, the notification just shows `Z ?`.

## Test

Send a fake alert to check the whole chain (replace the image URL with any reachable JPEG):

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"task":"TEST","progress":"50","layer":120,"total_layers":300,"confidence":0.6,
       "first_layer":118,"first_z":23.8,"good_layer":113,"good_z":22.8,
       "image_url":"http://GUARD_IP:8098/live.jpg","image_file":"test.jpg","time":"now"}' \
  http://HOME_ASSISTANT:8123/api/webhook/print_guard_alert
```
