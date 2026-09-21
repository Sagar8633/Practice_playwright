"""Target selection and speed conditioning.

The radar reports many simultaneous targets; the sign shows one number. This
module is where that reduction happens, and it is the part the business team
still needs to sign off on -- every rule here is a policy choice exposed in
config.json, not a fact about the hardware.

Three jobs:
  1. Filter tracks down to plausible road vehicles in the zone of interest.
  2. Lock onto one of them and stay locked, so the display does not hop
     between vehicles frame to frame.
  3. Smooth and quantise the speed so the digits do not flicker.
"""

import logging
import time

log = logging.getLogger(__name__)


class TargetSelector:
    def __init__(self, config):
        self.config = config
        self.locked_idx = None
        self.locked_obj_id = None
        self.lost_since = None
        self.smoothed_kph = None
        self.displayed_kph = None

    # -- filtering ---------------------------------------------------------

    def _candidates(self, tracks):
        f = self.config.section("filters")
        wanted_dir = str(f.get("direction", "BOTH")).upper()
        out = []

        for track in tracks:
            if track.x_m <= 0 or track.x_m < f["x_min_m"]:
                continue
            if track.x_m > f["x_max_m"]:
                continue
            if abs(track.y_m) > f["abs_y_max_m"]:
                continue
            if track.exist_prob < f["min_exist_prob"]:
                continue
            if track.obstacle_prob < f["min_obstacle_prob"]:
                continue
            if track.speed_kph < f["min_speed_kph"]:
                continue
            if wanted_dir in ("INCOMING", "OUTGOING") and track.direction != wanted_dir:
                continue
            out.append(track)

        return out

    def _pick(self, candidates):
        policy = self.config.section("selection").get("policy", "nearest")
        if policy == "fastest":
            return max(candidates, key=lambda t: t.speed_kph)
        if policy == "strongest":
            return max(candidates, key=lambda t: t.exist_prob)
        return min(candidates, key=lambda t: t.x_m)  # "nearest"

    # -- locking -----------------------------------------------------------

    def _resolve_lock(self, candidates, now):
        """Keep the current target while it remains plausible.

        A brief dropout must not release the lock, otherwise a vehicle that
        flickers for one cycle hands the display to the car behind it.
        """
        sel = self.config.section("selection")
        grace_s = sel.get("lock_grace_ms", 400) / 1000.0

        if self.locked_idx is not None:
            for track in candidates:
                # Match on slot AND object id: the radar reuses slots, and a
                # slot reused by a new vehicle is not the vehicle we locked.
                if track.idx == self.locked_idx and track.obj_id == self.locked_obj_id:
                    self.lost_since = None
                    return track

            if self.lost_since is None:
                self.lost_since = now
            if now - self.lost_since <= grace_s:
                return None  # still inside grace; hold, do not re-pick yet
            self._release()

        if not candidates:
            return None

        chosen = self._pick(candidates)
        self.locked_idx = chosen.idx
        self.locked_obj_id = chosen.obj_id
        self.lost_since = None
        log.debug("locked slot=%s obj=%s x=%.1fm v=%.1fkph",
                  chosen.idx, chosen.obj_id, chosen.x_m, chosen.speed_kph)
        return chosen

    def _release(self):
        self.locked_idx = None
        self.locked_obj_id = None
        self.lost_since = None
        self.smoothed_kph = None
        self.displayed_kph = None

    # -- conditioning ------------------------------------------------------

    def _condition(self, raw_kph):
        """Exponential smoothing plus display hysteresis.

        Without hysteresis the last digit oscillates between two values as the
        smoothed speed sits on a rounding boundary, which reads as broken.
        """
        sel = self.config.section("selection")
        alpha = float(sel.get("smoothing_alpha", 0.35))
        hysteresis = float(sel.get("hysteresis_kph", 1.0))

        if self.smoothed_kph is None:
            self.smoothed_kph = raw_kph
        else:
            self.smoothed_kph = alpha * raw_kph + (1.0 - alpha) * self.smoothed_kph

        candidate = int(round(self.smoothed_kph))
        if self.displayed_kph is None:
            self.displayed_kph = candidate
        elif abs(self.smoothed_kph - self.displayed_kph) >= hysteresis:
            self.displayed_kph = candidate

        return self.displayed_kph

    # -- public ------------------------------------------------------------

    def update(self, tracks, now=None):
        """Return the speed to display, or None if nothing should be shown."""
        now = now if now is not None else time.monotonic()
        candidates = self._candidates(tracks)
        target = self._resolve_lock(candidates, now)

        if target is None:
            if self.locked_idx is None:
                self.smoothed_kph = None
                self.displayed_kph = None
            # Inside the grace window we intentionally return the last value
            # so a one-cycle dropout does not blank the sign.
            return self.displayed_kph

        return self._condition(target.speed_kph)
