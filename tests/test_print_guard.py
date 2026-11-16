import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "print_guard"))

import print_guard as pg  # noqa: E402

GCODE = """\
; HEADER_BLOCK_START
; total layer number: 3
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; LAYER_HEIGHT: 0.2
G1 E-.8 F1800
; layer num/total_layer_count: 1/3
G1 X10 Y10
; CHANGE_LAYER
; Z_HEIGHT: 0.36
; layer num/total_layer_count: 2/3
; CHANGE_LAYER
; Z_HEIGHT: 0.52
; layer num/total_layer_count: 3/3
"""


def test_parse_layer_z_maps_layers_to_heights():
    assert pg.parse_layer_z(GCODE) == {1: 0.2, 2: 0.36, 3: 0.52}


def test_parse_layer_z_accepts_bytes_and_ignores_template_lines():
    data = ("; layer_change_gcode = ; layer num/total_layer_count: {layer_num+1}\n" + GCODE).encode()
    assert pg.parse_layer_z(data)[2] == 0.36


def test_to_int():
    assert pg.to_int("12") == 12
    assert pg.to_int("12.0") == 12
    assert pg.to_int("unavailable") is None
    assert pg.to_int(None) is None


def make_tracker(**kw):
    cfg = dict(pg.DEFAULTS)
    cfg.update(kw)
    return pg.ScoreTracker.from_config(cfg)


def test_clean_print_never_alerts():
    t = make_tracker()
    for layer in range(10, 60):
        t.update(0.0, layer)
        assert not t.should_alert(now=10_000)


def test_sustained_failure_alerts_after_three_frames():
    t = make_tracker()
    alerts = []
    for i, layer in enumerate(range(100, 106)):
        t.update(1.9, layer)
        alerts.append(t.should_alert(now=10_000 + i))
    assert alerts[:2] == [False, False]
    assert alerts[2] is True
    assert t.first_hit_layer == 100


def test_single_reflection_does_not_alert():
    t = make_tracker()
    for layer, score in [(50, 0), (51, 2.5), (52, 0), (53, 0), (54, 0), (55, 0)]:
        t.update(score, layer)
        assert not t.should_alert(now=10_000)
    assert t.first_hit_layer is None  # streak reset after the hits window is clean


def test_warm_up_layers_are_not_scored():
    t = make_tracker(min_layer=3)
    t.update(5.0, 1)
    t.update(5.0, 2)
    assert t.ewm == 0.0 and len(t.hits) == 0


def test_cooldown_blocks_repeated_alerts():
    t = make_tracker(cooldown_s=900)
    for layer in range(10, 15):
        t.update(2.0, layer)
    assert t.should_alert(now=10_000)
    t.last_alert = 10_000
    assert not t.should_alert(now=10_000 + 899)
    assert t.should_alert(now=10_000 + 900)


def test_convert_setting():
    assert pg.convert_setting("0.45", {}) == 0.45
    assert pg.convert_setting("15.0", {"factor": 60, "int": True}) == 900
    assert pg.convert_setting("3.0", {"int": True}) == 3
    assert pg.convert_setting("unavailable", {}) is None
    assert pg.convert_setting(None, {}) is None


class FakeHA:
    def __init__(self, states):
        self.states = states

    def state(self, entity_id, quiet=False):
        return self.states.get(entity_id)


def test_apply_ha_settings_updates_config_and_tracker(tmp_path):
    cfg = dict(pg.DEFAULTS)
    cfg["data_dir"] = str(tmp_path)
    cfg["ha_settings"] = {
        "ewm_alert": {"entity": "input_number.alert"},
        "cooldown_s": {"entity": "input_number.cooldown", "factor": 60, "int": True},
        "hits_needed": {"entity": "input_number.hits", "int": True},
        "keep_frames": {"entity": "input_number.not_tunable"},
    }
    ha = FakeHA({"input_number.alert": "0.6", "input_number.cooldown": "20.0",
                 "input_number.hits": "unavailable", "input_number.not_tunable": "5"})
    guard = pg.Guard(cfg, ha)
    changed = guard.apply_ha_settings()
    assert changed == {"ewm_alert": 0.6, "cooldown_s": 1200}
    assert guard.tracker.ewm_alert == 0.6 and guard.tracker.cooldown_s == 1200
    assert guard.cfg["hits_needed"] == 3          # unavailable helper keeps the old value
    assert guard.cfg["keep_frames"] == 30         # not tunable at runtime
    assert guard.apply_ha_settings() == {}        # nothing changes on the second read


def test_last_good_layer():
    assert pg.last_good_layer(100, 5) == 95
    assert pg.last_good_layer(3, 5) == 1
    assert pg.last_good_layer(None, 5) is None


def test_stats_and_summary():
    st = pg.new_stats(now=1000)
    pg.record_frame(st, 0.1, 0.03, 2, scored=False)    # warm-up frame: counted, not scored
    pg.record_frame(st, 0.5, 0.15, 10, scored=True)
    pg.record_frame(st, 0.2, 0.17, 11, scored=True)
    st["alerts"] = 1
    p = pg.summary_payload(st, "finish", "cube", 0.4, now=1000 + 30 * 60)
    assert p["frames"] == 3 and p["minutes"] == 30
    assert p["max_score"] == 0.5 and p["max_smoothed"] == 0.17
    assert p["alerts"] == 1 and p["last_layer"] == 11 and p["status"] == "finish"


def test_summary_needs_frames():
    assert pg.summary_payload(pg.new_stats(now=0), "finish", "", 0.4, now=60) is None


def test_cleanup_dir_and_history(tmp_path):
    import json
    import os

    alerts = tmp_path / "alerts"
    alerts.mkdir()
    old, new = alerts / "old.jpg", alerts / "new.jpg"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    os.utime(old, (1_000, 1_000))
    os.utime(new, (2_000_000_000, 2_000_000_000))
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"time": "2001-01-01T00:00:00"}) + "\n"
                       + json.dumps({"time": "2030-01-01T00:00:00"}) + "\n", encoding="utf-8")
    removed = pg.cleanup_dir_and_history(str(alerts), str(history), cutoff_ts=1_500_000_000)
    assert removed == 2
    assert not old.exists() and new.exists()
    assert history.read_text(encoding="utf-8").count("\n") == 1


def test_stats_survive_restart(tmp_path):
    path = str(tmp_path / "stats.json")
    st = pg.new_stats(now=100)
    pg.record_frame(st, 0.3, 0.1, 12, scored=True)
    pg.save_stats(path, "cube.gcode", st, now=200)
    assert pg.load_stats(path, "cube.gcode", now=300) == st          # same print -> resumed
    assert pg.load_stats(path, "other.gcode", now=300) is None       # different print
    assert pg.load_stats(path, "cube.gcode", now=200 + 86401) is None  # too old
    assert pg.load_stats(str(tmp_path / "missing.json"), "cube.gcode", now=300) is None
