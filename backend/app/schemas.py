"""Pydantic models: API request/response bodies and the fixed resume profile schema.

`Profile` is the single structured document stored in `resumes.profile_json`. The LLM's
output is validated against it before anything is saved, and both export templates render
from it, so the ATS PDF and the cinematic page never drift apart.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ExportType, JobStatus


# ---------- Resume profile (stored as JSON) ----------

class _Lenient(BaseModel):
    # LLM output sometimes adds stray keys; drop them rather than fail validation.
    model_config = ConfigDict(extra="ignore")


class Basics(_Lenient):
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""


class Education(_Lenient):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""
    details: str = ""


class Experience(_Lenient):
    company: str = ""
    title: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class Project(_Lenient):
    name: str = ""
    description: str = ""
    tech: list[str] = Field(default_factory=list)
    url: str = ""


class Link(_Lenient):
    label: str = ""
    url: str = ""


class Profile(_Lenient):
    basics: Basics = Field(default_factory=Basics)
    summary: str = ""
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)


# ---------- Auth ----------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt only uses the first 72 bytes


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


# ---------- Resume ----------

class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    photo_url: str | None
    profile: Profile = Field(validation_alias="profile_json")
    updated_at: datetime
    public_url: str | None = None


class ResumeUpsert(BaseModel):
    profile: Profile
    # Opt-in LLM spelling/grammar pass on free-text fields before save.
    correct_text: bool = False


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: JobStatus
    parsed_json: Profile | None = None
    error: str | None = None
    created_at: datetime


# ---------- Export ----------

class ExportRequest(BaseModel):
    type: ExportType


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ExportType
    status: JobStatus
    output_url: str | None
    error: str | None = None
    public_url: str | None = None
    created_at: datetime
