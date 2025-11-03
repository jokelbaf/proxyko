import typing

from fastapi import APIRouter, Request, Response
from loguru import logger

from db.models import AccessRecord, Config, ConfigMode, Device
from modules.utility import get_env_var, get_real_ip, is_ip_matched

router = APIRouter()

DEFAULT_RESPONSE = """
function FindProxyForURL(url, host) {
    return "DIRECT";
}
"""

BUILTIN_PROXY_RESPONSE = """
function FindProxyForURL(url, host) {
    // Use built-in proxy
    return "PROXY %s:%s";
}
"""

UNAUTHORIZED_RESPONSE = """
function FindProxyForURL(url, host) {
    alert("Unauthorized device. Proxy access denied.");
    return "DIRECT";
}
"""

MEDIA_TYPE = "application/x-ns-proxy-autoconfig"


def is_device_matched(device: Device | None, devices: list[Device]) -> bool:
    """Check if the given device matches any of the devices in the list."""
    if device is None:
        return False
    return any(d.id == device.id for d in devices)


def config_to_function(config: Config) -> str:
    """Convert a Config model to its PAC function representation."""
    if config.use_builtin_proxy:
        host = get_env_var("PROXY_PUBLIC_HOST")
        port = get_env_var("PROXY_PUBLIC_PORT")

        if not host or not port:
            logger.error(
                "PROXY_PUBLIC_HOST or PROXY_PUBLIC_PORT is not set in environment variables."
            )
            return DEFAULT_RESPONSE

        return BUILTIN_PROXY_RESPONSE % (host, port)

    return config.function


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
                return Response(config_to_function(config), media_type=MEDIA_TYPE)
        elif config.mode == ConfigMode.AND and ip_matched and device_matched:
            return Response(config_to_function(config), media_type=MEDIA_TYPE)

    return Response(DEFAULT_RESPONSE, media_type=MEDIA_TYPE)
