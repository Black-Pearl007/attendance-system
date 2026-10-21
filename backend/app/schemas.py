from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer


def _as_utc(d: datetime) -> str:
    return d.replace(tzinfo=timezone.utc).isoformat() if d.tzinfo is None else d.isoformat()


UTCDatetime = Annotated[datetime, PlainSerializer(_as_utc, return_type=str)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth -------------------------------------------------------------------
class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    role: Literal["admin", "teacher"] = "teacher"


# ---- students ---------------------------------------------------------------
class StudentCreate(BaseModel):
    roll_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    consent: bool = False


class StudentOut(ORM):
    id: int
    roll_no: str
    name: str
    email: str | None
    consent_given: bool
    consent_at: UTCDatetime | None
    face_count: int = 0


class ConsentIn(BaseModel):
    given: bool


# ---- courses / sessions -----------------------------------------------------
class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=160)


class CourseOut(ORM):
    id: int
    code: str
    name: str
    teacher_id: int | None
    student_count: int = 0


class CourseStudentsIn(BaseModel):
    student_ids: list[int]


class SessionCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=160)
    late_after_minutes: int = Field(default=10, ge=0, le=240)


class SessionOut(ORM):
    id: int
    course_id: int
    title: str
    starts_at: UTCDatetime
    ended_at: UTCDatetime | None
    status: str
    late_after_minutes: int


class RosterRow(BaseModel):
    student_id: int
    roll_no: str
    name: str
    status: Literal["present", "late", "absent", "pending"]
    marked_at: UTCDatetime | None = None
    confidence: float | None = None
    method: str | None = None


class SessionDetail(BaseModel):
    session: SessionOut
    course_code: str
    course_name: str
    roster: list[RosterRow]


class ManualMarkIn(BaseModel):
    student_id: int
    status: Literal["present", "late", "absent"]
