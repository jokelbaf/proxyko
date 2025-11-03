import asyncio
import contextlib
import logging
import os
import time

import dotenv
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import db
from db.models import AccessRecord
from middlewares import AuthMiddleware, ThemeMiddleware
from modules.templates import Jinja2Templates
from modules.utility import get_real_ip
from routes import (
    PendingLogins,
    configs_router,
    dashboard_router,
    devices_router,
    health_router,
    home_router,
    index_router,
    internal_proxy_router,
    login_router,
    logout_router,
    logs_router,
    pac_router,
    proxy_router,
    register_router,
    settings_router,
    users_router,
)

dotenv.load_dotenv()

templates = Jinja2Templates(directory="templates")

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)

loggers = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "asyncio",
    "starlette",
)

for logger_name in loggers:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = []
    logging_logger.propagate = True


async def clean_pending_logins_task(app: FastAPI):
    """Background task to clean expired pending logins."""
    while True:
        now = time.time()
        pending_logins: PendingLogins = app.state.pending_logins
        expired_tokens = [
            token for token, data in pending_logins.items() if now - data.expires_at > 300
        ]
        for token in expired_tokens:
            del pending_logins[token]
        await asyncio.sleep(60)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization."""
    app.state.global_config = await db.init()

    access_records: list[AccessRecord] = []
    app.state.access_records = access_records

    pending_logins: PendingLogins = {}
    app.state.pending_logins = pending_logins

    asyncio.create_task(clean_pending_logins_task(app))

    app.state.last_proxy_heartbeat_time = None

    yield
    await db.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RateLimitExceeded)
def rate_limit_exc_handler(request: Request, _: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 429,
            "title": "Too Many Requests",
            "details": (
                "Hold on there! You're making requests too quickly. "
                "Please slow down and try again in a moment."
            ),
        },
        status_code=429,
    )


@app.exception_handler(404)
def not_found_exc_handler(request: Request, exc: HTTPException) -> Response:
    """Handle not found errors."""
    details = (
        exc.detail
        if exc.detail and exc.detail != "Not Found"
        else "The requested resource was not found."
    )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 404,
            "title": "Not Found",
            "details": details,
        },
        status_code=404,
    )


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handle generic HTTP exceptions."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": exc.status_code,
            "title": "Error",
            "details": exc.detail if exc.detail else "An unexpected error occurred.",
        },
        status_code=exc.status_code,
    )


limiter = Limiter(key_func=get_real_ip, default_limits=["15/minute"])
app.state.limiter = limiter

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(GZipMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ThemeMiddleware)
app.add_middleware(AuthMiddleware)

app.include_router(dashboard_router)
app.include_router(index_router)
app.include_router(register_router)
app.include_router(login_router)
app.include_router(logout_router)
app.include_router(pac_router)
app.include_router(devices_router)
app.include_router(users_router)
app.include_router(configs_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(home_router)
app.include_router(health_router)
app.include_router(internal_proxy_router)
app.include_router(proxy_router)


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8032")),
        reload=os.getenv("PRODUCTION") != "yes",
        log_config=None,
        log_level=None,
        proxy_headers=True,
    )
