from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Permission, Role, User
from .security import hash_password

PERMISSIONS = [
    ("dashboard:view", "View dashboard"),
    ("users:read", "List users"),
    ("users:update", "Change user roles / status"),
    ("roles:read", "List roles and permissions"),
    ("roles:create", "Create roles"),
    ("roles:update", "Edit roles"),
    ("roles:delete", "Delete roles"),
    ("users:create", "Create users"),
]

DEFAULT_ROLES = {
    "admin": [c for c, _ in PERMISSIONS],
    "manager": ["dashboard:view", "users:read", "roles:read"],
    "user": ["dashboard:view"],
}


def seed(db: Session) -> None:
    perms: dict[str, Permission] = {}
    for code, desc in PERMISSIONS:
        p = db.scalar(select(Permission).where(Permission.code == code))
        if not p:
            p = Permission(code=code, description=desc)
            db.add(p)
        perms[code] = p
    db.flush()

    roles: dict[str, Role] = {}
    for name, codes in DEFAULT_ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if not role:
            role = Role(name=name, description=f"{name.title()} role")
            role.permissions = [perms[c] for c in codes]
            db.add(role)
        elif name == "admin":  # admin always gets every permission
            role.permissions = list(perms.values())
        roles[name] = role
    db.flush()

    email = settings.FIRST_ADMIN_EMAIL.lower()
    if not db.scalar(select(User).where(User.email == email)):
        db.add(
            User(
                full_name="Administrator",
                email=email,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                email_verified=True,
                roles=[roles["admin"]],
            )
        )
    db.commit()