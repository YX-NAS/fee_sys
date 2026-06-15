import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import User, UserRole, UserStatus
from app.routers import accounts, ai, ai_gateway, alerts, analytics, auth, budgets, notifications, transactions, users
from app.security import hash_password
from app.services.scheduler import start_scheduler, stop_scheduler

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def _ensure_admin():
    """首次启动时自动创建管理员账号（若不存在）。"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == settings.FIRST_ADMIN_USERNAME))
        if result.scalar_one_or_none() is None:
            admin = User(
                username=settings.FIRST_ADMIN_USERNAME,
                email=settings.FIRST_ADMIN_EMAIL,
                password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=UserRole.admin,
                status=UserStatus.active,
            )
            db.add(admin)
            await db.commit()
            logger.info("初始管理员账号已创建: %s", settings.FIRST_ADMIN_USERNAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_admin()
    start_scheduler()
    logger.info("费用管理系统 API 已启动")
    yield
    stop_scheduler()
    logger.info("费用管理系统 API 已停止")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(budgets.router)
app.include_router(ai.router)
app.include_router(ai_gateway.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/ai-gateway/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {
                "message": str(exc.detail), "type": "invalid_request_error",
                "param": None, "code": f"http_{exc.status_code}",
            }},
            headers=exc.headers,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Validation bodies can contain passwords or provider API keys.
    errors = [
        {key: value for key, value in error.items() if key not in {"input", "ctx"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
