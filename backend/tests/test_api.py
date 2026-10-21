from .conftest import make_image


def files(*imgs):
    return [("files", (f"f{i}.png", im, "image/png")) for i, im in enumerate(imgs)]


def frame(img):
    return {"file": ("frame.png", img, "image/png")}


def mk_student(client, auth, roll, name, consent=True):
    r = client.post("/api/students", json={"roll_no": roll, "name": name, "consent": consent}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def enroll(client, auth, sid, person):
    imgs = [make_image(person, y) for y in (0.0, 0.0, -0.3, 0.3)]
    r = client.post(f"/api/students/{sid}/enroll-face", files=files(*imgs), headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_required_and_login(client, auth):
    assert client.get("/api/students").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@test.io", "password": "nope"}).status_code == 401
    assert client.get("/api/auth/me", headers=auth).json()["role"] == "admin"


def test_enrolment_needs_consent_and_withdrawal_erases(client, auth):
    sid = mk_student(client, auth, "R1", "No Consent", consent=False)
    r = client.post(f"/api/students/{sid}/enroll-face", files=files(make_image(1)), headers=auth)
    assert r.status_code == 403

    sid2 = mk_student(client, auth, "R2", "Has Consent")
    res = enroll(client, auth, sid2, person=2)
    assert res["accepted"] == 4
    assert client.get(f"/api/students/{sid2}/biometrics", headers=auth).json()["total"] == 4
    r = client.post(f"/api/students/{sid2}/consent", json={"given": False}, headers=auth)
    assert r.json()["face_count"] == 0


def test_duplicate_face_rejected_for_other_student(client, auth):
    a = mk_student(client, auth, "A", "Alice")
    b = mk_student(client, auth, "B", "Bob")
    enroll(client, auth, a, person=3)
    res = client.post(f"/api/students/{b}/enroll-face", files=files(make_image(3)), headers=auth).json()
    assert res["accepted"] == 0
    assert "already matches" in res["results"][0]["reasons"][0]


def test_multi_face_and_no_face_rejected_at_enrolment(client, auth):
    sid = mk_student(client, auth, "R3", "Carol")
    res = client.post(
        f"/api/students/{sid}/enroll-face", files=files(make_image(0), make_image(4, n_faces=2)), headers=auth
    ).json()
    reasons = [x["reasons"][0] for x in res["results"]]
    assert "no face detected" in reasons and "more than one face in the image" in reasons


def _setup_class(client, auth):
    alice = mk_student(client, auth, "A1", "Alice")
    bob = mk_student(client, auth, "B1", "Bob")
    enroll(client, auth, alice, person=10)
    enroll(client, auth, bob, person=11)
    course = client.post("/api/courses", json={"code": "cs101", "name": "Intro"}, headers=auth).json()
    client.post(f"/api/courses/{course['id']}/students", json={"student_ids": [alice, bob]}, headers=auth)
    sess = client.post(
        "/api/sessions", json={"course_id": course["id"], "title": "Lecture 1"}, headers=auth
    ).json()
    return alice, bob, course, sess


def test_full_attendance_flow(client, auth):
    alice, bob, course, sess = _setup_class(client, auth)
    url = f"/api/recognition/{sess['id']}/frame"

    # stranger is never marked and is eventually reported as unknown
    for _ in range(4):
        out = client.post(url, files=frame(make_image(99)), headers=auth).json()
    assert out["faces"][0]["status"] == "unknown" and not out["newly_marked"]

    # Alice held still (like a photo): recognised, but liveness blocks marking
    for _ in range(5):
        out = client.post(url, files=frame(make_image(10, 0.0)), headers=auth).json()
    assert out["faces"][0]["status"] == "turn_head"
    assert out["faces"][0]["student"]["name"] == "Alice" and not out["faces"][0]["marked"]

    # she turns left, then right -> marked present
    newly = []
    for y in (-0.3, -0.3, 0.3, 0.3):
        out = client.post(url, files=frame(make_image(10, y)), headers=auth).json()
        newly += out["newly_marked"]
    assert [n["name"] for n in newly] == ["Alice"]
    assert out["faces"][0]["status"] == "marked"

    # no duplicate marking on further frames
    out = client.post(url, files=frame(make_image(10, 0.0)), headers=auth).json()
    assert out["newly_marked"] == []

    # closing the session marks Bob absent
    detail = client.post(f"/api/sessions/{sess['id']}/close", headers=auth).json()
    status = {r["name"]: r["status"] for r in detail["roster"]}
    assert status == {"Alice": "present", "Bob": "absent"}
    assert client.post(url, files=frame(make_image(10)), headers=auth).status_code == 409


def test_not_enrolled_student_not_marked(client, auth):
    alice, bob, course, sess = _setup_class(client, auth)
    outsider = mk_student(client, auth, "Z9", "Zed")
    enroll(client, auth, outsider, person=12)
    url = f"/api/recognition/{sess['id']}/frame"
    for y in (0.0, 0.0, 0.0, -0.3, 0.3, 0.3):
        out = client.post(url, files=frame(make_image(12, y)), headers=auth).json()
    assert out["faces"][0]["status"] == "not_enrolled" and out["newly_marked"] == []


def test_multiple_faces_in_one_frame(client, auth):
    alice, bob, course, sess = _setup_class(client, auth)
    url = f"/api/recognition/{sess['id']}/frame"
    out = client.post(url, files=frame(make_image(10, 0.0, n_faces=2)), headers=auth).json()
    assert len(out["faces"]) == 2  # both detected (each gets its own track)


def test_reports_and_exports(client, auth):
    alice, bob, course, sess = _setup_class(client, auth)
    client.post(
        f"/api/sessions/{sess['id']}/attendance/manual", json={"student_id": alice, "status": "present"}, headers=auth
    )
    client.post(f"/api/sessions/{sess['id']}/close", headers=auth)
    rep = client.get(f"/api/reports/course/{course['id']}", headers=auth).json()
    by = {r["name"]: r for r in rep["students"]}
    assert by["Alice"]["percent"] == 100.0 and by["Bob"]["percent"] == 0.0
    csv = client.get(f"/api/reports/course/{course['id']}/export?format=csv", headers=auth)
    assert csv.status_code == 200 and "Alice" in csv.text and "Attendance %" in csv.text
    xlsx = client.get(f"/api/reports/session/{sess['id']}/export?format=xlsx", headers=auth)
    assert xlsx.content[:2] == b"PK"  # zip container = valid xlsx
    dash = client.get("/api/reports/dashboard", headers=auth).json()
    assert dash["students"] == 2 and dash["courses"] == 1


def test_teacher_cannot_see_other_teachers_course(client, auth):
    client.post(
        "/api/auth/users",
        json={"email": "t@test.io", "name": "T", "password": "TeacherPass1", "role": "teacher"},
        headers=auth,
    )
    tok = client.post("/api/auth/login", json={"email": "t@test.io", "password": "TeacherPass1"}).json()["access_token"]
    teacher = {"Authorization": f"Bearer {tok}"}
    course = client.post("/api/courses", json={"code": "ADM1", "name": "Admin's"}, headers=auth).json()
    assert client.get(f"/api/reports/course/{course['id']}", headers=teacher).status_code == 403
    assert client.get("/api/courses", headers=teacher).json() == []
    assert client.post("/api/privacy/purge-expired", headers=teacher).status_code == 403


def test_health_and_missing_models(client, tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app

    s = Settings(data_dir=tmp_path, models_dir=tmp_path / "nope", database_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}")
    c = TestClient(create_app(s))
    assert c.get("/api/health").json() == {"status": "ok", "models_loaded": False}
