import ipaddress
import re
import time
import typing
import urllib.parse
from typing import Annotated, TypeVar

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, BeforeValidator

from db.models import GlobalConfig, ProtocolType, ProxyAction, ProxyRule, PydanticProxyRule, User
from modules.templates import Jinja2Templates
from routes.api.internal.proxy import notify_rules_change, notify_status_change

T = TypeVar("T")

type EmptyToNone[T] = Annotated[T, BeforeValidator(lambda v: None if (v == "") else v)]

router = APIRouter()

templates = Jinja2Templates(directory="templates")


class ProxyRuleFormModel(BaseModel):
    name: str
    description: EmptyToNone[str | None] = None
    ip_filter: EmptyToNone[str | None] = None
    protocol_matches: str = ""
    host_matches: EmptyToNone[str | None] = None
    port_matches: EmptyToNone[str | None] = None
    path_matches: EmptyToNone[str | None] = None
    query_str_matches: EmptyToNone[str | None] = None
    action: ProxyAction
    forward_protocol: EmptyToNone[str | None] = None
    forward_host: EmptyToNone[str | None] = None
    forward_port: str = ""


def validate_ip_filter(ip_filter: str) -> bool:
    """Validate IP filter format (comma-separated IPs or CIDR ranges)."""
    entries = [entry.strip() for entry in ip_filter.split(",")]

    for entry in entries:
        if not entry:
            continue

        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return False

    return True


def validate_port_matches(port_matches: str) -> bool:
    """Validate port matches format (comma-separated ports or port ranges)."""
    entries = [entry.strip() for entry in port_matches.split(",")]

    for entry in entries:
        if not entry:
            continue

        # Check if it's a range (e.g., 80-443)
        if "-" in entry:
            parts = entry.split("-")
            if len(parts) != 2:
                return False
            try:
                start, end = int(parts[0]), int(parts[1])
                if not (1 <= start <= 65535 and 1 <= end <= 65535 and start <= end):
                    return False
            except ValueError:
                return False
        else:
            # Single port
            try:
                port = int(entry)
                if not (1 <= port <= 65535):
                    return False
            except ValueError:
                return False

    return True


def validate_host_matches(host_matches: str) -> bool:
    """Validate host matches format (wildcards allowed)."""
    if len(host_matches) > 255:
        return False

    # Allow wildcards like *.example.com or example.*
    pattern = r"^[\w\-\*\.]+$"
    return bool(re.match(pattern, host_matches))


def validate_proxy_rule(form_data: ProxyRuleFormModel, forward_port_int: int | None) -> list[str]:
    """Validate proxy rule form data."""
    errors: list[str] = []

    if not form_data.name or len(form_data.name) < 3 or len(form_data.name) > 64:
        errors.append("Rule name must be between 3 and 64 characters long.")

    if form_data.description is not None and len(form_data.description) > 256:
        errors.append("Description cannot exceed 256 characters.")

    if form_data.ip_filter:
        if len(form_data.ip_filter) > 500:
            errors.append("IP filter cannot exceed 500 characters.")
        elif not validate_ip_filter(form_data.ip_filter):
            errors.append(
                "IP filter format is invalid. Use comma-separated IP addresses or CIDR ranges "
                "(e.g., 192.168.1.0/24, 10.0.0.1)."
            )

    if form_data.action not in list(ProxyAction):
        errors.append("Invalid proxy action selected.")

    if form_data.protocol_matches and form_data.protocol_matches not in [
        e.value for e in ProtocolType
    ]:
        errors.append("Invalid protocol type selected.")

    if form_data.host_matches:
        if len(form_data.host_matches) > 255:
            errors.append("Host matches cannot exceed 255 characters.")
        elif not validate_host_matches(form_data.host_matches):
            errors.append(
                "Host matches format is invalid. Use valid hostnames with optional wildcards."
            )

    if form_data.port_matches:
        if len(form_data.port_matches) > 255:
            errors.append("Port matches cannot exceed 255 characters.")
        elif not validate_port_matches(form_data.port_matches):
            errors.append(
                "Port matches format is invalid. Use comma-separated ports or port ranges "
                "(e.g., 80, 443, 8080-8090)."
            )

    if form_data.path_matches and len(form_data.path_matches) > 255:
        errors.append("Path matches cannot exceed 255 characters.")

    if form_data.query_str_matches and len(form_data.query_str_matches) > 255:
        errors.append("Query string matches cannot exceed 255 characters.")

    if form_data.action == ProxyAction.FORWARD:
        if not form_data.forward_host:
            errors.append("Forward IP is required when action is set to Forward.")
        elif len(form_data.forward_host) > 255:
            errors.append("Forward IP cannot exceed 255 characters.")

        if forward_port_int is None:
            errors.append("Forward port is required when action is set to Forward.")
        elif not (1 <= forward_port_int <= 65535):
            errors.append("Forward port must be between 1 and 65535.")

        if form_data.forward_protocol and form_data.forward_protocol not in [
            "http",
            "https",
            "socks5",
        ]:
            errors.append("Invalid forward protocol. Use http, https, or socks5.")

    return errors


def proxy_rule_to_dict(rule: ProxyRule) -> dict[str, typing.Any]:
    """Convert a ProxyRule model to a dictionary with formatted data."""
    action_display_map = {
        "FORWARD": "Forward to Proxy",
        "DIRECT": "Direct Connection",
        "BLOCK": "Block Connection",
    }

    dict_rule = PydanticProxyRule.model_validate(rule).model_dump()
    dict_rule["action_display"] = action_display_map.get(rule.action, rule.action)

    for k, v in dict_rule.items():
        if v is None:
            dict_rule[k] = ""

    return dict_rule


def proxy_rules_to_dicts(rules: list[ProxyRule]) -> list[dict[str, typing.Any]]:
    """Convert ProxyRule models to dictionaries with formatted data."""
    return [proxy_rule_to_dict(rule) for rule in rules]


@router.get("/dashboard/proxy", tags=["Dashboard"])
async def proxy(
    request: Request,
    message: str | None = None,
    errors: list[str] | None = None,
) -> Response:
    """Display all proxy rules."""
    user: User = request.state.user
    config: GlobalConfig = request.app.state.global_config
    rules = await ProxyRule.filter(user=user).order_by("priority")

    is_proxy_healthy = (
        request.app.state.last_proxy_heartbeat_time is not None
        and time.time() - request.app.state.last_proxy_heartbeat_time < 30
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.proxy.html",
        context={
            "user": user,
            "rules": proxy_rules_to_dicts(rules),
            "proxy_enabled": config.enable_proxy,
            "is_proxy_healthy": is_proxy_healthy,
            "message": message,
            "errors": errors or [],
        },
    )


@router.get("/dashboard/proxy/rule/new", tags=["Dashboard"])
async def new_proxy_rule(
    request: Request,
    errors: list[str] | None = None,
) -> Response:
    """Display the new proxy rule page."""
    user: User = request.state.user

    return templates.TemplateResponse(
        request=request,
        name="dashboard.proxy.rule.html",
        context={
            "user": user,
            "rule": None,
            "protocol_types": [e.value for e in ProtocolType],
            "proxy_actions": [e.value for e in ProxyAction],
            "errors": errors or [],
        },
    )


@router.post("/dashboard/proxy/rule/new", tags=["Dashboard"])
async def create_proxy_rule(
    request: Request,
    form_data: ProxyRuleFormModel = Form(),
) -> Response:
    """Create a new proxy rule."""
    user: User = request.state.user

    protocol_matches_enum = (
        ProtocolType(form_data.protocol_matches) if form_data.protocol_matches else None
    )
    forward_port_int = int(form_data.forward_port) if form_data.forward_port else None

    errors = validate_proxy_rule(form_data, forward_port_int)

    if errors:
        return await new_proxy_rule(request, errors=errors)

    # Get the highest priority and add 1
    top_priority_rule = await ProxyRule.filter(user=user).order_by("-priority").first()

    await ProxyRule.create(
        user=user,
        priority=(top_priority_rule.priority + 1) if top_priority_rule else 1,
        protocol_matches=protocol_matches_enum,
        forward_port=forward_port_int,
        **form_data.model_dump(exclude={"protocol_matches", "forward_port"}),
    )

    await notify_rules_change()

    query_string = urllib.parse.urlencode({"message": "Proxy rule created successfully."})
    return RedirectResponse(
        url="/dashboard/proxy?" + query_string,
        status_code=303,
    )


@router.get("/dashboard/proxy/rule/{rule_id}", tags=["Dashboard"])
async def proxy_rule(
    request: Request,
    rule_id: int,
    errors: list[str] | None = None,
) -> Response:
    """Display a specific proxy rule page for editing."""
    user: User = request.state.user
    rule = await ProxyRule.get_or_none(id=rule_id, user=user)

    if rule is None:
        raise HTTPException(status_code=404, detail="The requested proxy rule does not exist.")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.proxy.rule.html",
        context={
            "user": user,
            "rule": proxy_rule_to_dict(rule),
            "protocol_types": [e.value for e in ProtocolType],
            "proxy_actions": [e.value for e in ProxyAction],
            "errors": errors or [],
        },
    )


@router.post("/dashboard/proxy/rule/{rule_id}", tags=["Dashboard"])
async def update_proxy_rule(
    request: Request,
    rule_id: int,
    form_data: ProxyRuleFormModel = Form(),
) -> Response:
    """Update an existing proxy rule."""
    user: User = request.state.user
    existing_rule = await ProxyRule.get_or_none(id=rule_id, user=user)

    if existing_rule is None:
        raise HTTPException(status_code=404, detail="The requested proxy rule does not exist.")

    protocol_matches_enum = (
        ProtocolType(form_data.protocol_matches) if form_data.protocol_matches else None
    )
    forward_port_int = int(form_data.forward_port) if form_data.forward_port else None

    errors = validate_proxy_rule(form_data, forward_port_int)

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.proxy.rule.html",
            context={
                "user": user,
                "rule": existing_rule,
                "protocol_types": [e.value for e in ProtocolType],
                "proxy_actions": [e.value for e in ProxyAction],
                "errors": errors,
            },
        )

    existing_rule.update_from_dict(  # type: ignore
        {
            **form_data.model_dump(exclude={"protocol_matches", "forward_port"}),
            "protocol_matches": protocol_matches_enum,
            "forward_port": forward_port_int,
        }
    )

    await existing_rule.save(
        update_fields=[
            "name",
            "description",
            "ip_filter",
            "protocol_matches",
            "host_matches",
            "port_matches",
            "path_matches",
            "query_str_matches",
            "action",
            "forward_protocol",
            "forward_host",
            "forward_port",
        ]
    )

    await notify_rules_change()

    query_string = urllib.parse.urlencode({"message": "Proxy rule updated successfully."})
    return RedirectResponse(
        url="/dashboard/proxy?" + query_string,
        status_code=303,
    )


@router.delete("/dashboard/proxy/rule/{rule_id}", tags=["Dashboard"])
async def delete_proxy_rule(request: Request, rule_id: int) -> Response:
    """Delete an existing proxy rule."""
    user: User = request.state.user
    existing_rule = await ProxyRule.get_or_none(id=rule_id, user=user)

    if existing_rule is None:
        raise HTTPException(status_code=404, detail="The requested proxy rule does not exist.")

    deleted_priority = existing_rule.priority
    await existing_rule.delete()

    rules_to_reorder = await ProxyRule.filter(
        user=user, priority__gt=deleted_priority
    ).order_by("priority")
    for rule in rules_to_reorder:
        rule.priority -= 1
        await rule.save(update_fields=["priority"])

    await notify_rules_change()

    query_string = urllib.parse.urlencode({"message": "Proxy rule deleted successfully."})
    return RedirectResponse(
        url="/dashboard/proxy?" + query_string,
        status_code=303,
    )


@router.post("/dashboard/proxy/rule/{rule_id}/priority", tags=["Dashboard"])
async def update_proxy_rule_priority(
    request: Request,
    rule_id: int,
    priority: int = Form(...),
) -> Response:
    """Update the priority of a proxy rule and reorder others accordingly."""
    user: User = request.state.user
    rule = await ProxyRule.get_or_none(id=rule_id, user=user)

    if rule is None:
        raise HTTPException(status_code=404, detail="The requested proxy rule does not exist.")

    old_priority = rule.priority
    new_priority = priority

    if old_priority == new_priority:
        return Response(status_code=200)

    all_rules = await ProxyRule.filter(user=user).order_by("priority")

    if old_priority < new_priority:
        for r in all_rules:
            if old_priority < r.priority <= new_priority:
                r.priority -= 1
                await r.save(update_fields=["priority"])
    else:
        for r in all_rules:
            if new_priority <= r.priority < old_priority:
                r.priority += 1
                await r.save(update_fields=["priority"])

    rule.priority = new_priority
    await rule.save(update_fields=["priority"])

    await notify_rules_change()

    return Response(status_code=200)


@router.post("/dashboard/proxy/status", tags=["Dashboard"])
async def toggle_proxy_status(
    request: Request,
    enable_proxy: bool = Form(...),
) -> Response:
    """Toggle proxy server status."""
    config: GlobalConfig = request.app.state.global_config

    config.enable_proxy = enable_proxy
    await config.save(update_fields=["enable_proxy"])

    await notify_status_change(request.app.state)

    return Response(status_code=200)


@router.post("/dashboard/proxy/rule/{rule_id}/toggle", tags=["Dashboard"])
async def toggle_rule(
    _: Request,
    rule_id: int,
    is_enabled: bool = Form(...),
) -> Response:
    """Toggle rule enabled status."""
    existing_rule = await ProxyRule.get_or_none(id=rule_id)

    if existing_rule is None:
        raise HTTPException(status_code=404, detail="The requested rule does not exist.")

    existing_rule.is_enabled = is_enabled
    await existing_rule.save(update_fields=["is_enabled"])

    return Response(status_code=200)
