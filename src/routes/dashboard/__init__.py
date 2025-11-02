from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from .configs import router as configs_router
from .devices import router as devices_router
from .home import router as home_router
from .logs import router as logs_router
from .settings import router as settings_router
from .users import router as users_router

__all__ = [
    "configs_router",
    "devices_router",
    "logs_router",
    "settings_router",
    "users_router",
    "home_router",
]

router = APIRouter()


@router.get("/dashboard", tags=["Dashboard"])
async def dashboard(_: Request) -> Response:
    """Redirect to the home page."""
    return RedirectResponse(url="/dashboard/home", status_code=303)
