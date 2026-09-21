"""Configuration loading with hot reload.

Everything that is a policy decision lives in config.json, not in code, so the
selection rules and colour thresholds can be tuned in the field without a
redeploy. The file is re-read on a timer, never in the per-frame path.
"""

import json
import os
import threading
import time

DEFAULTS = {
    "mode": "sim",
    "radar": {
        "dev_type": 3,
        "dev_idx": 0,
        "ch_idx": 0,
        "timing0": 0x00,
        "timing1": 0x1C,
        "lib_dir": ".",
        "poll_wait_ms": 50,
        "rx_batch": 100,
    },
    "filters": {
        "direction": "INCOMING",
        "x_min_m": 8.0,
        "x_max_m": 120.0,
        "abs_y_max_m": 8.0,
        "min_speed_kph": 5.0,
        "min_exist_prob": 35.0,
        "min_obstacle_prob": 20.0,
        "track_timeout_ms": 300,
    },
    "selection": {
        "policy": "nearest",
        "lock_grace_ms": 400,
        "smoothing_alpha": 0.35,
        "hysteresis_kph": 1.0,
    },
    "display": {
        "enabled": True,
        "host": "192.168.1.7",
        "port": 1000,
        "connect_timeout_s": 3.0,
        "min_command_interval_ms": 150,
        "refresh_interval_ms": 1000,
        "blank_after_ms": 1200,
        "reconnect_backoff_s": [1, 2, 5, 10, 30],
        "clear_region": [0, 16, 64, 64],
        "speed_min_kph": 5,
        "speed_max_kph": 199,
        "colors": {"green_below": 60, "orange_below": 80},
        "banner": {"enabled": False, "text": "SPEED", "x": 4, "y": 0,
                   "color": 8, "font": 12},
    },
    "service": {"loop_hz": 20.0, "config_reload_s": 5.0},
    "logging": {"level": "INFO"},
}


def _deep_merge(base, override):
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    """Holds the merged config and reloads it when the file changes on disk."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._lock = threading.Lock()
        self._mtime = 0.0
        self._data = dict(DEFAULTS)
        self._last_check = 0.0
        self.reload(force=True)

    def reload(self, force=False):
        """Re-read the file if its mtime moved. Returns True if it changed."""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return False
        if not force and mtime == self._mtime:
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            # Keep serving the last good config rather than crashing a
            # roadside device because someone saved a half-written file.
            return False
        with self._lock:
            self._data = _deep_merge(DEFAULTS, raw)
            self._mtime = mtime
        return True

    def maybe_reload(self, interval_s):
        now = time.monotonic()
        if now - self._last_check < interval_s:
            return False
        self._last_check = now
        return self.reload()

    def section(self, name):
        with self._lock:
            return dict(self._data.get(name, {}))

    @property
    def data(self):
        with self._lock:
            return dict(self._data)
