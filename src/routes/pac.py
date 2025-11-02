import ipaddress
import typing

from fastapi import APIRouter, Request, Response
from fastapi.datastructures import Address
from loguru import logger

from db.models import AccessRecord, Config, ConfigMode, Device

router = APIRouter()

DEFAULT_RESPONSE = """
function FindProxyForURL(url, host) {
    return "DIRECT";
}
"""

UNAUTHORIZED_RESPONSE = """
function FindProxyForURL(url, host) {
    alert("Unauthorized device. Proxy access denied.");
    return "DIRECT";
}
"""

MEDIA_TYPE = "application/x-ns-proxy-autoconfig"


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


def is_device_matched(device: Device | None, devices: list[Device]) -> bool:
    """Check if the given device matches any of the devices in the list."""
    if device is None:
        return False
    return any(d.id == device.id for d in devices)


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


@router.get("/pac", tags=["PAC"])
async def pac(request: Request, device_token: str | None = None) -> Response:
    """Generate and return the PAC file based on active configurations."""
    if device_token is not None and len(device_token) > 64:
        # Prevent excessively long tokens
        return Response(UNAUTHORIZED_RESPONSE, media_type=MEDIA_TYPE)

    device = await Device.get_or_none(token=device_token)

    if device is None and request.app.state.global_config.require_auth:
        return Response(UNAUTHORIZED_RESPONSE, media_type=MEDIA_TYPE)

    user_agent = request.headers.get("User-Agent")

    record = await AccessRecord.create(
        ip=get_real_ip(request), user_agent=user_agent, device=device
    )

    configs = await Config.filter(is_active=True).order_by("priority")

    for config in configs:
        ip_filter = typing.cast(str | None, config.ip_filter)
        ip_matched = ip_filter is None or is_ip_matched(record.ip, ip_filter)

        config_devices = await config.devices.all()
        device_matched = not config_devices or is_device_matched(device, config_devices)

        if config.mode == ConfigMode.OR:
            if ip_matched or device_matched:
                return Response(config.function, media_type=MEDIA_TYPE)
        elif config.mode == ConfigMode.AND and ip_matched and device_matched:
            return Response(config.function, media_type=MEDIA_TYPE)

    return Response(DEFAULT_RESPONSE, media_type=MEDIA_TYPE)
