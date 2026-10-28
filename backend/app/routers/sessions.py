from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit, models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..security import hash_token

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])


def _current_session_id(db: Session, user: models.User, refresh_token: str | None) -> str | None:
    if not refresh_token:
        return None
    row = db.scalar(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_token(refresh_token))
    )
    return row.session_id if row and row.user_id == user.id and not row.revoked else None


@router.get("", response_model=list[schemas.SessionOut])
def list_sessions(
    refresh_token: str | None = Cookie(default=None),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One entry per signed-in device: the newest live refresh token of each session."""
    rows = db.scalars(
        select(models.RefreshToken)
        .where(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked.is_(False),
            models.RefreshToken.expires_at > datetime.now(UTC),
        )
        .order_by(models.RefreshToken.created_at.desc())
    ).all()
    current = _current_session_id(db, user, refresh_token)
    return [
        schemas.SessionOut(
            id=r.session_id,
            user_agent=r.user_agent,
            ip=r.ip,
            started_at=r.session_started_at,
            last_active_at=r.created_at,
            current=r.session_id == current,
        )
        for r in rows
    ]


@router.post("/revoke-others")
def revoke_others(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = _current_session_id(db, user, refresh_token)
    if current is None:
        raise HTTPException(400, "Could not identify this device. Please sign in again.")
    result = db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked.is_(False),
            models.RefreshToken.session_id != current,
        )
        .values(revoked=True)
    )
    audit.record(
        db, request, "auth.session.revoke_others", actor=user, target_type="user", target_id=user.id,
        detail={"sessions": result.rowcount},
    )
    db.commit()
    return {"revoked": result.rowcount}


@router.post("/{session_id}/revoke")
def revoke_session(
    session_id: str,
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if session_id == _current_session_id(db, user, refresh_token):
        raise HTTPException(400, "This is your current device. Use Sign out instead.")
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
        db, request, "auth.session.revoke", actor=user, target_type="user", target_id=user.id,
        detail={"session": session_id[:8]},
    )
    db.commit()
    return {"message": "Session signed out"}
