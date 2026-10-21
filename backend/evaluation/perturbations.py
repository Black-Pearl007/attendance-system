"""Image degradations used for the robustness ablation (all operate on BGR uint8)."""
import cv2
import numpy as np


def identity(img):
    return img


def dark(img):  # poor lighting
    return np.clip(img.astype(np.float32) * 0.35, 0, 255).astype(np.uint8)


def bright(img):  # overexposure
    return np.clip(img.astype(np.float32) * 1.7 + 30, 0, 255).astype(np.uint8)


def blur(img):  # motion / defocus
    return cv2.GaussianBlur(img, (0, 0), 3.0)


def low_res(img):  # subject far from the camera
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(w // 4, 1), max(h // 4, 1)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def noise(img):  # sensor noise
    rng = np.random.default_rng(0)
    return np.clip(img.astype(np.float32) + rng.normal(0, 25, img.shape), 0, 255).astype(np.uint8)


def occlusion(img):  # mask-like occlusion of the lower face (LFW faces are centred)
    out = img.copy()
    h, w = out.shape[:2]
    out[int(h * 0.54) : int(h * 0.78), int(w * 0.28) : int(w * 0.72)] = (128, 128, 128)
    return out


PERTURBATIONS = {
    "clean": identity,
    "dark": dark,
    "bright": bright,
    "blur": blur,
    "low_res": low_res,
    "noise": noise,
    "occlusion": occlusion,
}
