"""Background jobs: LLM parsing/correction and export rendering.

Run via FastAPI BackgroundTasks (in-process, after the response is sent). Each job opens its
own DB session and records its outcome on the job row, which the frontend polls. The
function signatures take plain ids/bytes so they can move to Celery + Redis unchanged.
"""
import logging

from app.clients.llm_client import LLMError, get_llm_client
from app.db import SessionLocal
from app.models import ExportJob, JobStatus, Resume, ResumeUpload
from app.schemas import Profile
from app.services.text_extract import extract_text

log = logging.getLogger(__name__)


def parse_upload(upload_id: int, kind: str, data: bytes) -> None:
    with SessionLocal() as db:
        upload = db.get(ResumeUpload, upload_id)
        if upload is None:
            return
        upload.status = JobStatus.processing
        db.commit()
        try:
            text = extract_text(kind, data)
            if len(text) < 50:
                raise ValueError("No readable text found (scanned or image-only file?)")
            llm = get_llm_client()
            profile = llm.parse_resume(text)
            try:
                profile = llm.correct_profile(profile)
            except LLMError as e:
                log.warning("Correction skipped for upload %s: %s", upload_id, e)
            upload.parsed_json = profile.model_dump()
            upload.status = JobStatus.done
        except (LLMError, ValueError) as e:
            upload.status = JobStatus.failed
            upload.error = f"Autofill unavailable - you can still fill the form manually. ({e})"
        except Exception as e:  # noqa: BLE001 - never leave a job stuck in "processing"
            log.exception("parse_upload %s crashed", upload_id)
            upload.status = JobStatus.failed
            upload.error = f"Unexpected error while parsing: {type(e).__name__}"
        db.commit()


def correct_saved_resume(resume_id: int, snapshot: dict) -> None:
    """Spelling/grammar pass on an already-saved profile. Skipped if the user edited it since."""
    try:
        corrected = get_llm_client().correct_profile(Profile.model_validate(snapshot))
    except Exception as e:  # noqa: BLE001 - correction is optional; the save already happened
        log.warning("Correction skipped for resume %s: %s", resume_id, e)
        return
    with SessionLocal() as db:
        resume = db.get(Resume, resume_id)
        if resume is not None and resume.profile_json == snapshot:
            resume.profile_json = corrected.model_dump()
            db.commit()


def run_export(job_id: int) -> None:
    from app.services.export_service import render_and_store

    with SessionLocal() as db:
        job = db.get(ExportJob, job_id)
        if job is None:
            return
        job.status = JobStatus.processing
        db.commit()
        try:
            job.output_url = render_and_store(db, job)
            job.status = JobStatus.done
        except Exception as e:  # noqa: BLE001
            log.exception("export %s failed", job_id)
            job.status = JobStatus.failed
            job.error = f"{type(e).__name__}: {e}"[:1000]
        db.commit()
