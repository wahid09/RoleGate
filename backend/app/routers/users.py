from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
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
    if not user:
        raise HTTPException(404, "User not found")
    if not user.totp_enabled:
        raise HTTPException(400, "Two-factor authentication is not enabled for this user")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_step = None
    db.execute(delete(models.RecoveryCode).where(models.RecoveryCode.user_id == user.id))
    audit.record(
        db, request, "user.2fa.reset", actor=actor, target_type="user", target_id=user.id,
        detail={"email": user.email},
    )
    db.commit()
    db.refresh(user)
    return user