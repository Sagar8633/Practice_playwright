"""Decoding of the radar object bus.

Bit offsets and scaling factors are taken verbatim from the vendor-supplied
test.py so that behaviour matches the hardware you have already validated.

CAVEAT: extract_motorola_u64 uses MSB0-sequential bit numbering, which is NOT
the same as the classic Motorola/Intel start-bit convention used in DBC files.
It happens to agree for these signals, but validate every field against the
radar's DBC before trusting a number on a live roadside sign.
"""

import time
from dataclasses import dataclass, field

# Object bus layout: each physical target occupies one ID in each range.
OBJ_PART1_ID_START = 0x50
OBJ_PART1_ID_END = 0x77
OBJ_PART2_ID_START = 0x20
OBJ_PART2_ID_END = 0x47
ID_VEHICLE_SPEED = 0x330

OBJ_SLOTS = OBJ_PART1_ID_END - OBJ_PART1_ID_START + 1


def extract_motorola_u64(data_bytes, start_bit, length):
    """Pull an unsigned field out of an 8-byte CAN payload, MSB first."""
    total = int.from_bytes(bytes(data_bytes), byteorder="big", signed=False)
    shift = 64 - (start_bit + length)
    mask = (1 << length) - 1
    return (total >> shift) & mask


def pack_motorola_u64(fields):
    """Inverse of extract_motorola_u64. Used by the radar simulator.

    fields: iterable of (start_bit, length, raw_value)
    """
    total = 0
    for start_bit, length, raw in fields:
        shift = 64 - (start_bit + length)
        total |= (int(raw) & ((1 << length) - 1)) << shift
    return total.to_bytes(8, byteorder="big")


@dataclass
class Track:
    """One radar target, assembled from its PART1 and PART2 frames."""

    idx: int
    obj_id: int = 0
    valid_flag: int = 0
    exist_prob: float = 0.0
    obstacle_prob: float = 0.0
    x_m: float = 0.0
    y_m: float = 0.0
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    meas_flag: int = 0
    has_part1: bool = False
    has_part2: bool = False
    updated_at: float = field(default_factory=time.monotonic)

    @property
    def speed_kph(self):
        return abs(self.vx_mps) * 3.6

    @property
    def direction(self):
        """Sign of vx decides approach vs recede, matching the vendor script."""
        return "INCOMING" if self.vx_mps < 0 else "OUTGOING"

    @property
    def complete(self):
        return self.has_part1 and self.has_part2


class RadarDecoder:
    """Stateful assembler that turns a CAN frame stream into live tracks.

    Thread-safe for a single producer (the CAN reader) and a single consumer
    calling snapshot(); dict mutation under CPython is atomic enough here
    because we never mutate a Track after publishing a snapshot copy.
    """

    def __init__(self, track_timeout_ms=300):
        self.track_timeout_s = track_timeout_ms / 1000.0
        self.tracks = {}
        self.ego_speed_kph = 0.0
        self.frames_seen = 0

    def feed(self, can_id, data_bytes):
        self.frames_seen += 1
        now = time.monotonic()

        if can_id == ID_VEHICLE_SPEED:
            # Ego-vehicle speed. Always ~0 on a fixed roadside pole; retained
            # because the radar is an automotive unit and still emits it.
            raw_speed = extract_motorola_u64(data_bytes, 8, 13)
            self.ego_speed_kph = raw_speed * 0.05625
            return

        if OBJ_PART1_ID_START <= can_id <= OBJ_PART1_ID_END:
            self._feed_part1(can_id - OBJ_PART1_ID_START, data_bytes, now)
        elif OBJ_PART2_ID_START <= can_id <= OBJ_PART2_ID_END:
            self._feed_part2(can_id - OBJ_PART2_ID_START, data_bytes, now)

    def _feed_part1(self, idx, data_bytes, now):
        obj_id = extract_motorola_u64(data_bytes, 0, 8)
        valid_flag = extract_motorola_u64(data_bytes, 23, 1)

        # obj_id 255 is the vendor's "slot empty" marker.
        if obj_id == 255 or valid_flag == 0:
            self.tracks.pop(idx, None)
            return

        track = self.tracks.get(idx)
        if track is None:
            track = Track(idx=idx)
            self.tracks[idx] = track

        track.obj_id = obj_id
        track.valid_flag = valid_flag
        track.exist_prob = extract_motorola_u64(data_bytes, 52, 6) * 1.5873
        track.obstacle_prob = extract_motorola_u64(data_bytes, 24, 5) * 3.2258
        track.has_part1 = True
        track.updated_at = now

    def _feed_part2(self, idx, data_bytes, now):
        track = self.tracks.get(idx)
        if track is None:
            # PART2 without a live PART1 is a stale slot; ignore it.
            return

        raw_vx = extract_motorola_u64(data_bytes, 0, 11)
        track.vx_mps = (raw_vx * 0.1) - 102.4

        raw_y = extract_motorola_u64(data_bytes, 11, 13)
        track.y_m = (raw_y * 0.015625) - 64.0

        raw_x = extract_motorola_u64(data_bytes, 24, 14)
        track.x_m = raw_x * 0.015625

        raw_vy = extract_motorola_u64(data_bytes, 40, 11)
        track.vy_mps = (raw_vy * 0.1) - 102.4

        track.meas_flag = extract_motorola_u64(data_bytes, 51, 1)
        track.has_part2 = True
        track.updated_at = now

    def snapshot(self):
        """Return the currently live, fully-assembled tracks."""
        now = time.monotonic()
        live = []
        for idx in list(self.tracks.keys()):
            track = self.tracks.get(idx)
            if track is None:
                continue
            if now - track.updated_at > self.track_timeout_s:
                self.tracks.pop(idx, None)
                continue
            if track.complete:
                live.append(track)
        return live
