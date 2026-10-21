"""Test fixtures. A deterministic FakeEngine replaces the real ONNX models so the
whole API (auth, enrolment, tracking, liveness, reports) is testable offline.

Fake "images" are tiny PNGs whose pixel (0,0) encodes (person_id, yaw_code):
  person 0  -> no face in the image
  yaw       -> (code - 128) / 200
"""
import numpy as np
import pytest
import cv2
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.face_engine import Face


def make_image(person: int, yaw: float = 0.0, n_faces: int = 1) -> bytes:
    img = np.full((120, 160, 3), 90, dtype=np.uint8)
    img[0, 0] = (person, int(round(128 + yaw * 200)), n_faces)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


class FakeEngine:
    def _decode(self, img):
        person, code, n = (int(v) for v in img[0, 0])
        return person, (code - 128) / 200.0, n

    def detect(self, img):
        person, yaw, n = self._decode(img)
        if person == 0:
            return []
        lm = np.array([[50, 50], [110, 50], [80 + yaw * 60, 75], [60, 95], [100, 95]], dtype=np.float32)
        return [Face(box=(20 + 5 * i, 20, 120, 90), landmarks=lm, score=0.99) for i in range(n)]

    def embed(self, img, face):
        person, _, _ = self._decode(img)
        base = np.random.default_rng(1000 + person).normal(size=128)
        noise = np.random.default_rng().normal(size=128) * 0.05
        v = base + noise
        return (v / np.linalg.norm(v)).astype(np.float32)


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        secret_key="test-secret",
        admin_email="admin@test.io",
        admin_password="AdminPass123",
        min_face_px=1,
        min_blur_var=0,
        min_brightness=0,
        max_brightness=255,
    )


@pytest.fixture()
def client(settings):
    app = create_app(settings, engine_provider=lambda: FakeEngine())
    return TestClient(app)


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.io", "password": "AdminPass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
