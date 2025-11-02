import typing
import urllib.parse

import pyotp
from argon2 import PasswordHasher
from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from db.models import PydanticReadUser, User
from modules.auth import verify_totp
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


def users_to_dicts(user_id: int, users: list[User]) -> list[dict[str, typing.Any]]:
    """Convert User models to dictionaries with formatted data."""
    dict_users: list[dict[str, typing.Any]] = []

    user = users.pop(next(i for i, x in enumerate(users) if x.id == user_id))
    users.insert(0, user)

    for user in users:
        read_user = PydanticReadUser.model_validate(user)
        dict_users.append(
            {
                "totp_enabled": typing.cast(str | None, user.totp_secret) is not None,
                **read_user.model_dump(include={"id", "username", "created_at"}),
            }
        )

    return dict_users


@router.get("/dashboard/users", tags=["Dashboard"])
async def users(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    totp_secret: str | None = None,
) -> Response:
    user: User = request.state.user
    users = await User.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.users.html",
        context={
            "user": user,
            "users": users_to_dicts(user.id, users),
            "message": message,
            "errors": [error] if error else [],
            "modal_user": None,
            "modal_errors": [],
            "display_modal": False,
            "totp_secret": totp_secret,
        },
    )


@router.get("/dashboard/users/new", tags=["Dashboard"])
async def new_user(request: Request) -> Response:
    """Display the new user modal."""
    user: User = request.state.user
    users = await User.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.users.html",
        context={
            "user": user,
            "users": users_to_dicts(user.id, users),
            "message": None,
            "errors": [],
            "modal_user": None,
            "modal_errors": [],
            "display_modal": True,
            "totp_secret": None,
        },
    )


@router.post("/dashboard/users/new", tags=["Dashboard"])
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Create a new user."""
    user: User = request.state.user
    users = await User.all()

    errors: list[str] = []

    if not username or len(username) < 3 or len(username) > 36:
        errors.append("Username must be between 3 and 36 characters long.")

    if not password or len(password) < 8 or len(password) > 48:
        errors.append("Password must be between 8 and 48 characters long.")

    if any(u.username == username for u in users):
        errors.append("Username is already taken.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.users.html",
            context={
                "user": user,
                "users": users_to_dicts(user.id, users),
                "message": None,
                "errors": [],
                "modal_user": None,
                "modal_errors": errors,
                "display_modal": True,
                "totp_secret": None,
            },
        )

    ph = PasswordHasher()
    hashed_password = ph.hash(password)

    await User.create(username=username, password=hashed_password)
    users = await User.all()

    query_string = urllib.parse.urlencode({"message": "User has been created successfully."})
    return RedirectResponse(
        url="/dashboard/users?" + query_string,
        status_code=303,
    )


@router.get("/dashboard/users/{user_id}", tags=["Dashboard"])
async def user(request: Request, user_id: int) -> Response:
    """Display a specific user in modal for editing."""
    user: User = request.state.user
    users = await User.all()
    modal_user = await User.get_or_none(id=user_id).only("id", "username", "created_at")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.users.html",
        context={
            "user": user,
            "users": users_to_dicts(user.id, users),
            "message": None,
            "errors": [],
            "modal_user": modal_user,
            "modal_errors": [],
            "display_modal": True,
            "totp_secret": None,
        },
    )


@router.post("/dashboard/users/{user_id}", tags=["Dashboard"])
async def update_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Edit an existing user."""
    user: User = request.state.user
    users = await User.all()
    modal_user = await User.get_or_none(id=user_id).only("id", "username", "created_at")

    if modal_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    errors: list[str] = []

    if not username or len(username) < 3 or len(username) > 36:
        errors.append("Username must be between 3 and 36 characters long.")

    if password and (len(password) < 8 or len(password) > 48):
        errors.append("Password must be between 8 and 48 characters long.")

    if any(u.username == username and u.id != user_id for u in users):
        errors.append("Username is already taken.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.users.html",
            context={
                "user": user,
                "users": users_to_dicts(user.id, users),
                "message": None,
                "errors": [],
                "modal_user": modal_user,
                "modal_errors": errors,
                "display_modal": True,
                "totp_secret": None,
            },
        )

    modal_user.username = username
    update_fields = ["username"]

    if password:
        ph = PasswordHasher()
        hashed_password = ph.hash(password)
        modal_user.password = hashed_password
        update_fields.append("password")

    await modal_user.save(update_fields=update_fields)
    users = await User.all()

    query_string = urllib.parse.urlencode({"message": "User has been updated successfully."})
    return RedirectResponse(
        url="/dashboard/users?" + query_string,
        status_code=303,
    )


@router.delete("/dashboard/users/{user_id}", tags=["Dashboard"])
async def delete_user(request: Request, user_id: int) -> Response:
    """Delete an existing user."""
    user: User = request.state.user

    target_user = await User.get_or_none(id=user_id)

    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if target_user.id == user.id:
        query_string = urllib.parse.urlencode({"error": "You cannot delete your own account."})
        return RedirectResponse(url="/dashboard/users?" + query_string, status_code=303)

    await target_user.delete()

    query_string = urllib.parse.urlencode({"message": "User has been deleted successfully."})
    return RedirectResponse(url="/dashboard/users?" + query_string, status_code=303)


@router.post("/dashboard/users/{user_id}/2fa")
async def toggle_2fa(
    request: Request, user_id: int, code: int | None = Form(default=None)
) -> Response:
    """Enable or disable 2FA for a user."""
    target_user = await User.get_or_none(id=user_id)

    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    has_2fa = typing.cast(str | None, target_user.totp_secret) is not None

    if has_2fa:
        if code is None:
            query_string = urllib.parse.urlencode({"error": "2FA code is required to disable 2FA."})
            return RedirectResponse(
                url="/dashboard/users?" + query_string,
                status_code=303,
            )
        if not verify_totp(target_user.totp_secret, code):
            query_string = urllib.parse.urlencode({"error": "Invalid 2FA code provided."})
            return RedirectResponse(
                url="/dashboard/users?" + query_string,
                status_code=303,
            )

    secret = pyotp.random_base32() if not has_2fa else None
    target_user.totp_secret = secret  # type: ignore

    await target_user.save(update_fields=["totp_secret"])

    if target_user.totp_secret:
        query = {
            "totp_secret": target_user.totp_secret,
        }
    else:
        query = {"message": "2FA has been successfully disabled."}

    query_string = urllib.parse.urlencode(query)

    return RedirectResponse(
        url="/dashboard/users?" + query_string,
        status_code=303,
    )
