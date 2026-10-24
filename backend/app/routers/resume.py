from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ResumeOut, ResumeUpsert, UploadOut
from app.services import resume_service

router = APIRouter(prefix="/resume", tags=["resume"])


@router.get("", response_model=ResumeOut)
def get_resume(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = resume_service.get_resume(db, user)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume yet")
    return resume_service.to_out(db, resume)


@router.put("", response_model=ResumeOut)
def upsert_resume(body: ResumeUpsert, background: BackgroundTasks,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = resume_service.upsert(db, user, body.profile, body.correct_text, background)
    return resume_service.to_out(db, resume)


@router.post("/upload", response_model=UploadOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(background: BackgroundTasks, file: UploadFile = File(...),
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await resume_service.start_upload(db, user, file, background)


@router.get("/upload/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return resume_service.get_upload(db, user, upload_id)


@router.post("/photo", response_model=ResumeOut)
async def upload_photo(
    file: UploadFile = File(...),
    crop_x: int | None = Form(None),
    crop_y: int | None = Form(None),
    crop_size: int | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    crop = None
    if None not in (crop_x, crop_y, crop_size):
        crop = (crop_x, crop_y, crop_size)
    resume = await resume_service.upload_photo(db, user, file, crop)
    return resume_service.to_out(db, resume)
