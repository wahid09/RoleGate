from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from .. import audit, models, schemas
from ..database import get_db
from ..deps import require_permission
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_permission("users:read"))):
    return db.scalars(select(models.User).order_by(models.User.id)).all()


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:create")),
):
    email = data.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(400, "Email already registered")
    if data.role_ids:
        roles = list(db.scalars(select(models.Role).where(models.Role.id.in_(data.role_ids))).all())
    else:  # no roles chosen: fall back to the default "user" role
        default = db.scalar(select(models.Role).where(models.Role.name == "user"))
        roles = [default] if default else []
    user = models.User(
        full_name=data.full_name,
        email=email,
        hashed_password=hash_password(data.password),
        is_active=data.is_active,
        email_verified=True,
        roles=roles,
    )
    db.add(user)
    db.flush()  # assigns user.id
    audit.record(
        db, request, "user.create", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "roles": sorted(r.name for r in roles)},
    )
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/roles", response_model=schemas.UserOut)
def set_roles(
    user_id: int,
    body: schemas.UserRolesIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    before = sorted(r.name for r in user.roles)
    user.roles = list(db.scalars(select(models.Role).where(models.Role.id.in_(body.role_ids))).all())
    audit.record(
        db, request, "user.roles.update", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "before": before, "after": sorted(r.name for r in user.roles)},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=schemas.UserOut)
def set_active(
    user_id: int,
    body: schemas.UserActiveIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == actor.id:
        raise HTTPException(400, "You cannot disable your own account")
    user.is_active = body.is_active
    audit.record(
        db, request, "user.active.update", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "is_active": body.is_active},
    )
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}/2fa", response_model=schemas.UserOut)
def reset_two_factor(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    user = db.get(models.User, user_id)
    if not user.mfa_enabled:
        raise HTTPException(400, "Two-factor authentication is not enabled for this user")
    removed = len(user.passkeys)
    user.passkeys.clear()
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_step = None
    db.execute(delete(models.RecoveryCode).where(models.RecoveryCode.user_id == user.id))
    audit.record(
        db, request, "user.2fa.reset", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "passkeys_removed": removed},
    )
    db.commit()
    db.refresh(user)
    return user

def _active_sessions(db: Session, user_id: int):
    return db.scalars(
        select(models.RefreshToken)
        .where(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked.is_(False),
            models.RefreshToken.expires_at > datetime.now(UTC),
        )
        .order_by(models.RefreshToken.created_at.desc())
    ).all()


def _target(db: Session, user_id: int, actor: models.User) -> models.User:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == actor.id:
        raise HTTPException(400, "Use your Profile page to manage your own sessions")
    return user


@router.get("/{user_id}/sessions", response_model=list[schemas.SessionOut])
def list_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    user = _target(db, user_id, actor)
    return [
        schemas.SessionOut(
            id=r.session_id, user_agent=r.user_agent, ip=r.ip,
            started_at=r.session_started_at, last_active_at=r.created_at, current=False,
        )
        for r in _active_sessions(db, user.id)
    ]


@router.post("/{user_id}/sessions/revoke-all")
def revoke_all_user_sessions(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    """Sign the user out everywhere, immediately: refresh tokens AND already-issued access tokens stop working."""
    user = _target(db, user_id, actor)
    result = db.execute(
        update(models.RefreshToken)
        .where(models.RefreshToken.user_id == user.id, models.RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    user.tokens_valid_after = datetime.now(UTC)
    audit.record(
        db, request, "user.sessions.revoke_all", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "sessions": result.rowcount},
    )
    db.commit()
    return {"revoked": result.rowcount}


@router.post("/{user_id}/sessions/{session_id}/revoke")
def revoke_user_session(
    user_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("users:update")),
):
    """Sign out one device. Its access token can still work for up to ACCESS_TOKEN_EXPIRE_MINUTES."""
    user = _target(db, user_id, actor)
    result = db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.session_id == session_id,
            models.RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(404, "Session not found")
    audit.record(
        db, request, "user.session.revoke", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email, "session": session_id[:8]},
    )
    db.commit()
    return {"message": "Session signed out"}

SORTS = {"id": models.User.id, "name": models.User.full_name, "email": models.User.email}


@router.get("/search", response_model=schemas.UserPage)
def search_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=100, description="Substring of name or email"),
    role_id: int | None = Query(None),
    status: Literal["active", "disabled"] | None = Query(None),
    mfa: Literal["on", "off"] | None = Query(None, description="Has an authenticator app or a passkey"),
    sort: Literal["id", "name", "email"] = "id",
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
):
    q = select(models.User)

    term = (search or "").strip()
    if term:
        # escape LIKE wildcards so "50%" or "a_b" are searched literally
        like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        q = q.where(
            or_(models.User.full_name.ilike(like, escape="\\"), models.User.email.ilike(like, escape="\\"))
        )
    if role_id is not None:
        q = q.where(models.User.roles.any(models.Role.id == role_id))
    if status:
        q = q.where(models.User.is_active.is_(status == "active"))
    if mfa:
        has_mfa = or_(
            models.User.totp_enabled.is_(True),
            exists().where(models.WebAuthnCredential.user_id == models.User.id),
        )
        q = q.where(has_mfa if mfa == "on" else ~has_mfa)

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    column = SORTS[sort]
    ordering = (column.asc() if order == "asc" else column.desc(), models.User.id)  # id = stable tie-break
    items = db.scalars(q.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}