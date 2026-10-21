from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..deps import audit, course_for_user, get_current_user, get_db
from ..models import Course, CourseStudent, Student, User
from ..schemas import CourseCreate, CourseOut, CourseStudentsIn, StudentOut
from .students import _out as student_out

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _course_out(db: Session, c: Course) -> CourseOut:
    n = db.scalar(select(func.count()).select_from(CourseStudent).where(CourseStudent.course_id == c.id)) or 0
    out = CourseOut.model_validate(c)
    out.student_count = n
    return out


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Course).order_by(Course.code)
    if user.role != "admin":
        q = q.where(Course.teacher_id == user.id)
    return [_course_out(db, c) for c in db.scalars(q)]


@router.post("", response_model=CourseOut, status_code=201)
def create_course(body: CourseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    code = body.code.strip().upper()
    if db.scalar(select(Course).where(Course.code == code)):
        raise HTTPException(409, "Course code already exists")
    c = Course(code=code, name=body.name.strip(), teacher_id=user.id)
    db.add(c)
    db.commit()
    audit(db, user, "course.create", code)
    return _course_out(db, c)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = course_for_user(db, course_id, user)
    db.delete(c)
    db.commit()
    audit(db, user, "course.delete", c.code)


@router.get("/{course_id}/students", response_model=list[StudentOut])
def course_students(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course_for_user(db, course_id, user)
    q = (
        select(Student)
        .join(CourseStudent, CourseStudent.student_id == Student.id)
        .where(CourseStudent.course_id == course_id)
        .order_by(Student.roll_no)
    )
    return [student_out(db, s) for s in db.scalars(q)]


@router.post("/{course_id}/students", response_model=CourseOut)
def add_students(
    course_id: int, body: CourseStudentsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    c = course_for_user(db, course_id, user)
    have = set(db.scalars(select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)))
    valid = set(db.scalars(select(Student.id).where(Student.id.in_(body.student_ids))))
    for sid in valid - have:
        db.add(CourseStudent(course_id=course_id, student_id=sid))
    db.commit()
    return _course_out(db, c)


@router.delete("/{course_id}/students/{student_id}", status_code=204)
def remove_student(course_id: int, student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course_for_user(db, course_id, user)
    db.execute(delete(CourseStudent).where(CourseStudent.course_id == course_id, CourseStudent.student_id == student_id))
    db.commit()
