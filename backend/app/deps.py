from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .models import AuditLog, ClassSession, Course, User
from .security import decode_access_token
from .services.face_engine import ModelsMissing

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if creds is None:
        raise unauthorized
    uid = decode_access_token(creds.credentials, request.app.state.settings.secret_key)
    user = db.get(User, uid) if uid else None
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def get_engine(request: Request):
    try:
        return request.app.state.engine_provider()
    except ModelsMissing as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


def course_for_user(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found")
    if user.role != "admin" and course.teacher_id != user.id:
        raise HTTPException(403, "Not your course")
    return course


def session_for_user(db: Session, session_id: int, user: User) -> ClassSession:
    s = db.get(ClassSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    course_for_user(db, s.course_id, user)
    return s


def audit(db: Session, user: User | None, action: str, target: str = "", detail: str = "") -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, target=target, detail=detail))
    db.commit()
