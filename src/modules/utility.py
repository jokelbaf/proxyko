import ipaddress
import os
import typing

from fastapi import Request
from fastapi.datastructures import Address
from loguru import logger


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


def is_ip_matched(ip: str, ip_filter: str) -> bool:
    """Check if the given IP matches any of the IP addresses or CIDR ranges in the filter."""
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        logger.warning(f"Invalid IP address: {ip}")
        return False

    entries = [entry.strip() for entry in ip_filter.split(",")]

    for entry in entries:
        if not entry:
            continue

        try:
            network = ipaddress.ip_network(entry, strict=False)
            if ip_obj in network:
                return True
        except ValueError:
            logger.warning(f"Invalid IP filter entry: {entry}")
            continue

    return False
