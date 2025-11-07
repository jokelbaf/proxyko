import secrets

from argon2 import PasswordHasher
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from db.models import Session, User
from modules.cookies import set_secure_cookie
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/register", tags=["Auth"])
async def register(request: Request) -> Response:
    """Display the registration page."""
    users = await User.all()
    if users:
        # Register page is only accessible once to create the first user
        # Afterwards, any new user must be created from the dashboard
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request=request, name="register.html")


@router.post("/register", tags=["Auth"])
async def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Handle user registration."""
    errors: list[str] = []

    if not username or len(username) < 3 or len(username) > 36:
        errors.append("Username must be between 3 and 36 characters long.")

    if not password or len(password) < 8 or len(password) > 48:
        errors.append("Password must be between 8 and 48 characters long.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"errors": errors, "username": username, "password": password},
        )

    users = await User.all()
    if users:
        return RedirectResponse(url="/login", status_code=303)

    ph = PasswordHasher()
    hashed_password = ph.hash(password)

    user = await User.create(username=username, password=hashed_password)

    rsp = RedirectResponse(url="/dashboard", status_code=303)

    session_token = secrets.token_hex(32)
    await Session.create(user=user, token=session_token)

    set_secure_cookie(rsp, key="session-token", value=session_token, max_age=60 * 60 * 24 * 7)

    return rsp
