import os
import typing

from fastapi import Request
from fastapi.datastructures import Address


@typing.overload
def get_env_var(name: str, required: typing.Literal[True]) -> str: ...


@typing.overload
def get_env_var(name: str, required: typing.Literal[False] = ...) -> str | None: ...


def get_env_var(name: str, required: bool = False) -> str | None:
    """Get an environment variable, raising an error if not found and required is True."""
    if (value := os.getenv(name)) is not None or not required:
        return value
    raise RuntimeError(f"Required environment variable '{name}' is not set.")


def get_real_ip(request: Request) -> str:
    """Extract the real client IP address from the request headers."""
    possible_headers = [
        "X-Forwarded-For",
        "X-Real-IP",
        "CF-Connecting-IP",  # Cloudflare
        "True-Client-IP",  # Akamai
    ]
    for header in possible_headers:
        ip = request.headers.get(header)
        if ip:
            # In case of multiple IPs, take the first one
            return ip.split(",")[0].strip()

    return typing.cast(Address, request.client).host
