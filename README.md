# FaceAttend — Face-Recognition Attendance System (v2)

A full rebuild (2026) of my 2023 B.E. interdisciplinary project *"Face Recognition for Attendance System"* (PT2).
The original (Flask + Haar cascade + raw-pixel KNN + CSV files) is replaced by a deployable, evaluated system:

| | Original (PT2) | v2 (this repo) |
|---|---|---|
| Detection | Haar cascade, first face only | **YuNet** (DNN) with landmarks, all faces per frame |
| Recognition | KNN on 50×50 raw pixels — always names *someone* | **SFace** 128-d embeddings + cosine threshold + margin → real **unknown-face rejection** |
| Liveness | none (a photo works) | head-turn **challenge-response** using landmarks |
| Capture | server-side `cv2.imshow` window | **browser webcam** (getUserMedia) → API, works on any machine |
| Storage | CSV + image folders | **SQL database** (students, courses, sessions, attendance, audit log) |
| Attendance logic | present only | present / **late** / **absent** (auto-marked on session close), no duplicates |
| Access | none | JWT login, admin / teacher roles |
| Reports | today's table | per-student & per-course stats, charts, **CSV / Excel export** |
| Privacy | none | consent gate, **encrypted templates**, no photos stored, delete-my-data, retention purge, audit log |
| Evidence | none | **ROC / EER benchmark vs. the original pipeline**, robustness ablation, tests, CI |

## Results

Benchmark on LFW (1,000 image pairs), comparing the original pipeline with this one:

| | Equal error rate (lower is better) | AUC (higher is better) |
|---|---|---|
| Original (Haar + raw-pixel KNN) | 41.4% | 0.621 |
| v2 (YuNet + SFace) | **1.8%** | **0.994** |

LFW contains public photos taken in good conditions. Real classroom results depend on
camera, lighting and enrolment quality, so measure them on your own consented data
(`evaluate_local.py`) before relying on the system.

---

## 1. Folder structure

```
attendance-system/
├── README.md
├── docker-compose.yml
├── .gitignore                    # keeps secrets, databases, face data, models out of git
├── .github/workflows/ci.yml      # runs backend tests + frontend build on every push
├── docs/
│   └── EVALUATION.md             # experiment protocol + result tables for the report
├── backend/                      # FastAPI + OpenCV
│   ├── requirements.txt          # runtime packages
│   ├── requirements-dev.txt      # + pytest, httpx
│   ├── requirements-eval.txt     # + scikit-learn, matplotlib (benchmarks)
│   ├── .env.example              # copy to .env
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py               # app factory, admin seeding, CORS
│   │   ├── config.py             # all tunables (thresholds, liveness, retention…)
│   │   ├── database.py  models.py  schemas.py  security.py  deps.py
│   │   ├── routers/              # auth, students, courses, sessions, recognition, reports, privacy
│   │   └── services/
│   │       ├── face_engine.py    # YuNet + SFace via OpenCV
│   │       ├── quality.py        # blur / brightness / size / pose gate at enrolment
│   │       ├── matcher.py        # open-set matching against the encrypted gallery
│   │       ├── tracker.py        # multi-face tracking, identity voting, head-turn liveness
│   │       ├── attendance.py     # mark-once, late rule, auto-absent
│   │       └── crypto.py         # Fernet encryption of face templates
│   ├── scripts/download_models.py
│   ├── evaluation/               # benchmarks used in the report
│   │   ├── evaluate_lfw.py       # new vs. original pipeline, ROC/EER, 6 degradations
│   │   ├── evaluate_local.py     # open-set test on your own consented photos
│   │   ├── baseline.py           # the original Haar + raw-pixel method, re-implemented
│   │   ├── metrics.py  perturbations.py
│   ├── tests/                    # 21 tests (API flow, liveness, matcher, metrics…)
│   └── models/                   # ONNX models land here (git-ignored)
└── frontend/                     # React + Vite
    ├── package.json  vite.config.js  index.html  Dockerfile  nginx.conf
    └── src/
        ├── api.js  auth.jsx  useWebcam.js  App.jsx  main.jsx  styles.css
        ├── components/           # Layout, CameraView (live boxes over the video)
        └── pages/                # Login, Dashboard, Students, Enroll, Courses,
                                  # CourseDetail, Session (live), Reports, Users, Privacy
```

---

## 2. Install the packages (exact steps)

### 2.1 Install these once
| Tool | Version | Check with |
|---|---|---|
| Python | 3.10 – 3.13 | `python --version` (Windows: `py --version`) |
| Node.js (includes npm) | 18 or newer (LTS 20/22 recommended) | `node --version` |
| Git | any | `git --version` |

Downloads: <https://www.python.org/downloads/> · <https://nodejs.org/> · <https://git-scm.com/downloads>
(On Windows tick **"Add Python to PATH"** in the Python installer.)

### 2.2 Backend (Python packages + face models)

Open a terminal in VS Code (`Ctrl+` `` ` ``) and run:

**Windows (PowerShell)**
```powershell
cd attendance-system\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\download_models.py
copy .env.example .env
```
> If PowerShell refuses to run the activation script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and retry.

**macOS / Linux**
```bash
cd attendance-system/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/download_models.py
cp .env.example .env
```

What these do:
* `pip install -r requirements.txt` downloads FastAPI, Uvicorn, SQLAlchemy, OpenCV (4.x), NumPy, bcrypt, cryptography, openpyxl, PyJWT and the other backend packages (takes a minute or two).
* `download_models.py` downloads two ONNX models from the OpenCV Zoo into `backend/models/` — **YuNet** (face detector, ~0.2 MB) and **SFace** (face recogniser, ~37 MB) — then checks that OpenCV can load them. It must print `OK - both models load in OpenCV`.
  If your network blocks GitHub downloads, open <https://github.com/opencv/opencv_zoo/tree/main/models>, download `face_detection_yunet_2023mar.onnx` (folder `face_detection_yunet`) and `face_recognition_sface_2021dec.onnx` (folder `face_recognition_sface`) in the browser, and copy them into `backend/models/`.

Edit `backend/.env` and set a real secret (and change the admin password):
```
python -c "import secrets; print(secrets.token_hex(32))"     # paste the output as SECRET_KEY
```

### 2.3 Frontend (npm packages)
In a **second** terminal:
```bash
cd attendance-system/frontend
npm install
```
This downloads React, React Router, Recharts, Vite (~100 packages) into `frontend/node_modules/`.

---

## 3. Run it

Terminal 1 — backend (keep `.venv` activated, stay in `backend/`):
```bash
uvicorn app.main:get_app --factory --reload --port 8000
```
Check <http://localhost:8000/api/health> → `{"status":"ok","models_loaded":true}`
(API docs: <http://localhost:8000/docs>).

Terminal 2 — frontend (in `frontend/`):
```bash
npm run dev
```
Open **<http://localhost:5173>** and sign in with the admin from your `.env`
(default `admin@example.com` / `ChangeMe123!`). Allow camera access when the browser asks (works on `localhost` without HTTPS).

> Run the backend with a **single worker** (as above): live-recognition tracking state is kept in memory.

### Typical workflow
1. **Students → Add student**, tick the consent box (required before any face can be stored).
2. **Enrol face**: front / left / right, 5 photos each. The server rejects blurry, dark, tiny, multi-face or duplicate-identity photos and tells you why.
3. **Courses → New course → add students**.
4. **Start a class session** → **Start scanning**. Each student looks at the camera, then turns their head left and right (liveness) → marked present (or late after the configured minutes).
5. **Close session** → everyone not recognised is marked absent. Teachers can override manually (audited).
6. **Reports** → charts per student / session, export CSV or Excel.

---

## 4. Tests, CI, Docker

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q          # 21 tests; uses a deterministic fake face engine, no models needed
```
The API tests cover login/roles, consent gate, duplicate-face rejection, stranger rejection, **photo-style (no head-turn) blocking**, multi-face frames, auto-absent, reports and exports.

Docker (optional): `docker compose up --build` → app on <http://localhost:8080>
(copy `backend/.env.example` to `backend/.env` first). Note: browsers only allow the camera on `localhost` or HTTPS, so for a remote server put it behind HTTPS.

---

## 5. Evaluation

```bash
cd backend
pip install -r requirements-eval.txt
python -m evaluation.evaluate_lfw --subset test                    # LFW pairs: new vs. original pipeline
python -m evaluation.evaluate_local --dataset dataset --unknown 2  # your own consented photos
```
Outputs (ROC curve, EER, TAR@FAR, robustness bars, markdown tables) go to `backend/evaluation/results/`.
The full protocol, result tables to fill in, spoofing test procedure and limitations are in [`docs/EVALUATION.md`](docs/EVALUATION.md).

---

## 6. Configuration (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | *(set it!)* | JWT signing key (≥ 32 random chars) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | admin@example.com / ChangeMe123! | first admin, created on first start |
| `MATCH_THRESHOLD` | 0.363 | cosine similarity needed to accept a face (SFace's published value — recalibrate with the evaluation scripts) |
| `MATCH_MARGIN` | 0.05 | best student must beat the runner-up by this much, else "unknown" |
| `LIVENESS_REQUIRED` | true | require the head-turn challenge before marking |
| `RETENTION_DAYS` | 365 | age after which *Privacy → Purge* deletes templates |
| `EMBEDDING_KEY` | auto | Fernet key for template encryption (auto-created at `backend/data/embedding.key`) |

---

## 7. Privacy & ethics

* Face data is **special-category biometric data** (GDPR Art. 9): explicit opt-in consent per student, manual roll-call remains available.
* Camera frames are processed in memory and **never stored**; only an encrypted 128-number template is kept.
* Withdrawing consent, *Delete faces*, or deleting a student erases the templates immediately; *Purge* enforces the retention period; sensitive actions go to the audit log.
* **Never commit** `backend/data/`, `.env`, `embedding.key`, or any photo dataset — `.gitignore` already excludes them.
* The privacy notice in the app is a template, not legal advice.

## 8. Known limitations

* **Liveness** is a head-turn challenge: it stops a still photo or a phone screen held up, **not** a pre-recorded video of the person turning their head, a 3-D mask or a deepfake. A stronger option is a trained passive anti-spoofing model (e.g. MiniFASNet) as a second check.
* **Accuracy depends on enrolment quality and lighting**; fairness across skin tones, ages and glasses/occlusion should be measured on your own data before any real use (see the occlusion test).
* Live-tracking state lives in one process; scaling out would need Redis or sticky sessions.

<img width="1916" height="858" alt="image" src="https://github.com/user-attachments/assets/13d184bd-0187-458d-b274-2c35ff726a70" />

* SQLite is used by default; set `DATABASE_URL` to PostgreSQL for multi-user deployments.
* Model files are third-party (OpenCV Zoo: YuNet MIT, SFace Apache-2.0).
