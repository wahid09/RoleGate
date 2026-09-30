from fastapi import Request
from sqlalchemy.orm import Session

from . import models
from .ratelimit import client_ip


def record(
    db: Session,
    request: Request,
    action: str,
    *,
    actor: models.User | None = None,
    actor_email: str | None = None,
    target_type: str | None = None,
    target_id: int | str | None = None,
    detail: dict | None = None,
) -> None:
    """Stage an audit row. The caller commits."""
    db.add(
        models.AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else actor_email,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
            ip=client_ip(request),
        )
    )