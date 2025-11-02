import urllib.parse

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from db.models import GlobalConfig, User
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/dashboard/settings", tags=["Dashboard"])
async def settings(
    request: Request,
    message: str | None = None,
) -> Response:
    """Display global settings."""
    user: User = request.state.user

    config = await GlobalConfig.get(server_id=1)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.settings.html",
        context={
            "user": user,
            "config": config,
            "message": message,
        },
    )


@router.post("/dashboard/settings", tags=["Dashboard"])
async def update_settings(
    request: Request,
    require_auth: bool = Form(default=False),
) -> Response:
    """Update global settings."""
    config: GlobalConfig = request.app.state.global_config

    config.require_auth = require_auth
    await config.save(update_fields=["require_auth"])

    query_string = urllib.parse.urlencode({"message": "Settings have been saved successfully."})
    return RedirectResponse(
        url="/dashboard/settings?" + query_string,
        status_code=303,
    )
