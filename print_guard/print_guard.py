#!/usr/bin/env python3
"""bambu-print-guard: local AI failure detection for 3D printers in Home Assistant.

Every few seconds while a print is running, the guard
  1. fetches the printer camera snapshot from Home Assistant,
  2. sends it to the Obico failure-detection model (separate container),
  3. smooths the score over several frames,
  4. on a sustained failure, renders an annotated image and calls a
     Home Assistant webhook with layer / Z-height / "last good layer".

It also publishes a live annotated image (``live.jpg``) and a score sensor
so you can watch what the model sees.

Configuration: JSON file (see config.example.json), path via ``--config`` or
the ``PRINT_GUARD_CONFIG`` environment variable. The Home Assistant token comes
from ``HA_TOKEN`` or the file named in ``token_file``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

__version__ = "1.2.2"

log = logging.getLogger("print-guard")

DEFAULTS: dict = {
    # --- Home Assistant -----------------------------------------------------
    "ha_url": "http://homeassistant.local:8123",
    "token_file": "/config/ha_token",
    "camera": "camera.p1s_camera",
    "status_sensor": "sensor.p1s_print_status",
    "layer_sensor": "sensor.p1s_current_layer",
    "total_layer_sensor": "sensor.p1s_total_layer_count",
    "progress_sensor": "sensor.p1s_print_progress",
    "task_sensor": "sensor.p1s_task_name",
    # Optional: exact Z heights from the G-code cached by ha-bambulab.
    # Leave gcode_sensor empty to disable.
    "gcode_sensor": "",
    "gcode_url_path": "/local/media/ha-bambulab/YOUR_PRINTER_SERIAL/prints/",
    "webhook_id": "print_guard_alert",
    "score_entity": "sensor.print_guard_score",
    "running_states": ["running"],
    "finished_states": ["finish", "failed", "idle"],
    # --- Detection service ---------------------------------------------------
    "ml_api": "http://127.0.0.1:3333/p/",
    # URL under which the *ML container* can fetch frames from this guard.
    "frame_base_url": "http://127.0.0.1:8098",
    # URL under which *Home Assistant* can fetch alert images from this guard.
    "public_url": "http://127.0.0.1:8098",
    "http_port": 8098,
    "data_dir": "./data",
    # --- Tuning --------------------------------------------------------------
    "interval_s": 10,
    "frame_score_min": 0.25,
    "ewm_alpha": 0.3,
    "ewm_alert": 0.40,
    "hits_needed": 3,
    "hits_window": 4,
    "cooldown_s": 900,
    "min_layer": 3,
    "safety_layers": 5,
    "keep_frames": 30,
    # Optional: read tuning values live from Home Assistant helpers, e.g.
    # {"ewm_alert": {"entity": "input_number.print_guard_alert_threshold"},
    #  "cooldown_s": {"entity": "input_number.print_guard_cooldown", "factor": 60, "int": true}}
    "ha_settings": {},
}

# Settings that may be changed at runtime through ``ha_settings``.
TUNABLE = ("ewm_alert", "frame_score_min", "hits_needed", "cooldown_s", "min_layer", "safety_layers",
           "ewm_alpha", "interval_s")


def convert_setting(raw, spec: dict):
    """Convert a Home Assistant state to a setting value; None if not usable."""
    try:
        value = float(raw) * spec.get("factor", 1)
    except (TypeError, ValueError):
        return None
    return int(round(value)) if spec.get("int") else value


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def parse_layer_z(gcode: bytes | str) -> dict[int, float]:
    """Map layer number -> Z height from Bambu Studio / Orca G-code.

    Bambu G-code writes ``; Z_HEIGHT: <z>`` right before
    ``; layer num/total_layer_count: <n>/<total>`` in every layer-change block.
    """
    text = gcode.decode("utf-8", "replace") if isinstance(gcode, bytes) else gcode
    z_map: dict[int, float] = {}
    z = None
    for line in text.splitlines():
        if line.startswith("; Z_HEIGHT:"):
            z = float(line.split(":", 1)[1])
        elif line.startswith("; layer num/total_layer_count:") and z is not None:
            n = int(line.split(":", 1)[1].split("/")[0])
            z_map[n] = z
    return z_map


def to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@dataclass
class ScoreTracker:
    """Turns per-frame scores into a debounced alert decision."""

    alpha: float = 0.3
    frame_score_min: float = 0.25
    ewm_alert: float = 0.40
    hits_needed: int = 3
    hits_window: int = 4
    cooldown_s: float = 900
    min_layer: int = 3
    ewm: float = 0.0
    first_hit_layer: int | None = None
    last_alert: float = 0.0
    hits: deque = field(default_factory=deque)

    @classmethod
    def from_config(cls, cfg: dict) -> ScoreTracker:
        return cls(alpha=cfg["ewm_alpha"], frame_score_min=cfg["frame_score_min"],
                   ewm_alert=cfg["ewm_alert"], hits_needed=cfg["hits_needed"],
                   hits_window=cfg["hits_window"], cooldown_s=cfg["cooldown_s"],
                   min_layer=cfg["min_layer"])

    def __post_init__(self):
        self.hits = deque(self.hits, maxlen=self.hits_window)

    def scoring(self, layer: int | None) -> bool:
        return not (layer is not None and layer < self.min_layer)

    def update(self, score: float, layer: int | None) -> None:
        if not self.scoring(layer):
            return
        self.ewm = self.alpha * score + (1 - self.alpha) * self.ewm
        hit = score >= self.frame_score_min
        self.hits.append(hit)
        if hit and self.first_hit_layer is None:
            self.first_hit_layer = layer
        if not any(self.hits):
            self.first_hit_layer = None

    def should_alert(self, now: float) -> bool:
        return (self.ewm >= self.ewm_alert
                and sum(self.hits) >= self.hits_needed
                and now - self.last_alert >= self.cooldown_s)

    @property
    def hits_text(self) -> str:
        return f"{sum(self.hits)}/{len(self.hits)}"


def last_good_layer(first_hit: int | None, safety_layers: int) -> int | None:
    return max(1, first_hit - safety_layers) if first_hit else None


# --------------------------------------------------------------------------- #
# Home Assistant client
# --------------------------------------------------------------------------- #
class HomeAssistant:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def _req(self, path, data=None, raw=False, timeout=10, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.url + path, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
        return content if raw else (json.loads(content) if content else None)

    def state(self, entity_id: str, quiet: bool = False):
        if not entity_id:
            return None
        try:
            return self._req(f"/api/states/{entity_id}")["state"]
        except Exception as exc:  # noqa: BLE001
            (log.debug if quiet else log.warning)("Cannot read %s: %s", entity_id, exc)
            return None

    def camera(self, entity_id: str) -> bytes:
        return self._req(f"/api/camera_proxy/{entity_id}", raw=True, timeout=15)

    def fetch(self, path: str) -> bytes:
        return self._req(path, raw=True, timeout=60, auth=False)

    def set_state(self, entity_id: str, state, attributes: dict) -> None:
        self._req(f"/api/states/{entity_id}", data={"state": state, "attributes": attributes})

    def webhook(self, webhook_id: str, payload: dict) -> None:
        self._req(f"/api/webhook/{webhook_id}", data=payload, auth=False)


# --------------------------------------------------------------------------- #
# Image annotation
# --------------------------------------------------------------------------- #
def annotate(src: str, dst: str, detections, lines) -> None:
    from PIL import Image, ImageDraw, ImageFont  # imported lazily for tests

    img = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = None
    for candidate in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(candidate, 22)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    for _label, conf, (xc, yc, w, h) in detections:
        box = (xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2)
        draw.rectangle(box, outline=(255, 40, 40), width=4)
        draw.text((box[0] + 4, max(0, box[1] - 26)), f"{conf:.0%}", fill=(255, 40, 40), font=font)
    y = 8
    for text in lines:
        width = draw.textlength(text, font=font)
        draw.rectangle((6, y - 2, 14 + width, y + 26), fill=(0, 0, 0))
        draw.text((10, y), text, fill=(255, 255, 255), font=font)
        y += 30
    img.save(dst, quality=88)


# --------------------------------------------------------------------------- #
# Guard
# --------------------------------------------------------------------------- #
class Guard:
    def __init__(self, cfg: dict, ha: HomeAssistant):
        self.cfg = cfg
        self.ha = ha
        self.www = os.path.join(cfg["data_dir"], "www")
        self.frames_dir = os.path.join(self.www, "frames")
        self.alerts_dir = os.path.join(self.www, "alerts")
        self.history = os.path.join(cfg["data_dir"], "history.jsonl")
        for d in (self.frames_dir, self.alerts_dir):
            os.makedirs(d, exist_ok=True)
        self.published_active = None
        self.reset_job(None)

    # -- job state ----------------------------------------------------------
    def reset_job(self, gcode_name):
        for name in os.listdir(self.frames_dir):
            try:
                os.remove(os.path.join(self.frames_dir, name))
            except OSError:
                pass
        self.gcode_name = gcode_name
        self.z_map: dict[int, float] = {}
        self.tracker = ScoreTracker.from_config(self.cfg)
        self.frames: deque = deque(maxlen=self.cfg["keep_frames"])

    def ensure_gcode(self):
        sensor = self.cfg["gcode_sensor"]
        if not sensor:
            return
        name = self.ha.state(sensor)
        if not name or name in ("unknown", "unavailable") or name == self.gcode_name:
            return
        log.info("New print: %s", name)
        self.reset_job(name)
        try:
            path = self.cfg["gcode_url_path"] + urllib.parse.quote(name)
            self.z_map = parse_layer_z(self.ha.fetch(path))
            log.info("G-code loaded: %d layers with Z height", len(self.z_map))
        except Exception as exc:  # noqa: BLE001
            log.warning("G-code not available (%s) - Z heights disabled for this print", exc)

    # -- detection ----------------------------------------------------------
    def detect(self, frame_name: str):
        url = f"{self.cfg['frame_base_url'].rstrip('/')}/frames/{frame_name}"
        query = self.cfg["ml_api"] + "?img=" + urllib.parse.quote(url, safe="")
        with urllib.request.urlopen(query, timeout=30) as resp:
            return json.loads(resp.read()).get("detections", [])

    def step(self):
        layer = to_int(self.ha.state(self.cfg["layer_sensor"]))
        jpg = self.ha.camera(self.cfg["camera"])
        frame_name = datetime.now().strftime("%Y%m%d-%H%M%S") + ".jpg"
        frame_path = os.path.join(self.frames_dir, frame_name)
        with open(frame_path, "wb") as fh:
            fh.write(jpg)
        detections = self.detect(frame_name)
        score = sum(c for _, c, _ in detections)

        if len(self.frames) == self.frames.maxlen:
            try:
                os.remove(os.path.join(self.frames_dir, self.frames[0]["frame"]))
            except OSError:
                pass
        self.frames.append({"frame": frame_name, "layer": layer, "score": score})

        t = self.tracker
        t.update(score, layer)
        if t.scoring(layer):
            log.info("layer %s  score=%.2f  ewm=%.2f  hits=%s", layer, score, t.ewm, t.hits_text)

        try:
            self.publish_live(frame_path, detections, layer, score)
        except Exception as exc:  # noqa: BLE001
            log.warning("Live view not updated: %s", exc)

        if t.scoring(layer) and t.should_alert(time.time()):
            self.alert(frame_path, frame_name, detections, layer, score)

    def z(self, layer):
        return self.z_map.get(layer) if layer else None

    # -- outputs ------------------------------------------------------------
    def publish_live(self, frame_path, detections, layer, score):
        t = self.tracker
        lines = [
            f"AI score {score:.2f} | smoothed {t.ewm:.2f} (alert at {t.ewm_alert:.2f})",
            f"layer {layer} | hits {t.hits_text} | {datetime.now():%H:%M:%S}"
            + ("" if t.scoring(layer) else " | warm-up, not scored"),
        ]
        tmp = os.path.join(self.www, "live.tmp.jpg")
        annotate(frame_path, tmp, detections, lines)
        os.replace(tmp, os.path.join(self.www, "live.jpg"))
        self.publish_state(True, score, layer, len(detections))

    def publish_state(self, active: bool, score=0.0, layer=None, boxes=0):
        entity = self.cfg["score_entity"]
        if not entity:
            return
        t = self.tracker
        self.ha.set_state(entity, round(score, 2), {
            "friendly_name": "Print Guard score",
            "icon": "mdi:brain",
            "state_class": "measurement",
            "active": active,
            "smoothed": round(t.ewm, 2),
            "hits": t.hits_text,
            "layer": layer,
            "boxes": boxes,
            "alert_threshold": t.ewm_alert,
        })
        self.published_active = active

    def alert(self, frame_path, frame_name, detections, layer, score):
        t = self.tracker
        t.last_alert = time.time()
        total = to_int(self.ha.state(self.cfg["total_layer_sensor"]))
        progress = self.ha.state(self.cfg["progress_sensor"])
        task = self.ha.state(self.cfg["task_sensor"]) or ""
        first = t.first_hit_layer or layer
        good = last_good_layer(first, self.cfg["safety_layers"])
        z_first, z_good = self.z(first), self.z(good)
        conf = max((c for _, c, _ in detections), default=score)

        def fmt_z(z):
            return f"Z {z:.2f} mm" if z is not None else "Z ?"

        lines = [
            f"Possible failure {conf:.0%} - layer {layer}/{total}",
            f"First detected at layer {first} ({fmt_z(z_first)})",
            f"Last good layer {good} ({fmt_z(z_good)})",
        ]
        alert_name = "alert-" + frame_name
        annotate(frame_path, os.path.join(self.alerts_dir, alert_name), detections, lines)
        payload = {
            "task": task,
            "progress": progress,
            "layer": layer,
            "total_layers": total,
            "confidence": round(conf, 3),
            "first_layer": first,
            "first_z": z_first,
            "good_layer": good,
            "good_z": z_good,
            "image_url": f"{self.cfg['public_url'].rstrip('/')}/alerts/{alert_name}",
            "image_file": alert_name,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        before = [f["frame"] for f in list(self.frames)[:-1]]
        with open(self.history, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(payload, before_frames=before), ensure_ascii=False) + "\n")
        log.warning("ALERT: %s", payload)
        try:
            self.ha.webhook(self.cfg["webhook_id"], payload)
        except Exception as exc:  # noqa: BLE001
            log.error("Webhook to Home Assistant failed: %s", exc)

    # -- live settings ------------------------------------------------------
    def apply_ha_settings(self) -> dict:
        """Read tuning values from HA helpers; takes effect with the next frame."""
        changed = {}
        for key, spec in (self.cfg.get("ha_settings") or {}).items():
            if key not in TUNABLE:
                log.warning("ha_settings: %s cannot be changed at runtime", key)
                continue
            # quiet: optional helpers that don't exist must not flood the log
            value = convert_setting(self.ha.state(spec["entity"], quiet=True), spec)
            if value is None or self.cfg.get(key) == value:
                continue
            log.info("Setting from Home Assistant: %s = %s (was %s)", key, value, self.cfg.get(key))
            self.cfg[key] = value
            changed[key] = value
        if changed:
            t = self.tracker
            t.ewm_alert = self.cfg["ewm_alert"]
            t.frame_score_min = self.cfg["frame_score_min"]
            t.hits_needed = self.cfg["hits_needed"]
            t.cooldown_s = self.cfg["cooldown_s"]
            t.min_layer = self.cfg["min_layer"]
            t.alpha = self.cfg["ewm_alpha"]
        return changed

    # -- main loop ----------------------------------------------------------
    def cycle(self) -> str | None:
        status = self.ha.state(self.cfg["status_sensor"])
        if status in self.cfg["running_states"]:
            self.ensure_gcode()
            self.apply_ha_settings()
            self.step()
        elif status in self.cfg["finished_states"]:
            if self.gcode_name:
                log.info("Print finished (%s)", status)
            self.reset_job(None)
            if self.published_active is not False:
                self.publish_state(False)
        return status

    def run(self):
        while True:
            started = time.time()
            try:
                self.cycle()
            except Exception as exc:  # noqa: BLE001
                log.error("Cycle failed: %s", exc)
            time.sleep(max(1.0, self.cfg["interval_s"] - (time.time() - started)))

    def shutdown(self):
        try:
            self.publish_state(False)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


def serve(directory: str, port: int) -> None:
    ThreadingHTTPServer(("0.0.0.0", port), partial(_QuietHandler, directory=directory)).serve_forever()


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    elif path:
        log.warning("Config file %s not found - using defaults", path)
    token = os.environ.get("HA_TOKEN", "").strip()
    if not token and os.path.exists(cfg["token_file"]):
        with open(cfg["token_file"], encoding="utf-8") as fh:
            token = "".join(fh.read().split())
    if not token:
        sys.exit("No Home Assistant token: set HA_TOKEN or create the file named in token_file")
    cfg["token"] = token
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=os.environ.get("PRINT_GUARD_CONFIG", "config.json"))
    parser.add_argument("--once", action="store_true",
                        help="run a single cycle, print the result and exit (for testing)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    guard = Guard(cfg, HomeAssistant(cfg["ha_url"], cfg["token"]))
    threading.Thread(target=serve, args=(guard.www, cfg["http_port"]), daemon=True).start()
    log.info("bambu-print-guard %s started", __version__)

    if args.once:
        status = guard.cycle()
        print(json.dumps({"status": status, "ewm": guard.tracker.ewm,
                          "hits": guard.tracker.hits_text, "layers_with_z": len(guard.z_map)}))
        return 0

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        guard.run()
    finally:
        guard.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
