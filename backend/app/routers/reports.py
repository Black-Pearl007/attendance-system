import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import course_for_user, get_current_user, get_db, session_for_user
from ..models import Attendance, ClassSession, Course, CourseStudent, Student, User, utcnow
from .sessions import build_detail

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _file(rows: list[list], header: list[str], fmt: str, name: str, sheet: str) -> Response:
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = sheet[:31]
        ws.append(header)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
        )
    if fmt != "csv":
        raise HTTPException(400, "format must be csv or xlsx")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


def course_summary(db: Session, course_id: int) -> dict:
    """Percentages are computed over CLOSED sessions only (open ones are incomplete)."""
    closed = db.scalars(
        select(ClassSession).where(ClassSession.course_id == course_id, ClassSession.status == "closed").order_by(ClassSession.starts_at)
    ).all()
    closed_ids = [s.id for s in closed]
    students = db.scalars(
        select(Student).join(CourseStudent, CourseStudent.student_id == Student.id).where(CourseStudent.course_id == course_id).order_by(Student.roll_no)
    ).all()
    marks: dict[tuple[int, int], str] = {}
    if closed_ids:
        for a in db.scalars(select(Attendance).where(Attendance.session_id.in_(closed_ids))):
            marks[(a.session_id, a.student_id)] = a.status

    rows = []
    for st in students:
        present = sum(marks.get((sid, st.id)) == "present" for sid in closed_ids)
        late = sum(marks.get((sid, st.id)) == "late" for sid in closed_ids)
        total = len(closed_ids)
        rows.append(
            {
                "student_id": st.id,
                "roll_no": st.roll_no,
                "name": st.name,
                "present": present,
                "late": late,
                "absent": total - present - late,
                "percent": round(100.0 * (present + late) / total, 1) if total else None,
            }
        )
    per_session = []
    for s in closed:
        n = len(students)
        attended = sum(marks.get((s.id, st.id)) in ("present", "late") for st in students)
        per_session.append(
            {"session_id": s.id, "title": s.title, "date": s.starts_at.date().isoformat(), "attended": attended, "enrolled": n,
             "percent": round(100.0 * attended / n, 1) if n else None}
        )
    return {"closed_sessions": len(closed_ids), "students": rows, "sessions": per_session}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course_q = select(Course.id)
    if user.role != "admin":
        course_q = course_q.where(Course.teacher_id == user.id)
    course_ids = list(db.scalars(course_q))
    since = utcnow() - timedelta(days=14)
    trend: dict[str, dict] = {}
    if course_ids:
        rows = db.execute(
            select(ClassSession.starts_at, Attendance.status)
            .join(Attendance, Attendance.session_id == ClassSession.id)
            .where(ClassSession.course_id.in_(course_ids), ClassSession.starts_at >= since)
        ).all()
        for starts, status in rows:
            d = trend.setdefault(starts.date().isoformat(), {"date": starts.date().isoformat(), "present": 0, "late": 0, "absent": 0})
            d[status] += 1
    open_sessions = (
        db.scalar(select(func.count()).select_from(ClassSession).where(ClassSession.course_id.in_(course_ids), ClassSession.status == "open"))
        if course_ids
        else 0
    )
    return {
        "students": db.scalar(select(func.count()).select_from(Student)) or 0,
        "courses": len(course_ids),
        "open_sessions": open_sessions or 0,
        "trend": sorted(trend.values(), key=lambda d: d["date"]),
    }


@router.get("/course/{course_id}")
def course_report(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = course_for_user(db, course_id, user)
    return {"course": {"id": course.id, "code": course.code, "name": course.name}, **course_summary(db, course_id)}


@router.get("/course/{course_id}/export")
def course_export(course_id: int, format: str = "csv", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = course_for_user(db, course_id, user)
    data = course_summary(db, course_id)
    rows = [[r["roll_no"], r["name"], r["present"], r["late"], r["absent"], r["percent"]] for r in data["students"]]
    return _file(rows, ["Roll no", "Name", "Present", "Late", "Absent", "Attendance %"], format, f"{course.code}_summary", "Summary")


@router.get("/session/{session_id}/export")
def session_export(session_id: int, format: str = "csv", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = session_for_user(db, session_id, user)
    d = build_detail(db, s)
    rows = [
        [r.roll_no, r.name, r.status, r.marked_at.isoformat(sep=" ", timespec="seconds") if r.marked_at else "", r.method or "",
         round(r.confidence, 3) if r.confidence is not None else ""]
        for r in d.roster
    ]
    return _file(rows, ["Roll no", "Name", "Status", "Marked at (UTC)", "Method", "Match score"], format, f"{d.course_code}_session_{s.id}", "Session")


@router.get("/student/{student_id}")
def student_report(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    st = db.get(Student, student_id)
    if st is None:
        raise HTTPException(404, "Student not found")
    out = []
    course_q = select(Course).join(CourseStudent, CourseStudent.course_id == Course.id).where(CourseStudent.student_id == student_id)
    if user.role != "admin":
        course_q = course_q.where(Course.teacher_id == user.id)
    for c in db.scalars(course_q):
        row = next((r for r in course_summary(db, c.id)["students"] if r["student_id"] == student_id), None)
        if row:
            out.append({"course_code": c.code, "course_name": c.name, **row})
    return {"student": {"id": st.id, "roll_no": st.roll_no, "name": st.name}, "courses": out}
