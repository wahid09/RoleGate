from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_permission("users:read"))):
    return db.scalars(select(models.User).order_by(models.User.id)).all()


@router.put("/{user_id}/roles", response_model=schemas.UserOut)
def set_roles(
    user_id: int,
    body: schemas.UserRolesIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:update")),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.roles = list(db.scalars(select(models.Role).where(models.Role.id.in_(body.role_ids))).all())
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=schemas.UserOut)
def set_active(
    user_id: int,
    body: schemas.UserActiveIn,
    db: Session = Depends(get_db),
    current=Depends(require_permission("users:update")),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == current.id:
        raise HTTPException(400, "You cannot disable your own account")
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user

@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:create")),
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
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user