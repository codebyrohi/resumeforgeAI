from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ExportJobOut, ExportRequest
from app.services import export_service

router = APIRouter(prefix="/resume/export", tags=["export"])


@router.post("", response_model=ExportJobOut, status_code=status.HTTP_202_ACCEPTED)
def start_export(body: ExportRequest, background: BackgroundTasks,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = export_service.start_export(db, user, body.type, background)
    return export_service.to_out(db, job)


@router.get("/{job_id}", response_model=ExportJobOut)
def get_export(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return export_service.to_out(db, export_service.get_job(db, user, job_id))
