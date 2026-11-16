# Multiple printers

Run **one guard per printer**. One ML container can serve all of them.

## Docker Compose

```yaml
services:
  ml:
    build:
      context: https://github.com/TheSpaghettiDetective/obico-server.git#release:ml_api
      dockerfile: Containerfile.cpu
    restart: unless-stopped

  guard-p1s:
    build: ./print_guard
    restart: unless-stopped
    environment: { PRINT_GUARD_CONFIG: /config/p1s.json }
    volumes: [./config:/config, ./data/p1s:/data]
    ports: ["8098:8098"]

  guard-a1:
    build: ./print_guard
    restart: unless-stopped
    environment: { PRINT_GUARD_CONFIG: /config/a1.json }
    volumes: [./config:/config, ./data/a1:/data]
    ports: ["8099:8099"]
```

## Per-printer settings in each config file

| Key | P1S | A1 |
|---|---|---|
| entity IDs (`camera`, `status_sensor`, …) | the P1S entities | the A1 entities |
| `webhook_id` | `print_guard_alert_p1s` | `print_guard_alert_a1` |
| `score_webhook_id` | `print_guard_score_p1s` | `print_guard_score_a1` |
| `summary_webhook_id` | `print_guard_summary_p1s` | `print_guard_summary_a1` |
| `http_port` / `public_url` | `8098` | `8099` |
| `frame_base_url` | `http://guard-p1s:8098` | `http://guard-a1:8099` |

In Home Assistant duplicate the score template sensor of the core package once per printer
(different `webhook_id`, `name` and `unique_id`) and create one automation per printer from
each blueprint with the matching webhook IDs. Use separate `input_text` helpers and media
sub-folders per printer so the "last alert" data does not mix.
