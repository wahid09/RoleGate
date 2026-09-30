from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .database import SessionLocal
from .routers import audit_logs, auth, roles, users
from .seed import seed

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     Base.metadata.create_all(bind=engine)
#     with SessionLocal() as db:
#         seed(db)
#     yield

@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        seed(db)          # tables come from `alembic upgrade head`
    yield


app = FastAPI(
    title="Auth & RBAC API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(users.router)
api.include_router(roles.router)
api.include_router(audit_logs.router)
app.include_router(api)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)