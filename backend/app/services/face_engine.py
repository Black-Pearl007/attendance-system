"""Face detection + embedding.

Uses OpenCV's built-in DNN wrappers around two ONNX models from the OpenCV Zoo
(download them with `python scripts/download_models.py`):

* YuNet  - face detector with 5 facial landmarks (CPU real-time)
* SFace  - face recogniser producing 128-d embeddings (compare with cosine)

The engine is hidden behind a tiny interface so tests can inject a fake one and
the evaluation scripts can swap in other back-ends.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"


class ModelsMissing(RuntimeError):
    pass


@dataclass
class Face:
    box: tuple[int, int, int, int]  # x, y, w, h in pixels
    landmarks: np.ndarray  # (5, 2): right-eye, left-eye, nose, right-mouth, left-mouth
    score: float
    raw: np.ndarray | None = None  # original YuNet row, needed for alignment


class FaceEngine(Protocol):
    def detect(self, bgr: np.ndarray) -> list[Face]: ...
    def embed(self, bgr: np.ndarray, face: Face) -> np.ndarray: ...


def yaw_ratio(face: Face) -> float:
    """Head-turn proxy: horizontal nose offset from the eye midpoint, divided by
    the inter-eye distance. ~0 when frontal; grows in magnitude as the head turns.
    The sign depends on camera mirroring, so callers must treat it as symmetric."""
    lm = face.landmarks
    e1, e2 = lm[0], lm[1]
    nose = lm[2]
    d = abs(float(e2[0] - e1[0]))
    if d < 1e-6:
        return 0.0
    mid_x = float(e1[0] + e2[0]) / 2.0
    return float((nose[0] - mid_x) / d)


class OpenCVFaceEngine:
    def __init__(self, models_dir: Path, score_threshold: float = 0.8, max_side: int = 960):
        det = Path(models_dir) / DETECTOR_FILE
        rec = Path(models_dir) / RECOGNIZER_FILE
        missing = [p.name for p in (det, rec) if not p.exists()]
        if missing:
            raise ModelsMissing(
                f"Missing model file(s): {', '.join(missing)}. "
                "Run `python scripts/download_models.py` inside the backend folder."
            )
        self._detector = cv2.FaceDetectorYN.create(str(det), "", (320, 320), score_threshold, 0.3, 5000)
        self._recognizer = cv2.FaceRecognizerSF.create(str(rec), "")
        self._max_side = max_side
        self._lock = threading.Lock()  # OpenCV DNN objects are not thread-safe

    def detect(self, bgr: np.ndarray) -> list[Face]:
        h, w = bgr.shape[:2]
        scale = 1.0
        img = bgr
        if max(h, w) > self._max_side:
            scale = self._max_side / max(h, w)
            img = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        with self._lock:
            self._detector.setInputSize((img.shape[1], img.shape[0]))
            _, rows = self._detector.detect(img)
        faces: list[Face] = []
        if rows is None:
            return faces
        for r in rows:
            r = np.asarray(r, dtype=np.float32).copy()
            r[:14] /= scale  # back to full-frame pixel coordinates (used for alignment too)
            faces.append(
                Face(
                    box=tuple(int(round(v)) for v in r[:4]),  # type: ignore[arg-type]
                    landmarks=r[4:14].reshape(5, 2).astype(np.float32),
                    score=float(r[14]),
                    raw=r,
                )
            )
        return faces

    def embed(self, bgr: np.ndarray, face: Face) -> np.ndarray:
        with self._lock:
            aligned = self._recognizer.alignCrop(bgr, face.raw.reshape(1, -1))
            feat = self._recognizer.feature(aligned).flatten().astype(np.float32)
        n = np.linalg.norm(feat)
        return feat / n if n > 0 else feat
