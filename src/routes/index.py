from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/")
async def index() -> Response:
    """Redirect to the dashboard."""
    return RedirectResponse("/dashboard/configs", status_code=303)
