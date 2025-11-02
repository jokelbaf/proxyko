from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from db.models import Session
from modules.cookies import delete_secure_cookie

router = APIRouter()


@router.post("/logout", tags=["Auth"])
async def logout(request: Request) -> Response:
    """Log out the current user by deleting their session."""
    session_token = request.cookies.get("session-token")

    if session_token:
        session = await Session.get_or_none(token=session_token)
        if session:
            await session.delete()

    response = RedirectResponse(url="/login", status_code=303)
    delete_secure_cookie(response, key="session-token")

    return response
