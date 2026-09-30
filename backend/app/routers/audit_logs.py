from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=schemas.AuditPage)
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None, description="Action prefix, e.g. 'user.' or 'auth.login'"),
    actor: str | None = Query(None, description="Substring of the actor's email"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("audit:read")),
):
    q = select(models.AuditLog)
    if action:
        q = q.where(models.AuditLog.action.startswith(action, autoescape=True))
    if actor:
        q = q.where(models.AuditLog.actor_email.icontains(actor, autoescape=True))

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(
        q.order_by(models.AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}