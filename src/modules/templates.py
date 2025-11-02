import os
import typing
from collections.abc import Sequence

from fastapi import Request
from fastapi.templating import Jinja2Templates as BaseJinja2Templates


class RouteInfo(typing.TypedDict):
    """Route information."""

    title: str
    active: str | None


ROUTE_INFO: dict[str, RouteInfo] = {
    "/dashboard/home": {"title": "Home", "active": "home"},
    "/dashboard/configs": {"title": "Configs", "active": "configs"},
    "/dashboard/configs/new": {"title": "New Config", "active": "configs"},
    "/dashboard/devices": {"title": "Devices", "active": "devices"},
    "/dashboard/devices/new": {"title": "Devices", "active": "devices"},
    "/dashboard/users": {"title": "Users", "active": "users"},
    "/dashboard/users/new": {"title": "Users", "active": "users"},
    "/dashboard/logs": {"title": "Logs", "active": "logs"},
    "/dashboard/settings": {"title": "Settings", "active": "settings"},
}


def auto_context_processor(request: Request) -> dict[str, typing.Any]:
    """Context processor that injects theme, page_title, and active_page automatically."""
    context: dict[str, typing.Any] = {"theme": getattr(request.state, "theme", "light")}

    path = request.url.path

    if path in ROUTE_INFO:
        route_info = ROUTE_INFO[path]
        context["page_title"] = route_info["title"]
        context["active_page"] = route_info["active"]
    else:
        for route_pattern, _ in ROUTE_INFO.items():
            if "/" in route_pattern and path.startswith(route_pattern.rsplit("/", 1)[0] + "/"):
                parts = path.split("/")
                if len(parts) >= 3:
                    section = parts[2]
                    context["page_title"] = f"Edit {section.capitalize().rstrip('s')}"
                    context["active_page"] = section
                break

    return context


class Jinja2Templates(BaseJinja2Templates):
    """Extended Jinja2Templates that automatically injects theme and page context."""

    def __init__(
        self,
        directory: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
        **env_options: typing.Any,
    ) -> None:
        context_processors = [auto_context_processor]
        super().__init__(  # type: ignore
            directory=directory,
            context_processors=context_processors,
            **env_options,
        )
