import re
import typing
import urllib.parse
from typing import Annotated, TypeVar

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, BeforeValidator

from db.models import Config, ConfigMode, Device, User
from modules.templates import Jinja2Templates
from modules.utility import get_env_var

T = TypeVar("T")

type EmptyToNone[T] = Annotated[T, BeforeValidator(lambda v: None if (v == "") else v)]

router = APIRouter()

templates = Jinja2Templates(directory="templates")


class ConfigFormModel(BaseModel):
    name: str
    description: EmptyToNone[str | None] = None
    ip_filter: EmptyToNone[str | None] = None
    function: str
    is_active: bool = False
    use_builtin_proxy: bool = False
    device_ids: list[str] = []
    mode: ConfigMode


def validate_pac_file(content: str) -> bool:
    """Validate PAC (Proxy Auto-Config) file content."""
    content_no_comments = re.sub(r"//.*?$", "", content, flags=re.MULTILINE)
    content_no_comments = re.sub(r"/\*.*?\*/", "", content_no_comments, flags=re.DOTALL)

    pattern = r"function\s+FindProxyForURL\s*\(\s*\w+\s*,\s*\w+\s*\)\s*\{"

    return bool(re.search(pattern, content_no_comments, re.IGNORECASE | re.DOTALL))


def validate_ip_filter(ip_filter: str) -> bool:
    """Validate IP filter format (comma-separated IPs or CIDR ranges)."""
    import ipaddress

    entries = [entry.strip() for entry in ip_filter.split(",")]

    for entry in entries:
        if not entry:
            continue

        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return False

    return True


def validate_config(form_data: ConfigFormModel) -> list[str]:
    """Validate config form data."""
    errors: list[str] = []

    if not form_data.name or len(form_data.name) < 3 or len(form_data.name) > 64:
        errors.append("Config name must be between 3 and 64 characters long.")

    if form_data.description is not None and len(form_data.description) > 256:
        errors.append("Description cannot exceed 256 characters.")

    if form_data.ip_filter is not None:
        if len(form_data.ip_filter) > 500:
            errors.append("IP filter cannot exceed 500 characters.")
        elif not validate_ip_filter(form_data.ip_filter):
            errors.append(
                "IP filter format is invalid. Use comma-separated IP addresses or CIDR ranges "
                "(e.g., 192.168.1.0/24, 10.0.0.1)."
            )

    if form_data.mode not in [ConfigMode.AND, ConfigMode.OR]:
        errors.append("Invalid config mode selected.")

    if not validate_pac_file(form_data.function):
        errors.append(
            "PAC file content is invalid. Ensure it contains a valid FindProxyForURL function."
        )

    return errors


def configs_to_dicts(configs: list[Config]) -> list[dict[str, typing.Any]]:
    """Convert Config models to dictionaries with formatted data."""
    mode_display_map = {"OR": "Any Match", "AND": "All Match"}

    dict_configs: list[dict[str, typing.Any]] = []
    for config in configs:
        dict_configs.append(
            {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "priority": config.priority,
                "ip_filter": config.ip_filter,
                "function": config.function,
                "is_active": config.is_active,
                "use_builtin_proxy": config.use_builtin_proxy,
                "mode": config.mode,
                "mode_display": mode_display_map.get(config.mode, config.mode),
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "devices": config.devices if hasattr(config, "devices") else [],
            }
        )
    return dict_configs


@router.get("/dashboard/configs", tags=["Dashboard"])
async def configs(
    request: Request,
    message: str | None = None,
    errors: list[str] | None = None,
) -> Response:
    """Display all configs."""
    user: User = request.state.user
    configs_list = await Config.all().prefetch_related("devices").order_by("priority")
    devices = await Device.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.configs.html",
        context={
            "user": user,
            "configs": configs_to_dicts(configs_list),
            "devices": devices,
            "message": message,
            "errors": errors or [],
        },
    )


@router.get("/dashboard/configs/new", tags=["Dashboard"])
async def new_config(
    request: Request,
    errors: list[str] | None = None,
) -> Response:
    """Display the new config page."""
    user: User = request.state.user
    devices = await Device.all()

    proxy_host = get_env_var("PROXY_PUBLIC_HOST")
    proxy_port = get_env_var("PROXY_PUBLIC_PORT")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.config.html",
        context={
            "user": user,
            "devices": devices,
            "config": None,
            "proxy_host": proxy_host,
            "proxy_port": proxy_port,
            "errors": errors or [],
        },
    )


@router.post("/dashboard/configs/new", tags=["Dashboard"])
async def create_config(
    request: Request,
    form_data: ConfigFormModel = Form(),
) -> Response:
    """Create a new config."""
    user: User = request.state.user

    errors = validate_config(form_data)

    device_ids_parsed = [int(d_id) for d_id in form_data.device_ids if d_id.isdigit()]

    if errors:
        devices = await Device.all()
        proxy_host = get_env_var("PROXY_PUBLIC_HOST")
        proxy_port = get_env_var("PROXY_PUBLIC_PORT")

        return templates.TemplateResponse(
            request=request,
            name="dashboard.config.html",
            context={
                "user": user,
                "devices": devices,
                "config": None,
                "proxy_host": proxy_host,
                "proxy_port": proxy_port,
                "errors": errors,
            },
        )

    top_priority_config = await Config.all().order_by("-priority").first()

    new_config = await Config.create(
        user=user,
        priority=(top_priority_config.priority + 1) if top_priority_config else 1,
        **form_data.model_dump(exclude={"device_ids"}),
    )

    if device_ids_parsed:
        devices = await Device.filter(id__in=device_ids_parsed)
        await new_config.devices.add(*devices)

    query_string = urllib.parse.urlencode({"message": "Config created successfully."})
    return RedirectResponse(
        url="/dashboard/configs?" + query_string,
        status_code=303,
    )


@router.get("/dashboard/configs/{config_id}", tags=["Dashboard"])
async def config(
    request: Request,
    config_id: int,
    errors: list[str] | None = None,
) -> Response:
    """Display a specific config page for editing."""
    user: User = request.state.user
    config = await Config.get_or_none(id=config_id).prefetch_related("devices")
    devices = await Device.all()

    if config is None:
        raise HTTPException(status_code=404, detail="The requested config does not exist.")

    proxy_host = get_env_var("PROXY_PUBLIC_HOST")
    proxy_port = get_env_var("PROXY_PUBLIC_PORT")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.config.html",
        context={
            "user": user,
            "devices": devices,
            "config": config,
            "proxy_host": proxy_host,
            "proxy_port": proxy_port,
            "errors": errors or [],
        },
    )


@router.post("/dashboard/configs/{config_id}", tags=["Dashboard"])
async def update_config(
    request: Request,
    config_id: int,
    form_data: ConfigFormModel = Form(),
) -> Response:
    """Update an existing config."""
    user: User = request.state.user
    existing_config = await Config.get_or_none(id=config_id).prefetch_related("devices")

    if existing_config is None:
        raise HTTPException(status_code=404, detail="The requested config does not exist.")

    errors = validate_config(form_data)

    device_ids_parsed = [int(d_id) for d_id in form_data.device_ids if d_id.isdigit()]

    if errors:
        devices = await Device.all()
        proxy_host = get_env_var("PROXY_PUBLIC_HOST")
        proxy_port = get_env_var("PROXY_PUBLIC_PORT")
        return templates.TemplateResponse(
            request=request,
            name="dashboard.config.html",
            context={
                "user": user,
                "devices": devices,
                "config": existing_config,
                "proxy_host": proxy_host,
                "proxy_port": proxy_port,
                "errors": errors,
            },
        )

    existing_config.update_from_dict(form_data.model_dump(exclude={"device_ids"}))  # type: ignore

    await existing_config.save(
        update_fields=[
            "name",
            "description",
            "ip_filter",
            "function",
            "is_active",
            "use_builtin_proxy",
            "mode",
        ]
    )

    await existing_config.devices.clear()
    if device_ids_parsed:
        devices = await Device.filter(id__in=device_ids_parsed)
        await existing_config.devices.add(*devices)

    query_string = urllib.parse.urlencode({"message": "Config updated successfully."})
    return RedirectResponse(
        url="/dashboard/configs?" + query_string,
        status_code=303,
    )


@router.delete("/dashboard/configs/{config_id}", tags=["Dashboard"])
async def delete_config(_: Request, config_id: int) -> Response:
    """Delete an existing config."""
    existing_config = await Config.get_or_none(id=config_id)

    if existing_config is None:
        raise HTTPException(status_code=404, detail="The requested config does not exist.")

    await existing_config.delete()

    query_string = urllib.parse.urlencode({"message": "Config deleted successfully."})
    return RedirectResponse(
        url="/dashboard/configs?" + query_string,
        status_code=303,
    )


@router.post("/dashboard/configs/{config_id}/priority", tags=["Dashboard"])
async def update_config_priority(
    _: Request,
    config_id: int,
    priority: int = Form(...),
) -> Response:
    """Update the priority of a config."""
    configs = await Config.all().order_by("priority")
    target = next((c for c in configs if c.id == config_id), None)

    if target is None:
        raise HTTPException(status_code=404, detail="The requested config does not exist.")

    configs.remove(target)
    priority = max(1, min(priority, len(configs) + 1))
    configs.insert(priority - 1, target)

    for i, config in enumerate(configs, start=1):
        if config.priority != i:
            config.priority = i
            await config.save(update_fields=["priority"])

    return Response(status_code=200)


@router.post("/dashboard/configs/{config_id}/toggle", tags=["Dashboard"])
async def toggle_config(
    _: Request,
    config_id: int,
    is_active: bool = Form(...),
) -> Response:
    """Toggle config active status."""
    existing_config = await Config.get_or_none(id=config_id)

    if existing_config is None:
        raise HTTPException(status_code=404, detail="The requested config does not exist.")

    existing_config.is_active = is_active
    await existing_config.save(update_fields=["is_active"])

    return Response(status_code=200)
