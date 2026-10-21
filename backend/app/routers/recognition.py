import time

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, get_engine, session_for_user
from ..models import Student, User
from ..services import attendance as svc
from ..services.face_engine import yaw_ratio
from ..services.tracker import Observation, SessionTracker
from .students import decode_image

router = APIRouter(prefix="/api/recognition", tags=["recognition"])


def _tracker(request: Request, session_id: int) -> SessionTracker:
    trackers: dict[int, SessionTracker] = request.app.state.trackers
    if session_id not in trackers:
        trackers[session_id] = SessionTracker(request.app.state.settings)
    return trackers[session_id]


@router.post("/{session_id}/frame")
def process_frame(
    session_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recognise every face in one webcam frame and mark attendance when a track
    is (1) consistently identified, (2) enrolled in this course and (3) live."""
    cfg = request.app.state.settings
    session = session_for_user(db, session_id, user)
    if session.status != "open":
        raise HTTPException(409, "Session is closed")
    data = file.file.read(cfg.max_upload_bytes + 1)
    if len(data) > cfg.max_upload_bytes:
        raise HTTPException(413, "Frame too large")
    img = decode_image(data)
    H, W = img.shape[:2]

    engine = get_engine(request)
    gallery = request.app.state.gallery
    gallery.ensure(db)

    observations = []
    for f in engine.detect(img):
        m = gallery.match(engine.embed(img, f))
        x, y, w, h = f.box
        observations.append(Observation((x / W, y / H, w / W, h / H), m.student_id, m.score, yaw_ratio(f)))

    tracked = _tracker(request, session_id).update(observations, time.monotonic())
    enrolled = svc.enrolled_student_ids(db, session.course_id)

    faces_out, newly = [], []
    for track, ob in tracked:
        ident = track.identity
        live = track.liveness()
        student = db.get(Student, ident) if ident else None
        status, marked = "verifying", False

        if track.verdict_unknown:
            status = "unknown"
        elif ident is not None:
            if ident not in enrolled:
                status = "not_enrolled"
            elif track.marked:
                status, marked = "marked", True
            elif not live["passed"]:
                status = "turn_head"
            else:
                row, created = svc.mark_present(db, session, ident, track.confidence)
                track.marked = True
                status, marked = "marked", True
                if created:
                    newly.append({"student_id": ident, "name": student.name, "roll_no": student.roll_no, "status": row.status})

        faces_out.append(
            {
                "track_id": track.id,
                "box": [round(v, 4) for v in ob.box],
                "status": status,
                "student": {"id": student.id, "name": student.name, "roll_no": student.roll_no} if student else None,
                "score": round(ob.score, 3),
                "liveness": live,
                "marked": marked,
            }
        )
    return {"faces": faces_out, "newly_marked": newly}


@router.post("/{session_id}/reset")
def reset_tracking(session_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session_for_user(db, session_id, user)
    request.app.state.trackers.pop(session_id, None)
    return {"ok": True}
