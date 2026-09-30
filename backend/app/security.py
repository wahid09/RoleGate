from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import hashlib
import secrets

from .config import settings


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