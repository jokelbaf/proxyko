from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response

from db.models import AccessRecord, Config, Device, User
from modules.templates import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/dashboard/home", tags=["Dashboard"])
async def home(request: Request) -> Response:
    """Display home dashboard with statistics."""
    user: User = request.state.user

    total_logs = await AccessRecord.all().count()
    total_devices = await Device.all().count()
    total_configs = await Config.all().count()
    active_configs = await Config.filter(is_active=True).count()

    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_logs = await AccessRecord.filter(created_at__gte=seven_days_ago).order_by("-created_at")

    logs_by_date: defaultdict[str, int] = defaultdict(int)
    for log in recent_logs:
        date_key = log.created_at.strftime("%Y-%m-%d")
        logs_by_date[date_key] += 1

    chart_labels: list[str] = []
    chart_data: list[int] = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_key = date.strftime("%Y-%m-%d")
        date_label = date.strftime("%b %d")
        chart_labels.append(date_label)
        chart_data.append(logs_by_date[date_key])

    access_records = await AccessRecord.all().prefetch_related("device")
    device_types: defaultdict[str, int] = defaultdict(int)
    for record in access_records:
        if record.device:
            device_types[record.device.type.value] += 1
        else:
            device_types["OTHER"] += 1

    recent_activity = (
        await AccessRecord.all().prefetch_related("device").order_by("-created_at").limit(5)
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.home.html",
        context={
            "user": user,
            "total_logs": total_logs,
            "total_devices": total_devices,
            "total_configs": total_configs,
            "active_configs": active_configs,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "device_types": dict(device_types),
            "recent_activity": recent_activity,
        },
    )
