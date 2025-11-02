import secrets
import typing
import urllib.parse

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from db.models import Device, DeviceType, User
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


def devices_to_dicts(devices: list[Device]) -> list[dict[str, typing.Any]]:
    """Convert Device models to dictionaries with formatted data."""
    type_display_map = {
        "DESKTOP": "Desktop",
        "APPLE": "Apple",
        "ANDROID": "Android",
        "TV": "TV",
        "OTHER": "Other",
    }

    dict_devices: list[dict[str, typing.Any]] = []
    for device in devices:
        dict_devices.append(
            {
                "id": device.id,
                "name": device.name,
                "type": device.type,
                "type_display": type_display_map.get(device.type, device.type),
                "token": device.token,
                "created_at": device.created_at,
                "updated_at": device.updated_at,
            }
        )
    return dict_devices


@router.get("/dashboard/devices", tags=["Dashboard"])
async def devices(
    request: Request,
    message: str | None = None,
) -> Response:
    """Display all devices."""
    user: User = request.state.user
    devices = await Device.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.devices.html",
        context={
            "user": user,
            "devices": devices_to_dicts(devices),
            "device_types": [dt.value for dt in DeviceType],
            "message": message,
            "errors": [],
            "modal_device": None,
            "modal_errors": [],
            "display_modal": False,
        },
    )


@router.get("/dashboard/devices/new", tags=["Dashboard"])
async def new_device(request: Request) -> Response:
    """Display the new device modal."""
    user: User = request.state.user
    devices = await Device.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.devices.html",
        context={
            "user": user,
            "devices": devices_to_dicts(devices),
            "device_types": [dt.value for dt in DeviceType],
            "message": None,
            "errors": [],
            "modal_device": None,
            "modal_errors": [],
            "display_modal": True,
        },
    )


@router.post("/dashboard/devices/new", tags=["Dashboard"])
async def create_device(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
) -> Response:
    """Create a new device."""
    user: User = request.state.user
    devices = await Device.all()

    errors: list[str] = []

    if not name or len(name) < 1 or len(name) > 255:
        errors.append("Device name must be between 1 and 255 characters long.")

    if type not in [dt.value for dt in DeviceType]:
        errors.append("Invalid device type selected.")

    if any(d.name == name for d in devices):
        errors.append("A device with this name already exists.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.devices.html",
            context={
                "user": user,
                "devices": devices_to_dicts(devices),
                "device_types": [dt.value for dt in DeviceType],
                "message": None,
                "errors": [],
                "modal_device": {"name": name, "type": type},
                "modal_errors": errors,
                "display_modal": True,
            },
        )

    device_token = secrets.token_urlsafe(32)
    await Device.create(user=user, name=name, type=type, token=device_token)

    query_string = urllib.parse.urlencode({"message": "Device created successfully."})
    return RedirectResponse(url="/dashboard/devices?" + query_string, status_code=303)


@router.get("/dashboard/devices/{device_id}", tags=["Dashboard"])
async def device(request: Request, device_id: int) -> Response:
    """Display a specific device in the modal for editing."""
    user: User = request.state.user
    device = await Device.get_or_none(id=device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="The requested device does not exist.")

    devices = await Device.all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.devices.html",
        context={
            "user": user,
            "devices": devices_to_dicts(devices),
            "device_types": [dt.value for dt in DeviceType],
            "message": None,
            "errors": [],
            "modal_device": {
                "id": device.id,
                "name": device.name,
                "type": device.type,
                "token": device.token,
            },
            "modal_errors": [],
            "display_modal": True,
        },
    )


@router.post("/dashboard/devices/{device_id}", tags=["Dashboard"])
async def update_device(
    request: Request,
    device_id: int,
    name: str = Form(...),
    type: str = Form(...),
) -> Response:
    """Update an existing device."""
    user: User = request.state.user
    existing_device = await Device.get_or_none(id=device_id)

    if existing_device is None:
        raise HTTPException(status_code=404, detail="The requested device does not exist.")

    devices = await Device.all()
    errors: list[str] = []

    if not name or len(name) < 1 or len(name) > 255:
        errors.append("Device name must be between 1 and 255 characters long.")

    if type not in [dt.value for dt in DeviceType]:
        errors.append("Invalid device type selected.")

    if any(d.name == name and d.id != device_id for d in devices):
        errors.append("A device with this name already exists.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.devices.html",
            context={
                "user": user,
                "devices": devices_to_dicts(devices),
                "device_types": [dt.value for dt in DeviceType],
                "message": None,
                "errors": [],
                "modal_device": {
                    "id": device_id,
                    "name": name,
                    "type": type,
                    "token": existing_device.token,
                },
                "modal_errors": errors,
                "display_modal": True,
            },
        )

    existing_device.name = name
    existing_device.type = DeviceType(type)  # type: ignore
    await existing_device.save(update_fields=["name", "type"])

    query_string = urllib.parse.urlencode({"message": "Device updated successfully."})
    return RedirectResponse(url="/dashboard/devices?" + query_string, status_code=303)


@router.delete("/dashboard/devices/{device_id}", tags=["Dashboard"])
async def delete_device(_: Request, device_id: int) -> Response:
    """Delete a device."""
    existing_device = await Device.get_or_none(id=device_id)

    if existing_device is None:
        raise HTTPException(status_code=404, detail="The requested device does not exist.")

    await existing_device.delete()

    query_string = urllib.parse.urlencode({"message": "Device deleted successfully."})
    return RedirectResponse(url="/dashboard/devices?" + query_string, status_code=303)
