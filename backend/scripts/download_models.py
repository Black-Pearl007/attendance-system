"""Download the two ONNX models used for detection and recognition.

    python scripts/download_models.py

Models come from the OpenCV Zoo (YuNet: MIT licence, SFace: Apache-2.0).
If your network blocks the download, fetch the two files manually from
https://github.com/opencv/opencv_zoo/tree/main/models (face_detection_yunet and
face_recognition_sface folders) and put them in backend/models/.
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://github.com/opencv/opencv_zoo/raw/main/models"
FILES = {
    "face_detection_yunet_2023mar.onnx": (f"{BASE}/face_detection_yunet/face_detection_yunet_2023mar.onnx", 100_000),
    "face_recognition_sface_2021dec.onnx": (f"{BASE}/face_recognition_sface/face_recognition_sface_2021dec.onnx", 5_000_000),
}
DEST = Path(__file__).resolve().parent.parent / "models"


def fetch(name: str, url: str, min_bytes: int) -> None:
    target = DEST / name
    if target.exists() and target.stat().st_size >= min_bytes:
        print(f"[skip] {name} already present")
        return
    print(f"[get ] {name}")
    tmp = target.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": "attendance-system/2.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as out:
        while chunk := r.read(1 << 16):
            out.write(chunk)
    size = tmp.stat().st_size
    head = tmp.read_bytes()[:40]
    if size < min_bytes or head.startswith(b"version https://git-lfs"):
        tmp.unlink()
        sys.exit(f"Download of {name} looks wrong ({size} bytes; Git-LFS pointer?). Download it manually - see header of this script.")
    tmp.replace(target)
    print(f"       saved {target} ({size / 1e6:.1f} MB)")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, (url, min_bytes) in FILES.items():
        fetch(name, url, min_bytes)
    try:  # final check: can OpenCV actually load them?
        import cv2

        cv2.FaceDetectorYN.create(str(DEST / "face_detection_yunet_2023mar.onnx"), "", (320, 320))
        cv2.FaceRecognizerSF.create(str(DEST / "face_recognition_sface_2021dec.onnx"), "")
        print("OK - both models load in OpenCV", cv2.__version__)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Models downloaded but OpenCV could not load them: {e}")


if __name__ == "__main__":
    main()
