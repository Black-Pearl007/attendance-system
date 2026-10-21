import numpy as np

from app.config import Settings
from app.services.crypto import EmbeddingVault
from app.services.face_engine import Face, yaw_ratio
from app.services.matcher import Gallery
from app.services.tracker import Observation, SessionTracker


def unit(seed):
    v = np.random.default_rng(seed).normal(size=128)
    return (v / np.linalg.norm(v)).astype(np.float32)


def test_vault_roundtrip(tmp_path):
    v = EmbeddingVault("", tmp_path)
    x = unit(1)
    assert np.allclose(v.decrypt(v.encrypt(x)), x)
    # key persisted -> a second vault can read it
    assert np.allclose(EmbeddingVault("", tmp_path).decrypt(v.encrypt(x)), x)


def _gallery(tmp_path, entries):
    g = Gallery(EmbeddingVault("", tmp_path), threshold=0.363, margin=0.05)
    ids = np.array([sid for sid, _ in entries])
    g._emb = np.stack([e for _, e in entries])
    g._groups = {int(s): np.where(ids == s)[0] for s in np.unique(ids)}
    g._dirty = False
    return g


def test_matcher_accepts_known_rejects_unknown(tmp_path):
    g = _gallery(tmp_path, [(1, unit(1)), (2, unit(2))])
    assert g.match(unit(1)).student_id == 1
    assert g.match(unit(2)).student_id == 2
    stranger = g.match(unit(99))
    assert stranger.student_id is None  # the original KNN would have named someone


def test_matcher_rejects_ambiguous(tmp_path):
    a = unit(1)
    near = a + 0.02 * unit(5)
    near /= np.linalg.norm(near)
    g = _gallery(tmp_path, [(1, a), (2, near)])
    assert g.match(a).student_id is None  # two students almost identical -> refuse to guess


def test_yaw_ratio_symmetry():
    def face(nose_x):
        lm = np.array([[50, 50], [110, 50], [nose_x, 75], [60, 95], [100, 95]], dtype=np.float32)
        return Face(box=(0, 0, 1, 1), landmarks=lm, score=1.0)

    assert abs(yaw_ratio(face(80))) < 1e-6
    assert yaw_ratio(face(95)) > 0.2 and yaw_ratio(face(65)) < -0.2


def _obs(sid, yaw, score=0.9):
    return Observation((0.3, 0.3, 0.3, 0.3), sid, score, yaw)


def test_tracker_requires_both_head_turns():
    t = SessionTracker(Settings())
    for i in range(4):
        (tr, _), = t.update([_obs(7, 0.0)], now=i)
    assert tr.identity == 7 and not tr.liveness()["passed"]
    (tr, _), = t.update([_obs(7, -0.3)], now=5)
    assert not tr.liveness()["passed"]  # only one side so far
    (tr, _), = t.update([_obs(7, 0.3)], now=6)
    assert tr.liveness()["passed"]


def test_tracker_identity_flip_resets_liveness():
    t = SessionTracker(Settings())
    for i in range(3):
        t.update([_obs(7, -0.3)], now=i)
    for i in range(3, 12):
        (tr, _), = t.update([_obs(8, 0.3)], now=i)
    assert tr.identity == 8
    assert not tr.liveness()["left"]  # the old person's left-turn must not count


def test_tracker_expires_and_separates_faces():
    t = SessionTracker(Settings())
    far = Observation((0.7, 0.3, 0.2, 0.2), 2, 0.9, 0.0)
    out = t.update([_obs(1, 0.0), far], now=0)
    assert len({tr.id for tr, _ in out}) == 2
    t.update([], now=100)  # long gap -> tracks expire
    assert not t.tracks
