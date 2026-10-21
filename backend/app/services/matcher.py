"""Open-set identification against the enrolled gallery.

Unlike the original KNN (which always returns the nearest person), this
matcher rejects faces whose cosine similarity is below a calibrated threshold
or that are ambiguous between two students -> real "unknown face" handling.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FaceEmbedding, Student
from .crypto import EmbeddingVault


@dataclass
class MatchResult:
    student_id: int | None
    score: float  # best cosine similarity (even when rejected)
    runner_up: float  # best similarity to a *different* student


class Gallery:
    def __init__(self, vault: EmbeddingVault, threshold: float, margin: float):
        self._vault = vault
        self.threshold = threshold
        self.margin = margin
        self._lock = threading.Lock()
        self._dirty = True
        self._emb = np.zeros((0, 128), dtype=np.float32)
        self._groups: dict[int, np.ndarray] = {}

    def invalidate(self) -> None:
        self._dirty = True

    def ensure(self, db: Session) -> None:
        if not self._dirty:
            return
        with self._lock:
            rows = db.execute(
                select(FaceEmbedding.student_id, FaceEmbedding.vector)
                .join(Student, Student.id == FaceEmbedding.student_id)
                .where(Student.consent_given.is_(True))  # no consent -> never matched
            ).all()
            if rows:
                vecs = np.stack([self._vault.decrypt(v) for _, v in rows])
                ids = np.array([sid for sid, _ in rows])
            else:
                vecs, ids = np.zeros((0, 128), dtype=np.float32), np.zeros(0, dtype=int)
            self._emb = vecs
            self._groups = {int(s): np.where(ids == s)[0] for s in np.unique(ids)}
            self._dirty = False

    def match(self, emb: np.ndarray) -> MatchResult:
        if len(self._emb) == 0:
            return MatchResult(None, -1.0, -1.0)
        sims = self._emb @ emb
        per_student = sorted(((float(sims[idx].max()), sid) for sid, idx in self._groups.items()), reverse=True)
        best, sid = per_student[0]
        runner = per_student[1][0] if len(per_student) > 1 else -1.0
        accepted = best >= self.threshold and (len(per_student) == 1 or best - runner >= self.margin)
        return MatchResult(sid if accepted else None, best, runner)

    def best_other(self, emb: np.ndarray, exclude_student: int) -> tuple[int | None, float]:
        """Best match among students other than `exclude_student` (duplicate-enrolment check)."""
        best_sid, best = None, -1.0
        for sid, idx in self._groups.items():
            if sid == exclude_student:
                continue
            s = float((self._emb[idx] @ emb).max())
            if s > best:
                best_sid, best = sid, s
        return best_sid, best
