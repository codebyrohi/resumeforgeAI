"""Export service: render the saved profile two ways from the same JSON.

  ats        -> plain single-column HTML -> PDF via Playwright (headless Chromium)
  cinematic  -> animated HTML page stored at exports/cinematic/{slug}.html, served at /r/{slug}

Both run as background jobs; the request returns 202 with a job id immediately.
"""
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.clients.storage_client import get_storage
from app.config import get_settings
from app.models import ExportJob, ExportType, JobStatus, Resume, User
from app.schemas import ExportJobOut, Profile
from app.services.resume_service import get_resume
from app.workers import tasks

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _safe_url(value: str) -> str:
    """Only allow http(s)/mailto links in rendered pages (blocks javascript: URLs)."""
    value = (value or "").strip()
    if not value:
        return ""
    scheme = urlparse(value).scheme.lower()
    if not scheme:
        return "https://" + value  # bare domain like "ada.dev"
    return value if scheme in ("http", "https", "mailto") else ""


_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
_env.filters["safe_url"] = _safe_url


def cinematic_key(slug: str) -> str:
    return f"exports/cinematic/{slug}.html"


def render_html(template: str, resume: Resume) -> str:
    profile = Profile.model_validate(resume.profile_json)
    return _env.get_template(template).render(p=profile, photo_url=resume.photo_url)


def html_to_pdf(html: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            return page.pdf(format="A4", print_background=False,
                            margin={"top": "16mm", "bottom": "16mm", "left": "16mm", "right": "16mm"})
        finally:
            browser.close()


def render_and_store(db: Session, job: ExportJob) -> str:
    """Called by the worker. Returns the output URL."""
    resume = db.get(Resume, job.resume_id)
    storage = get_storage()
    if job.type == ExportType.ats:
        pdf = html_to_pdf(render_html("ats.html", resume))
        return storage.put(f"exports/ats/{resume.id}/{job.id}.pdf", pdf, "application/pdf")
    html = render_html("cinematic.html", resume)
    return storage.put(cinematic_key(resume.slug), html.encode("utf-8"), "text/html; charset=utf-8")


def start_export(db: Session, user: User, export_type: ExportType,
                 background: BackgroundTasks) -> ExportJob:
    resume = get_resume(db, user)
    if resume is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Save your resume before exporting")
    job = ExportJob(resume_id=resume.id, type=export_type, status=JobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(tasks.run_export, job.id)
    return job


def get_job(db: Session, user: User, job_id: int) -> ExportJob:
    job = db.get(ExportJob, job_id)
    resume = db.get(Resume, job.resume_id) if job else None
    if job is None or resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export job not found")
    return job


def to_out(db: Session, job: ExportJob) -> ExportJobOut:
    out = ExportJobOut.model_validate(job)
    if job.type == ExportType.cinematic and job.status == JobStatus.done:
        slug = db.get(Resume, job.resume_id).slug
        out.public_url = f"{get_settings().public_api_base_url.rstrip('/')}/r/{slug}"
    return out
