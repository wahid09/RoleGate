from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit, models, schemas, webauthn_utils
from ..database import get_db
from ..deps import get_current_user
from ..ratelimit import login_failed, login_locked, login_ok, rate_limit
from ..security import decode_mfa_token, verify_password
from .auth import _access, _issue_refresh

router = APIRouter(prefix="/auth", tags=["passkeys"])

CHALLENGE_TTL = timedelta(minutes=5)
LOCKED = "Too many failed attempts. Try again in a few minutes."
EXPIRED = "Sign-in session expired. Please start again."


def _store_challenge(db: Session, user: models.User, purpose: str, challenge: bytes) -> None:
    # one open challenge per user and purpose; also sweep expired ones
    db.execute(
        delete(models.WebAuthnChallenge).where(
            (models.WebAuthnChallenge.user_id == user.id) & (models.WebAuthnChallenge.purpose == purpose)
            | (models.WebAuthnChallenge.expires_at < datetime.now(UTC))
        )
    )
    db.add(
        models.WebAuthnChallenge(
            user_id=user.id, purpose=purpose, challenge=challenge, expires_at=datetime.now(UTC) + CHALLENGE_TTL
        )
    )
    db.commit()


def _take_challenge(db: Session, user: models.User, purpose: str) -> bytes | None:
    """Single use: the row is deleted whether or not the attempt later succeeds."""
    row = db.scalar(
        select(models.WebAuthnChallenge).where(
            models.WebAuthnChallenge.user_id == user.id, models.WebAuthnChallenge.purpose == purpose
        )
    )
    if row is None:
        return None
    challenge, expires = row.challenge, row.expires_at
    db.delete(row)
    db.commit()
    return challenge if expires > datetime.now(UTC) else None


def _credential_id(credential: dict) -> str:
    cid = credential.get("id")
    if not isinstance(cid, str):
        raise HTTPException(400, "Invalid passkey response")
    return cid


@router.get("/passkeys", response_model=list[schemas.PasskeyOut])
def list_passkeys(user: models.User = Depends(get_current_user)):
    return sorted(user.passkeys, key=lambda p: p.created_at)


@router.post(
    "/passkeys/register/options",
    dependencies=[Depends(rate_limit("passkey-register", 10, 900))],
)
def register_options(
    data: schemas.PasswordIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(400, "Password is incorrect")
    text, challenge = webauthn_utils.registration_options(user.id, user.email, [p.credential_id for p in user.passkeys])
    _store_challenge(db, user, "register", challenge)
    return Response(content=text, media_type="application/json")


@router.post(
    "/passkeys/register",
    response_model=schemas.PasskeyOut,
    status_code=201,
    dependencies=[Depends(rate_limit("passkey-register", 10, 900))],
)
def register(
    data: schemas.PasskeyRegisterIn,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    challenge = _take_challenge(db, user, "register")
    if challenge is None:
        raise HTTPException(400, "Registration expired. Please try again.")
    try:
        verified = webauthn_utils.verify_registration(data.credential, challenge)
    except webauthn_utils.InvalidRegistrationResponse as exc:
        raise HTTPException(400, "Passkey could not be verified") from exc
    except Exception as exc:  # malformed client payloads surface as assorted errors
        raise HTTPException(400, "Passkey could not be verified") from exc

    cid = webauthn_utils.b64(verified.credential_id)
    if db.scalar(select(models.WebAuthnCredential).where(models.WebAuthnCredential.credential_id == cid)):
        raise HTTPException(409, "This passkey is already registered")

    transports = (data.credential.get("response") or {}).get("transports") or []
    passkey = models.WebAuthnCredential(
        user_id=user.id,
        name=data.name.strip() or "Passkey",
        credential_id=cid,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=[t for t in transports if isinstance(t, str)],
    )
    db.add(passkey)
    audit.record(
        db, request, "auth.passkey.add", actor=user, target_type="user", target_id=user.id, detail={"name": passkey.name}
    )
    db.commit()
    db.refresh(passkey)
    return passkey


@router.post(
    "/passkeys/{passkey_id}/remove",
    dependencies=[Depends(rate_limit("passkey-remove", 5, 900))],
)
def remove_passkey(
    passkey_id: int,
    data: schemas.PasswordIn,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    passkey = next((p for p in user.passkeys if p.id == passkey_id), None)
    if passkey is None:
        raise HTTPException(404, "Passkey not found")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(400, "Password is incorrect")
    audit.record(
        db, request, "auth.passkey.remove", actor=user, target_type="user", target_id=user.id,
        detail={"name": passkey.name},
    )
    user.passkeys.remove(passkey)
    db.commit()
    return {"message": "Passkey removed"}


# --- second step of sign-in -------------------------------------------------

def _mfa_user(db: Session, mfa_token: str) -> models.User:
    user_id = decode_mfa_token(mfa_token)
    user = db.get(models.User, user_id) if user_id else None
    if not user or not user.is_active or not user.passkeys:
        raise HTTPException(400, EXPIRED)
    if login_locked(user.email):
        raise HTTPException(429, LOCKED)
    return user


@router.post(
    "/login/webauthn/options",
    dependencies=[Depends(rate_limit("login-2fa", 10, 300))],
)
def login_options(data: schemas.MfaTokenIn, db: Session = Depends(get_db)):
    user = _mfa_user(db, data.mfa_token)
    text, challenge = webauthn_utils.authentication_options([p.credential_id for p in user.passkeys])
    _store_challenge(db, user, "login", challenge)
    return Response(content=text, media_type="application/json")


@router.post(
    "/login/webauthn",
    response_model=schemas.Token,
    dependencies=[Depends(rate_limit("login-2fa", 10, 300))],
)
def login_webauthn(
    data: schemas.PasskeyLoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = _mfa_user(db, data.mfa_token)
    challenge = _take_challenge(db, user, "login")
    passkey = next((p for p in user.passkeys if p.credential_id == data.credential.get("id")), None)

    def fail(reason: str):
        login_failed(user.email)
        audit.record(db, request, "auth.2fa_failed", actor=user, detail={"mfa": "passkey", "reason": reason})
        db.commit()
        raise HTTPException(400, "Passkey could not be verified")

    if challenge is None:
        raise HTTPException(400, EXPIRED)
    if passkey is None:
        fail("unknown_credential")
    try:
        verified = webauthn_utils.verify_authentication(
            data.credential, challenge, passkey.public_key, passkey.sign_count
        )
    except webauthn_utils.VERIFY_ERRORS:
        fail("verification_failed")

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(UTC)
    login_ok(user.email)
    audit.record(db, request, "auth.login", actor=user, detail={"mfa": "passkey"})
    _issue_refresh(db, user, response, request)  # commits everything above
    return _access(user)


