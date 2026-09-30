from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit, models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..emailer import send_email
from ..ratelimit import login_failed, login_locked, login_ok, rate_limit
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
NOT_VERIFIED = "Email not verified"   # the frontend matches on this text


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


def _send_verification(db: Session, user: models.User, background: BackgroundTasks) -> None:
    raw = generate_token()
    db.add(
        models.EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS),
        )
    )
    db.commit()
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw}"
    body = (
        f"Hi {user.full_name},\n\n"
        f"Please confirm your email address (link valid for {settings.VERIFY_TOKEN_EXPIRE_HOURS} hours):\n"
        f"{link}\n\nIf you didn't create an account, you can ignore this email."
    )
    background.add_task(send_email, user.email, "Verify your email address", body)


@router.post(
    "/register",
    response_model=schemas.UserOut,
    status_code=201,
    dependencies=[Depends(rate_limit("register", 10, 3600))],
)
def register(
    data: schemas.RegisterIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(400, "Email already registered")
    default_role = db.scalar(select(models.Role).where(models.Role.name == "user"))
    user = models.User(
        full_name=data.full_name,
        email=email,
        hashed_password=hash_password(data.password),
        email_verified=False,
        roles=[default_role] if default_role else [],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit.record(db, request, "auth.register", actor=user, target_type="user", target_id=user.id)
    _send_verification(db, user, background)   # commits the audit row too
    db.refresh(user)
    return user


@router.post("/verify-email", dependencies=[Depends(rate_limit("verify", 20, 900))])
def verify_email(data: schemas.VerifyIn, db: Session = Depends(get_db)):
    row = db.scalar(
        select(models.EmailVerificationToken).where(
            models.EmailVerificationToken.token_hash == hash_token(data.token)
        )
    )
    if not row or row.expires_at < _now():
        raise HTTPException(400, "Invalid or expired verification link")
    user = db.get(models.User, row.user_id)
    user.email_verified = True
    row.used = True
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification", dependencies=[Depends(rate_limit("resend", 3, 3600))])
def resend_verification(
    data: schemas.ForgotIn, background: BackgroundTasks, db: Session = Depends(get_db)
):
    user = db.scalar(select(models.User).where(models.User.email == data.email.lower()))
    if user and user.is_active and not user.email_verified:
        _send_verification(db, user, background)
    return {"message": "If that account still needs verification, a new email has been sent."}


@router.post(
    "/login",
    response_model=schemas.Token,
    dependencies=[Depends(rate_limit("login", 10, 60))],
)
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form.username.lower()
    if login_locked(email):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")

    user = db.scalar(select(models.User).where(models.User.email == email))
    if not user or not verify_password(form.password, user.hashed_password):
        login_failed(email)
        audit.record(db, request, "auth.login_failed", actor=user, actor_email=email,
                     detail={"reason": "bad_credentials"})
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if not user.email_verified:
        raise HTTPException(403, NOT_VERIFIED)

    login_ok(email)
    audit.record(db, request, "auth.login", actor=user)
    _issue_refresh(db, user, response)         # commits the audit row too
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


@router.post("/change-password", dependencies=[Depends(rate_limit("change-pw", 5, 900))])
def change_password(
    data: schemas.ChangePasswordIn,
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(400, "New password must be different from the current one")
    user.hashed_password = hash_password(data.new_password)
    audit.record(db, request, "auth.password.change", actor=user, target_type="user", target_id=user.id)
    db.commit()
    _revoke_all(db, user.id)
    _issue_refresh(db, user, response)
    return {"message": "Password changed. Other devices have been signed out."}


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5, 900))])
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
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10, 900))])
def reset_password(data: schemas.ResetIn, request: Request, db: Session = Depends(get_db)):
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
    audit.record(db, request, "auth.password.reset", actor=user, target_type="user", target_id=user.id)
    db.commit()
    _revoke_all(db, user.id)
    return {"message": "Password updated. You can now sign in."}