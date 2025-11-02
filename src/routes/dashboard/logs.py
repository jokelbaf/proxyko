from fastapi import APIRouter, Request, Response

from db.models import AccessRecord, User
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/dashboard/logs", tags=["Dashboard"])
async def logs(
    request: Request, page: int = 1, limit: int = 20, message: str | None = None
) -> Response:
    """Display all access logs."""
    user: User = request.state.user

    offset = (page - 1) * limit

    logs = (
        await AccessRecord.all()
        .prefetch_related("device")
        .order_by("-created_at")
        .offset(offset)
        .limit(limit)
    )

    total = await AccessRecord.all().count()
    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        request=request,
        name="dashboard.logs.html",
        context={
            "user": user,
            "logs": logs,
            "page": page,
            "total_pages": total_pages,
            "message": message,
        },
    )


@router.delete("/dashboard/logs", tags=["Dashboard"])
async def clear_logs(request: Request) -> Response:
    """Clear all access logs."""
    import urllib.parse

    from fastapi.responses import RedirectResponse

    await AccessRecord.all().delete()

    query_string = urllib.parse.urlencode({"message": "All logs have been cleared."})
    return RedirectResponse(
        url="/dashboard/logs?" + query_string,
        status_code=303,
    )
