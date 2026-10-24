"""Resume service - the single source of truth per user.

CRUD on the profile JSON, upload validation + hand-off to the parser job, photo handling.
LLM work is always queued to the background worker, never run on the request thread.
"""
import io
import re
import secrets
import uuid

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.storage_client import get_storage
from app.config import get_settings
from app.models import ExportJob, ExportType, JobStatus, Resume, ResumeUpload, User
from app.schemas import Profile, ResumeOut
from app.services import file_validation
from app.workers import tasks

PHOTO_SIZE = 512


def _make_slug(profile: Profile) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", profile.basics.full_name.lower()).strip("-")[:50] or "resume"
    return f"{base}-{secrets.token_hex(3)}"


def get_resume(db: Session, user: User) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user.id))


def get_or_create_resume(db: Session, user: User, profile: Profile | None = None) -> Resume:
    resume = get_resume(db, user)
    if resume is not None:
        return resume
    profile = profile or Profile()
    resume = Resume(user_id=user.id, slug=_make_slug(profile), profile_json=profile.model_dump())
    db.add(resume)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent create for the same user lost the race on UNIQUE(user_id): use the winner.
        db.rollback()
        resume = get_resume(db, user)
        if resume is None:
            raise
    db.refresh(resume)
    return resume


def to_out(db: Session, resume: Resume) -> ResumeOut:
    out = ResumeOut.model_validate(resume)
    published = db.scalar(select(ExportJob.id).where(
        ExportJob.resume_id == resume.id,
        ExportJob.type == ExportType.cinematic,
        ExportJob.status == JobStatus.done,
    ).limit(1))
    if published:
        out.public_url = f"{get_settings().public_api_base_url.rstrip('/')}/r/{resume.slug}"
    return out


def upsert(db: Session, user: User, profile: Profile, correct_text: bool,
           background: BackgroundTasks) -> Resume:
    resume = get_or_create_resume(db, user, profile)
    resume.profile_json = profile.model_dump()
    db.commit()
    db.refresh(resume)
    if correct_text:
        # The manually typed data is already saved; correction is an enhancement applied
        # afterwards, so a Groq failure never blocks the save.
        background.add_task(tasks.correct_saved_resume, resume.id, resume.profile_json)
    return resume


async def start_upload(db: Session, user: User, file: UploadFile,
                       background: BackgroundTasks) -> ResumeUpload:
    data = await file_validation.read_limited(file, get_settings().max_resume_bytes)
    kind = file_validation.detect_resume_kind(file.filename or "", data)

    key = f"uploads/{user.id}/{uuid.uuid4().hex}.{kind}"
    content_type = file_validation.PDF_MIME if kind == "pdf" else file_validation.DOCX_MIME
    file_url = get_storage().put(key, data, content_type)

    upload = ResumeUpload(user_id=user.id, file_url=file_url, status=JobStatus.pending)
    db.add(upload)
    db.commit()
    db.refresh(upload)
    background.add_task(tasks.parse_upload, upload.id, kind, data)
    return upload


def get_upload(db: Session, user: User, upload_id: int) -> ResumeUpload:
    upload = db.get(ResumeUpload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return upload


async def upload_photo(db: Session, user: User, file: UploadFile,
                       crop: tuple[int, int, int] | None) -> Resume:
    """Validate, crop to a square, re-encode as JPEG (strips EXIF/GPS), store, update photo_url."""
    data = await file_validation.read_limited(file, get_settings().max_photo_bytes)
    file_validation.detect_image_kind(data)
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not read image")

    if crop is not None:
        x, y, size = crop
        if size <= 0 or x < 0 or y < 0 or x + size > img.width or y + size > img.height:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Crop box is outside the image")
        img = img.crop((x, y, x + size, y + size))
    else:
        img = ImageOps.fit(img, (min(img.size),) * 2)  # centre square crop
    img = img.resize((PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    url = get_storage().put(f"photos/{user.id}/{uuid.uuid4().hex}.jpg", out.getvalue(), "image/jpeg")

    resume = get_or_create_resume(db, user)
    resume.photo_url = url
    db.commit()
    db.refresh(resume)
    return resume
