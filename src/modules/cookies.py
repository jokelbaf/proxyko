import os

from fastapi import Response


def is_production() -> bool:
    """Check if the app is running in production mode."""
    return os.getenv("PRODUCTION", "no").lower() == "yes"

def set_secure_cookie(
    response: Response,
    key: str,
    value: str,
    max_age: int | None = None,
    httponly: bool = True,
) -> None:
    """
    Set a cookie with security attributes appropriate for the environment."""
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=httponly,
        secure=is_production(),
        samesite="lax",
    )

def delete_secure_cookie(response: Response, key: str) -> None:
    """Delete a cookie with the same security attributes used when setting it."""
    response.delete_cookie(
        key=key,
        httponly=True,
        secure=is_production(),
        samesite="lax",
    )
