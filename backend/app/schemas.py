from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    description: str


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    permissions: list[PermissionOut] = []


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    description: str = ""
    permission_ids: list[int] = []


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    email_verified: bool
    created_at: datetime
    roles: list[RoleOut] = []

    @computed_field
    @property
    def permissions(self) -> list[str]:
        return sorted({p.code for r in self.roles for p in r.permissions})


class UserRolesIn(BaseModel):
    role_ids: list[int]


class UserActiveIn(BaseModel):
    is_active: bool

class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role_ids: list[int] = []
    is_active: bool = True

class VerifyIn(BaseModel):
    token: str

class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)