import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import auth, export, public, resume

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="ResumeForgeAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # JWT travels in the Authorization header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(export.router)
app.include_router(public.router)

if settings.storage_backend == "local":
    # Dev-only stand-in for public S3 URLs. Only the public prefixes are served;
    # raw uploads under uploads/ stay private.
    root = Path(settings.local_storage_dir)
    for prefix in ("photos", "exports"):
        (root / prefix).mkdir(parents=True, exist_ok=True)
        app.mount(f"/files/{prefix}", StaticFiles(directory=root / prefix), name=f"files-{prefix}")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
