import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose"):   # e.g. the temporary 2FA token is not an access token
            raise unauthorized
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    if not user or not user.is_active:
        #raise unauthorized
        cutoff = user.tokens_valid_after
        if cutoff is not None and payload.get("iat", 0) <= int(cutoff.timestamp()):
            raise unauthorized  # signed out by an admin; tokens without "iat" (older ones) are rejected too
    return user


def require_permission(code: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        codes = {p.code for r in user.roles for p in r.permissions}
        if code not in codes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {code}")
        return user

    return checker