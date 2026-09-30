from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..emailer import send_email
from ..security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "refresh_token"
COOKIE_PATH = "/api/auth"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_refresh(db: Session, user: models.User, response: Response) -> None:
    raw = generate_token()
    db.add(
        models.RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=COOKIE_PATH,
    )


def _revoke_all(db: Session, user_id: int) -> None:
    db.execute(
        update(models.RefreshToken)
        .where(models.RefreshToken.user_id == user_id, models.RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    db.commit()


def _access(user: models.User) -> dict:
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(400, "Email already registered")
    default_role = db.scalar(select(models.Role).where(models.Role.name == "user"))
    user = models.User(
        full_name=data.full_name,
        email=email,
        hashed_password=hash_password(data.password),
        roles=[default_role] if default_role else [],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(models.User).where(models.User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    _issue_refresh(db, user, response)
    return _access(user)


@router.post("/refresh", response_model=schemas.Token)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(401, "No refresh token")
    row = db.scalar(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_token(refresh_token))
    )
    if not row:
        raise HTTPException(401, "Invalid refresh token")
    if row.revoked:                       # reuse of a rotated token: assume theft
        _revoke_all(db, row.user_id)
        raise HTTPException(401, "Refresh token reuse detected")
    if row.expires_at < _now():
        raise HTTPException(401, "Refresh token expired")
    user = db.get(models.User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User unavailable")

    row.revoked = True                    # rotate
    db.commit()
    _issue_refresh(db, user, response)
    return _access(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if refresh_token:
        db.execute(
            update(models.RefreshToken)
            .where(models.RefreshToken.token_hash == hash_token(refresh_token))
            .values(revoked=True)
        )
        db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/forgot-password")
def forgot_password(
    data: schemas.ForgotIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.scalar(select(models.User).where(models.User.email == data.email.lower()))
    if user and user.is_active:
        raw = generate_token()
        db.add(
            models.PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=_now() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            )
        )
        db.commit()
        link = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
        body = (
            f"Hi {user.full_name},\n\n"
            f"Use this link to reset your password (valid for {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes):\n"
            f"{link}\n\nIf you didn't request this, you can ignore this email."
        )
        background.add_task(send_email, user.email, "Reset your password", body)
    # same answer whether or not the email exists, to avoid account enumeration
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(data: schemas.ResetIn, db: Session = Depends(get_db)):
    row = db.scalar(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == hash_token(data.token)
        )
    )
    if not row or row.used or row.expires_at < _now():
        raise HTTPException(400, "Invalid or expired reset link")
    user = db.get(models.User, row.user_id)
    user.hashed_password = hash_password(data.new_password)
    row.used = True
    db.commit()
    _revoke_all(db, user.id)              # sign out every device
    return {"message": "Password updated. You can now sign in."}