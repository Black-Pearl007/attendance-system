import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..deps import audit, get_current_user, get_db, get_engine, require_admin
from ..models import FaceEmbedding, Student, User, utcnow
from ..schemas import ConsentIn, StudentCreate, StudentOut
from ..services.quality import assess

router = APIRouter(prefix="/api/students", tags=["students"])

MAX_FILES_PER_REQUEST = 10


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Not a valid image")
    return img


def _out(db: Session, s: Student) -> StudentOut:
    n = db.scalar(select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == s.id)) or 0
    out = StudentOut.model_validate(s)
    out.face_count = n
    return out


def _get(db: Session, student_id: int) -> Student:
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(404, "Student not found")
    return s


@router.get("", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_out(db, s) for s in db.scalars(select(Student).order_by(Student.roll_no))]


@router.post("", response_model=StudentOut, status_code=201)
def create_student(body: StudentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    roll = body.roll_no.strip()
    if db.scalar(select(Student).where(Student.roll_no == roll)):
        raise HTTPException(409, "Roll number already exists")
    s = Student(
        roll_no=roll,
        name=body.name.strip(),
        email=body.email,
        consent_given=body.consent,
        consent_at=utcnow() if body.consent else None,
    )
    db.add(s)
    db.commit()
    audit(db, user, "student.create", roll, f"consent={body.consent}")
    return _out(db, s)


@router.post("/{student_id}/consent", response_model=StudentOut)
def set_consent(
    student_id: int,
    body: ConsentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = _get(db, student_id)
    s.consent_given = body.given
    s.consent_at = utcnow() if body.given else None
    if not body.given:  # withdrawing consent erases the biometric templates (GDPR Art. 7(3))
        db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == s.id))
        request.app.state.gallery.invalidate()
    db.commit()
    request.app.state.gallery.invalidate()
    audit(db, user, "student.consent", s.roll_no, f"given={body.given}")
    return _out(db, s)


@router.get("/{student_id}/biometrics")
def biometrics_summary(student_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get(db, student_id)
    rows = db.execute(
        select(FaceEmbedding.pose, func.count()).where(FaceEmbedding.student_id == student_id).group_by(FaceEmbedding.pose)
    ).all()
    by_pose = {p: n for p, n in rows}
    return {"total": sum(by_pose.values()), "by_pose": by_pose}


@router.post("/{student_id}/enroll-face")
def enroll_face(
    student_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add face templates from up to 10 images. Photos are processed in memory and discarded."""
    s = _get(db, student_id)
    if not s.consent_given:
        raise HTTPException(403, "Student has not given consent for biometric processing")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(400, f"At most {MAX_FILES_PER_REQUEST} images per request")

    cfg = request.app.state.settings
    engine = get_engine(request)
    gallery = request.app.state.gallery
    vault = request.app.state.vault
    gallery.ensure(db)

    existing = db.scalar(select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == s.id)) or 0
    results, accepted = [], 0
    for f in files:
        item = {"filename": f.filename, "accepted": False, "reasons": [], "pose": None}
        results.append(item)
        data = f.file.read(cfg.max_upload_bytes + 1)
        if len(data) > cfg.max_upload_bytes:
            item["reasons"].append("file too large")
            continue
        try:
            img = decode_image(data)
        except HTTPException:
            item["reasons"].append("not a valid image")
            continue
        if existing + accepted >= cfg.max_embeddings_per_student:
            item["reasons"].append("template limit reached for this student")
            continue
        faces = engine.detect(img)
        if len(faces) == 0:
            item["reasons"].append("no face detected")
            continue
        if len(faces) > 1:
            item["reasons"].append("more than one face in the image")
            continue
        face = faces[0]
        q = assess(img, face, cfg)
        item["pose"] = q.pose
        if not q.ok:
            item["reasons"] += q.reasons
            continue
        emb = engine.embed(img, face)
        other, sim = gallery.best_other(emb, s.id)
        if other is not None and sim >= cfg.match_threshold:
            item["reasons"].append("this face already matches a different enrolled student")
            continue
        db.add(FaceEmbedding(student_id=s.id, pose=q.pose, quality=q.score, vector=vault.encrypt(emb)))
        accepted += 1
        item["accepted"] = True
    db.commit()
    gallery.invalidate()
    audit(db, user, "face.enroll", s.roll_no, f"accepted={accepted}/{len(files)}")
    return {"accepted": accepted, "submitted": len(files), "total_templates": existing + accepted, "results": results}


@router.delete("/{student_id}/biometrics", status_code=204)
def delete_biometrics(
    student_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    s = _get(db, student_id)
    db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == s.id))
    db.commit()
    request.app.state.gallery.invalidate()
    audit(db, user, "face.delete", s.roll_no)


@router.delete("/{student_id}", status_code=204)
def delete_student(student_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = _get(db, student_id)
    roll = s.roll_no
    db.delete(s)
    db.commit()
    request.app.state.gallery.invalidate()
    audit(db, admin, "student.delete", roll)
