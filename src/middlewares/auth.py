from fnmatch import fnmatchcase

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from db.models import Session, User
from modules.utility import get_env_var

EXCLUDED_ROUTES: list[str] = ["/pac", "/logout", "/health", "/static/*"]

AUTH_ROUTES: list[str] = [
    "/login",
    "/register",
    "/login/2fa",
]


def is_protected_route(path: str) -> bool:
    """Check if the given path is a protected route."""
    is_in_excluded = not any(fnmatchcase(path, r) for r in EXCLUDED_ROUTES)
    is_in_auth = not any(fnmatchcase(path, r) for r in AUTH_ROUTES)
    return is_in_excluded and is_in_auth


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/api/internal"):
            api_key = get_env_var("INTERNAL_API_KEY")
            if not api_key or request.headers.get("X-Internal-API-Key") != api_key:
                return JSONResponse(
                    status_code=401,
                    content={
                        "status": 401,
                        "message": "Unauthorized",
                        "data": None,
                    },
                )
        else:
            session_token = request.cookies.get("session-token")
            if session_token:
                session = await Session.get_or_none(token=session_token).prefetch_related("user")
                if session is not None:
                    if not session.is_expired():
                        fields = ["id", "username", "created_at", "updated_at"]
                        request.state.user = await User.get(id=session.user.id).only(*fields)
                    else:
                        await session.delete()

            authenticated = hasattr(request.state, "user")

            if is_protected_route(request.url.path) and not authenticated:
                return RedirectResponse(url="/login", status_code=303)

            is_auth_page = request.url.path in AUTH_ROUTES

            if authenticated and is_auth_page:
                return RedirectResponse(url="/dashboard", status_code=303)

        response = await call_next(request)
        return response
