"""Per-session multi-face tracking, identity voting and head-turn liveness.

Why a tracker? The API is stateless per frame, but attendance should only be
marked when (a) the *same* face is recognised consistently over several frames
and (b) that face passes a liveness challenge. A very small centroid tracker is
enough for a classroom camera.

Liveness (challenge-response): the person must turn their head to BOTH sides
while being tracked. A flat printed photo or a phone screen held still cannot
produce the nose-offset swing measured from the landmarks. NOTE: this does not
stop a video replay or a deepfake - see docs/EVALUATION.md (limitations).
"""
from __future__ import annotations

import threading
from collections import Counter, deque
from dataclasses import dataclass, field

from ..config import Settings


@dataclass
class Observation:
    box: tuple[float, float, float, float]  # normalised x, y, w, h
    student_id: int | None
    score: float
    yaw: float


@dataclass
class Track:
    id: int
    box: tuple[float, float, float, float]
    last_seen: float
    cfg: Settings
    votes: deque = field(default_factory=deque)
    scores: deque = field(default_factory=deque)
    yaws: deque = field(default_factory=lambda: deque(maxlen=40))
    marked: bool = False
    _identity: int | None = None

    def add(self, obs: Observation, now: float) -> None:
        self.box, self.last_seen = obs.box, now
        self.votes.append(obs.student_id)
        self.scores.append(obs.score)
        while len(self.votes) > self.cfg.vote_window:
            self.votes.popleft()
            self.scores.popleft()
        self.yaws.append(obs.yaw)
        ident = self.identity
        if ident != self._identity:  # identity flipped -> old head-turns don't count
            self.yaws.clear()
            self.yaws.append(obs.yaw)
            self._identity = ident

    @property
    def identity(self) -> int | None:
        """Student id if one id holds >= votes_required of the recent votes."""
        counts = Counter(v for v in self.votes if v is not None)
        if not counts:
            return None
        sid, n = counts.most_common(1)[0]
        return sid if n >= self.cfg.votes_required else None

    @property
    def verdict_unknown(self) -> bool:
        """True once enough recent frames were rejected as 'unknown'."""
        return sum(v is None for v in self.votes) >= self.cfg.votes_required and self.identity is None

    @property
    def confidence(self) -> float:
        ident = self.identity
        vals = [s for v, s in zip(self.votes, self.scores) if v == ident and ident is not None]
        return float(sum(vals) / len(vals)) if vals else 0.0

    def liveness(self) -> dict:
        thr = self.cfg.liveness_yaw_threshold
        left = any(y <= -thr for y in self.yaws)
        right = any(y >= thr for y in self.yaws)
        return {
            "required": self.cfg.liveness_required,
            "left": left,
            "right": right,
            "passed": (left and right) or not self.cfg.liveness_required,
        }


class SessionTracker:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.tracks: dict[int, Track] = {}
        self._next = 1
        self.lock = threading.Lock()

    def update(self, observations: list[Observation], now: float) -> list[tuple[Track, Observation]]:
        with self.lock:
            for tid in [t for t, tr in self.tracks.items() if now - tr.last_seen > self.cfg.track_ttl_seconds]:
                del self.tracks[tid]

            def centre(b):
                return (b[0] + b[2] / 2, b[1] + b[3] / 2)

            pairs = []
            for tid, tr in self.tracks.items():
                tc = centre(tr.box)
                for i, ob in enumerate(observations):
                    oc = centre(ob.box)
                    size = max(tr.box[2], tr.box[3], ob.box[2], ob.box[3])
                    d = ((tc[0] - oc[0]) ** 2 + (tc[1] - oc[1]) ** 2) ** 0.5
                    if d < 0.6 * size:
                        pairs.append((d / size, tid, i))
            pairs.sort()
            used_t, used_o, assigned = set(), set(), {}
            for _, tid, i in pairs:
                if tid in used_t or i in used_o:
                    continue
                used_t.add(tid)
                used_o.add(i)
                assigned[i] = tid

            result = []
            for i, ob in enumerate(observations):
                if i in assigned:
                    tr = self.tracks[assigned[i]]
                else:
                    tr = Track(id=self._next, box=ob.box, last_seen=now, cfg=self.cfg)
                    self.tracks[tr.id] = tr
                    self._next += 1
                tr.add(ob, now)
                result.append((tr, ob))
            return result
