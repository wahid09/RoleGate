import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings
import base64
import hmac
import time

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken


def _b(password: str) -> bytes:
    return password.encode()[:72]  # bcrypt limit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_b(password), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(_b(password), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def generate_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


TOTP_STEP = 30
TOTP_ISSUER = "RoleGate"


def _unix_time() -> float:      # its own function so tests can control the clock
    return time.time()


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(f"totp:{settings.SECRET_KEY}".encode()).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:         # SECRET_KEY was rotated
        return None


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


def qr_data_uri(uri: str) -> str:
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2)


def verify_totp(secret: str, code: str, last_step: int | None) -> int | None:
    """Return the matching 30-second step, or None. Steps already used are rejected (replay)."""
    totp = pyotp.TOTP(secret)
    current = int(_unix_time() // TOTP_STEP)
    for step in (current - 1, current, current + 1):     # tolerate small clock drift
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * TOTP_STEP), code):
            return step
    return None


def new_recovery_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(6)
        codes.append(f"{raw[:6]}-{raw[6:]}")
    return codes


def create_mfa_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {"sub": subject, "exp": expire, "purpose": "mfa"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_mfa_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "mfa":
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None