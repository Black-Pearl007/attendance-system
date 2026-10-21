from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attendance, ClassSession, CourseStudent, utcnow


def enrolled_student_ids(db: Session, course_id: int) -> set[int]:
    return set(db.scalars(select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)))


def mark_present(
    db: Session, session: ClassSession, student_id: int, confidence: float | None, method: str = "face"
) -> tuple[Attendance, bool]:
    """Idempotent: a student is marked at most once per session. Returns (row, created)."""
    existing = db.scalar(
        select(Attendance).where(Attendance.session_id == session.id, Attendance.student_id == student_id)
    )
    if existing:
        return existing, False
    now = utcnow()
    late = now > session.starts_at + timedelta(minutes=session.late_after_minutes)
    row = Attendance(
        session_id=session.id,
        student_id=student_id,
        status="late" if late else "present",
        marked_at=now,
        confidence=confidence,
        method=method,
    )
    db.add(row)
    db.commit()
    return row, True


def close_session(db: Session, session: ClassSession) -> int:
    """Close the session and mark every enrolled student without a record as absent."""
    if session.status == "closed":
        return 0
    marked = set(db.scalars(select(Attendance.student_id).where(Attendance.session_id == session.id)))
    absent = enrolled_student_ids(db, session.course_id) - marked
    for sid in absent:
        db.add(Attendance(session_id=session.id, student_id=sid, status="absent", method="auto-absent"))
    session.status = "closed"
    session.ended_at = utcnow()
    db.commit()
    return len(absent)
