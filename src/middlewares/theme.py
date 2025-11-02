from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class ThemeMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically inject theme into template contexts."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        theme = request.cookies.get("theme", "light")

        if theme not in ("light", "dark"):
            theme = "light"

        request.state.theme = theme

        rsp = await call_next(request)
        return rsp
