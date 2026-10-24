"""Signup, login, token refresh. Owns the `users` table only."""
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import User
from app.schemas import TokenResponse


def _tokens_for(user_id: int) -> TokenResponse:
    return TokenResponse(access_token=create_token(user_id, "access"),
                         refresh_token=create_token(user_id, "refresh"))


def signup(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    return user


def login(db: Session, email: str, password: str) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _tokens_for(user.id)


def refresh(db: Session, refresh_token: str) -> TokenResponse:
    try:
        user_id = decode_token(refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if db.get(User, user_id) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens_for(user_id)
