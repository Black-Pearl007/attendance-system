from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import audit, course_for_user, get_current_user, get_db, session_for_user
from ..models import Attendance, ClassSession, Course, CourseStudent, Student, User, utcnow
from ..schemas import ManualMarkIn, RosterRow, SessionCreate, SessionDetail, SessionOut
from ..services import attendance as svc

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(course_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(ClassSession).order_by(ClassSession.starts_at.desc())
    if course_id is not None:
        course_for_user(db, course_id, user)
        q = q.where(ClassSession.course_id == course_id)
    elif user.role != "admin":
        q = q.join(Course, Course.id == ClassSession.course_id).where(Course.teacher_id == user.id)
    return db.scalars(q.limit(200)).all()


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course_for_user(db, body.course_id, user)
    s = ClassSession(
        course_id=body.course_id,
        title=body.title.strip(),
        late_after_minutes=body.late_after_minutes,
        created_by=user.id,
    )
    db.add(s)
    db.commit()
    return s


def build_detail(db: Session, s: ClassSession) -> SessionDetail:
    course = db.get(Course, s.course_id)
    students = db.scalars(
        select(Student)
        .join(CourseStudent, CourseStudent.student_id == Student.id)
        .where(CourseStudent.course_id == s.course_id)
        .order_by(Student.roll_no)
    ).all()
    marks = {a.student_id: a for a in db.scalars(select(Attendance).where(Attendance.session_id == s.id))}
    roster = []
    for st in students:
        a = marks.get(st.id)
        roster.append(
            RosterRow(
                student_id=st.id,
                roll_no=st.roll_no,
                name=st.name,
                status=a.status if a else "pending",
                marked_at=a.marked_at if a else None,
                confidence=a.confidence if a else None,
                method=a.method if a else None,
            )
        )
    return SessionDetail(session=SessionOut.model_validate(s), course_code=course.code, course_name=course.name, roster=roster)


@router.get("/{session_id}", response_model=SessionDetail)
def session_detail(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return build_detail(db, session_for_user(db, session_id, user))


@router.post("/{session_id}/close", response_model=SessionDetail)
def close(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = session_for_user(db, session_id, user)
    n = svc.close_session(db, s)
    audit(db, user, "session.close", str(s.id), f"auto_absent={n}")
    return build_detail(db, s)


@router.post("/{session_id}/attendance/manual", response_model=SessionDetail)
def manual_mark(
    session_id: int, body: ManualMarkIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Teacher override (e.g. camera failure, late correction). Always audited."""
    s = session_for_user(db, session_id, user)
    if body.student_id not in svc.enrolled_student_ids(db, s.course_id):
        raise HTTPException(400, "Student is not enrolled in this course")
    row = db.scalar(select(Attendance).where(Attendance.session_id == s.id, Attendance.student_id == body.student_id))
    if row is None:
        row = Attendance(session_id=s.id, student_id=body.student_id, status=body.status, method="manual")
        db.add(row)
    else:
        row.status, row.method, row.marked_at, row.confidence = body.status, "manual", utcnow(), None
    db.commit()
    audit(db, user, "attendance.manual", f"session={s.id} student={body.student_id}", body.status)
    return build_detail(db, s)
