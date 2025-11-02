import dataclasses
import secrets
import time
import typing

from argon2 import PasswordHasher
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from db.models import Session, User
from modules.auth import verify_totp
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@dataclasses.dataclass
class PendingLogin:
    """Pending login session data."""

    username: str
    expires_at: float


PendingLogins = dict[str, PendingLogin]
"""In-memory store for pending login sessions. Token is the key."""


@router.get("/login", tags=["Auth"])
async def login(request: Request) -> Response:
    """Display the login page."""
    users = await User.all()
    if not users:
        # If no users exist, an initial user must be created first
        return RedirectResponse(url="/register", status_code=303)

    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/login", tags=["Auth"])
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Handle user login."""
    errors: list[str] = []

    if not username or len(username) < 3 or len(username) > 36:
        errors.append("Username must be between 3 and 36 characters long.")

    if not password or len(password) < 8 or len(password) > 48:
        errors.append("Password must be between 8 and 48 characters long.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"errors": errors, "username": username},
        )

    user = await User.get_or_none(username=username)

    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"errors": ["Invalid username or password."], "username": username},
        )

    ph = PasswordHasher()
    try:
        ph.verify(user.password, password)
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"errors": ["Invalid username or password."], "username": username},
        )

    if typing.cast(str | None, user.totp_secret) is not None:
        # The user has 2FA enabled
        pending_login = PendingLogin(
            username=username,
            expires_at=time.time() + 300,
        )
        temp_token = secrets.token_hex(16)

        request.app.state.pending_logins[temp_token] = pending_login

        rsp = RedirectResponse(url="/login/2fa", status_code=303)
        rsp.set_cookie(key="pending-login-token", value=temp_token, httponly=True)

        return rsp

    rsp = RedirectResponse(url="/dashboard", status_code=303)

    session_token = secrets.token_hex(32)
    await Session.create(user=user, token=session_token)

    rsp.set_cookie(key="session-token", value=session_token, httponly=True)

    return rsp


@router.get("/login/2fa", tags=["Auth"])
async def login_2fa(request: Request) -> Response:
    """Display the 2FA verification page."""
    pending_login_token = request.cookies.get("pending-login-token")
    if pending_login_token is None:
        return RedirectResponse(url="/login", status_code=303)

    pending_login = request.app.state.pending_logins.get(pending_login_token)
    if pending_login is None or pending_login.expires_at < time.time():
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request=request, name="login.2fa.html")


@router.post("/login/2fa", tags=["Auth"])
async def login_2fa_post(
    request: Request,
    code: str = Form(...),
) -> Response:
    """Handle 2FA verification."""
    pending_login_token = request.cookies.get("pending-login-token")
    if pending_login_token is None:
        return RedirectResponse(url="/login", status_code=303)

    pending_login = request.app.state.pending_logins.get(pending_login_token)
    if pending_login is None or pending_login.expires_at < time.time():
        return RedirectResponse(url="/login", status_code=303)

    user = await User.get_or_none(username=pending_login.username)
    if user is None or typing.cast(str | None, user.totp_secret) is None:
        return RedirectResponse(url="/login", status_code=303)

    if not verify_totp(user.totp_secret, code):
        return templates.TemplateResponse(
            request=request,
            name="login.2fa.html",
            context={"errors": ["Invalid 2FA code."]},
        )

    rsp = RedirectResponse(url="/dashboard", status_code=303)

    session_token = secrets.token_hex(32)
    await Session.create(user=user, token=session_token)

    rsp.set_cookie(key="session-token", value=session_token, httponly=True)
    rsp.delete_cookie(key="pending-login-token")

    del request.app.state.pending_logins[pending_login_token]

    return rsp
