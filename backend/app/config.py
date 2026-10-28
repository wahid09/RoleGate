from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    COOKIE_SECURE: bool = False

    FRONTEND_URL: str = "http://localhost"
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@example.com"

    FIRST_ADMIN_EMAIL: str
    FIRST_ADMIN_PASSWORD: str

    REDIS_URL: str = "redis://redis:6379/0"
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCK_SECONDS: int = 900
    VERIFY_TOKEN_EXPIRE_HOURS: int = 24

    RATE_LIMIT_ENABLED: bool = True


    WEBAUTHN_RP_ID: str = "localhost"          # the site's domain, no scheme/port. Changing it invalidates all passkeys.
    WEBAUTHN_RP_NAME: str = "RoleGate"
    WEBAUTHN_ORIGINS: str = "http://localhost,http://localhost:5173"   # comma-separated, exact browser origins

    @property
    def webauthn_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.WEBAUTHN_ORIGINS.split(",") if o.strip()]


settings = Settings()