"""The ORIGINAL (PT2) pipeline, re-implemented as a baseline for the ablation:

    Haar cascade (detectMultiScale(gray, 1.3, 5)) -> first face -> 50x50 grayscale
    -> flattened raw pixels -> nearest-neighbour distance (as in KNN).

Pair-verification score = negative Euclidean distance (higher = more similar).
"""
from __future__ import annotations

import cv2
import numpy as np

_CASCADE = None


def _cascade():
    global _CASCADE
    if _CASCADE is None:
        _CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _CASCADE


def feature(bgr: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _cascade().detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]  # the original code only ever used the first detection
    crop = cv2.resize(bgr[y : y + h, x : x + w], (50, 50))
    return crop.reshape(-1).astype(np.float32)  # original flattened the 50x50x3 crop


def score(f1: np.ndarray | None, f2: np.ndarray | None) -> float:
    if f1 is None or f2 is None:
        return -np.inf  # failure to detect -> cannot verify -> worst score
    return -float(np.linalg.norm(f1 - f2))
