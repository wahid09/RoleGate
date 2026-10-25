from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, models, schemas
from ..database import get_db
from ..deps import require_permission
from ..seed import PERMISSIONS

router = APIRouter(prefix="/permissions", tags=["permissions"])
BUILTIN = {code for code, _ in PERMISSIONS}


def _role_map(db: Session) -> dict[int, list[str]]:
    rows = db.execute(
        select(models.role_permissions.c.permission_id, models.Role.name)
        .select_from(models.role_permissions)
        .join(models.Role, models.Role.id == models.role_permissions.c.role_id)
        .order_by(models.Role.name)
    ).all()
    out: dict[int, list[str]] = {}
    for permission_id, role_name in rows:
        out.setdefault(permission_id, []).append(role_name)
    return out


def _out(p: models.Permission, roles: dict[int, list[str]]) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "description": p.description,
        "builtin": p.code in BUILTIN,
        "roles": roles.get(p.id, []),
    }


@router.get("", response_model=list[schemas.PermissionAdminOut])
def list_permissions(
    db: Session = Depends(get_db), _=Depends(require_permission("permissions:read"))
):
    roles = _role_map(db)
    perms = db.scalars(select(models.Permission).order_by(models.Permission.code)).all()
    return [_out(p, roles) for p in perms]


@router.post("", response_model=schemas.PermissionAdminOut, status_code=201)
def create_permission(
    data: schemas.PermissionIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("permissions:create")),
):
    if db.scalar(select(models.Permission).where(models.Permission.code == data.code)):
        raise HTTPException(400, "Permission already exists")
    perm = models.Permission(code=data.code, description=data.description)
    db.add(perm)
    admin = db.scalar(select(models.Role).where(models.Role.name == "admin"))
    if admin:
        admin.permissions.append(perm)      # admin always holds every permission
    db.flush()
    audit.record(
        db, request, "permission.create", actor=actor, target_type="permission", target_id=perm.id,
        detail={"code": perm.code, "description": perm.description},
    )
    db.commit()
    db.refresh(perm)
    return _out(perm, _role_map(db))


@router.put("/{permission_id}", response_model=schemas.PermissionAdminOut)
def update_permission(
    permission_id: int,
    data: schemas.PermissionIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("permissions:update")),
):
    perm = db.get(models.Permission, permission_id)
    if not perm:
        raise HTTPException(404, "Permission not found")
    if perm.code in BUILTIN and data.code != perm.code:
        raise HTTPException(400, "Built-in permission codes cannot be renamed")
    clash = db.scalar(
        select(models.Permission).where(
            models.Permission.code == data.code, models.Permission.id != perm.id
        )
    )
    if clash:
        raise HTTPException(400, "Another permission already uses this code")
    before = {"code": perm.code, "description": perm.description}
    perm.code, perm.description = data.code, data.description
    audit.record(
        db, request, "permission.update", actor=actor, target_type="permission", target_id=perm.id,
        detail={"before": before, "after": {"code": perm.code, "description": perm.description}},
    )
    db.commit()
    db.refresh(perm)
    return _out(perm, _role_map(db))


@router.delete("/{permission_id}", status_code=204)
def delete_permission(
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission("permissions:delete")),
):
    perm = db.get(models.Permission, permission_id)
    if not perm:
        raise HTTPException(404, "Permission not found")
    if perm.code in BUILTIN:
        raise HTTPException(400, "Built-in permissions cannot be deleted")
    audit.record(
        db, request, "permission.delete", actor=actor, target_type="permission", target_id=perm.id,
        detail={"code": perm.code, "roles": _role_map(db).get(perm.id, [])},
    )
    db.delete(perm)     # the database cascades the role_permissions rows
    db.commit()