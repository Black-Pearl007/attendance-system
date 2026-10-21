"""Image-quality gate used at enrolment so only usable templates are stored."""
from dataclasses import dataclass, field

import cv2
import numpy as np

from ..config import Settings
from .face_engine import Face, yaw_ratio


@dataclass
class QualityReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    blur: float = 0.0
    brightness: float = 0.0
    face_px: int = 0
    yaw: float = 0.0
    pose: str = "front"

    @property
    def score(self) -> float:
        """Rough 0..1 quality figure stored alongside the template."""
        s_blur = min(self.blur / 200.0, 1.0)
        s_size = min(self.face_px / 200.0, 1.0)
        s_light = 1.0 - min(abs(self.brightness - 128.0) / 128.0, 1.0)
        return round((s_blur + s_size + s_light) / 3.0, 3)


def classify_pose(yaw: float, thr: float) -> str:
    if abs(yaw) < 0.12:
        return "front"
    if yaw <= -thr:
        return "left"
    if yaw >= thr:
        return "right"
    return "other"


def assess(img: np.ndarray, face: Face, cfg: Settings) -> QualityReport:
    x, y, w, h = face.box
    H, W = img.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    reasons: list[str] = []
    if x1 - x0 < 2 or y1 - y0 < 2:
        return QualityReport(False, ["face outside frame"])
    crop = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    crop = cv2.resize(crop, (112, 112), interpolation=cv2.INTER_AREA)  # comparable blur metric
    blur = float(cv2.Laplacian(crop, cv2.CV_64F).var())
    brightness = float(crop.mean())
    face_px = int(min(w, h))
    yaw = yaw_ratio(face)

    if face_px < cfg.min_face_px:
        reasons.append("face too small - move closer")
    if blur < cfg.min_blur_var:
        reasons.append("image too blurry - hold still")
    if brightness < cfg.min_brightness:
        reasons.append("too dark")
    if brightness > cfg.max_brightness:
        reasons.append("too bright / overexposed")
    if x < 0 or y < 0 or x + w > W or y + h > H:
        reasons.append("face cut off at the frame edge")

    return QualityReport(
        ok=not reasons,
        reasons=reasons,
        blur=blur,
        brightness=brightness,
        face_px=face_px,
        yaw=yaw,
        pose=classify_pose(yaw, cfg.liveness_yaw_threshold),
    )
