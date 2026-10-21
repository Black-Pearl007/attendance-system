from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..deps import audit, get_current_user, get_db, require_admin
from ..models import AuditLog, FaceEmbedding, User, utcnow

router = APIRouter(prefix="/api/privacy", tags=["privacy"])

POLICY = """\
FACE-RECOGNITION ATTENDANCE - PRIVACY NOTICE (template)

Purpose: recording class attendance. No other use is made of face data.
Data stored: for each consenting student, a small numeric face template
(embedding) and its pose/quality score. Camera images are processed in memory
and are NOT stored. Attendance records (status, time, match score) are stored.
Legal basis: explicit consent (GDPR Art. 6(1)(a) and 9(2)(a)) - biometric data
used to identify a person is a special category. Consent is optional: a manual
roll-call is always available as an alternative and carries no penalty.
Security: templates are encrypted at rest (Fernet); access requires login;
sensitive actions are written to an audit log.
Retention: templates are deleted when consent is withdrawn, when the student is
deleted, or automatically after the configured retention period.
Your rights: access, rectification, erasure and withdrawal of consent at any
time - ask a teacher/administrator or use the delete-biometrics action.

(This is a template for a university project, not legal advice. Have your data
protection officer review it before any real deployment.)
"""


@router.get("/policy")
def policy(request: Request):
    return {"policy": POLICY, "retention_days": request.app.state.settings.retention_days}


@router.post("/purge-expired")
def purge_expired(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Delete face templates older than the retention period."""
    cutoff = utcnow() - timedelta(days=request.app.state.settings.retention_days)
    old = db.scalars(select(FaceEmbedding.id).where(FaceEmbedding.created_at < cutoff)).all()
    if old:
        db.execute(delete(FaceEmbedding).where(FaceEmbedding.id.in_(old)))
        db.commit()
        request.app.state.gallery.invalidate()
    audit(db, admin, "privacy.purge", "face_embeddings", f"deleted={len(old)}")
    return {"deleted": len(old)}


@router.get("/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [
        {"id": r.id, "user_id": r.user_id, "action": r.action, "target": r.target, "detail": r.detail,
         "created_at": r.created_at.isoformat() + "Z"}
        for r in rows
    ]
