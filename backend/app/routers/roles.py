from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission

router = APIRouter(prefix="/roles", tags=["roles"])
PROTECTED = {"admin", "user"}


def _perms(db: Session, ids: list[int]):
    return list(db.scalars(select(models.Permission).where(models.Permission.id.in_(ids))).all())


@router.get("", response_model=list[schemas.RoleOut])
def list_roles(db: Session = Depends(get_db), _=Depends(require_permission("roles:read"))):
    return db.scalars(select(models.Role).order_by(models.Role.id)).all()


@router.get("/permissions", response_model=list[schemas.PermissionOut])
def list_permissions(db: Session = Depends(get_db), _=Depends(require_permission("roles:read"))):
    return db.scalars(select(models.Permission).order_by(models.Permission.code)).all()


@router.post("", response_model=schemas.RoleOut, status_code=201)
def create_role(
    data: schemas.RoleIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:create")),
):
    if db.scalar(select(models.Role).where(models.Role.name == data.name)):
        raise HTTPException(400, "Role already exists")
    role = models.Role(name=data.name, description=data.description, permissions=_perms(db, data.permission_ids))
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}", response_model=schemas.RoleOut)
def update_role(
    role_id: int,
    data: schemas.RoleIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:update")),
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    if role.name == "admin":
        raise HTTPException(400, "The admin role cannot be modified")
    role.name, role.description = data.name, data.description
    role.permissions = _perms(db, data.permission_ids)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:delete")),
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    if role.name in PROTECTED:
        raise HTTPException(400, "This role is protected")
    db.delete(role)
    db.commit()