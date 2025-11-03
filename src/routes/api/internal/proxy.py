import time
import typing

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from db.models import ProxyRule, PydanticProxyRule
from modules.templates import Jinja2Templates
from modules.utility import get_env_var

router = APIRouter(prefix="/api/internal/proxy")

templates = Jinja2Templates(directory="templates")

active_connections: set[WebSocket] = set()
"""Set of currently connected WebSocket clients."""

class SocketMsg(typing.TypedDict):
    action: typing.Literal[
        "error",
        "login_req",
        "login_res",
        "heartbeat_push",
        "status_notify",
        "rules_notify",
    ]
    message: str | None
    data: dict[str, typing.Any] | None


async def notify_status_change(app_state: typing.Any) -> None:
    """Notify all connected clients about status change."""
    status_data = {
        "enabled": app_state.global_config.enable_proxy,
        "require_auth": app_state.global_config.require_auth,
    }

    disconnected: set[WebSocket] = set()
    for connection in active_connections:
        try:
            await connection.send_json({
                "action": "status_notify",
                "message": "Proxy status changed",
                "data": status_data,
            })
        except Exception:
            disconnected.add(connection)

    for conn in disconnected:
        active_connections.discard(conn)


async def notify_rules_change() -> None:
    """Notify all connected clients about rules change."""
    rules = await ProxyRule.all()
    dict_rules: list[dict[str, typing.Any]] = []

    for rule in rules:
        pd_rule = PydanticProxyRule.model_validate(rule)
        dict_rules.append(pd_rule.model_dump(mode='json'))

    disconnected: set[WebSocket] = set()
    for connection in active_connections:
        try:
            await connection.send_json({
                "action": "rules_notify",
                "message": "Proxy rules changed",
                "data": dict_rules,
            })
        except Exception:
            disconnected.add(connection)

    for conn in disconnected:
        active_connections.discard(conn)


@router.get("/rules", tags=["API"])
async def rules(_: Request) -> Response:
    """Get all proxy rules."""
    rules = await ProxyRule.all()

    dict_rules: list[dict[str, typing.Any]] = []

    for rule in rules:
        pd_rule = PydanticProxyRule.model_validate(rule)
        dict_rules.append(pd_rule.model_dump(mode='json'))

    return JSONResponse(
        content={
            "status": 200,
            "message": "OK",
            "data": dict_rules,
        })

@router.get("/status", tags=["API"])
async def status(request: Request) -> Response:
    """Get proxy status."""
    return JSONResponse(
        content={
            "status": 200,
            "message": "OK",
            "data": {
                "enabled": request.app.state.global_config.enable_proxy,
                "require_auth": request.app.state.global_config.require_auth,
            }
        })


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for proxy communication."""
    await websocket.accept()

    authenticated = False
    api_key = get_env_var("INTERNAL_API_KEY")

    try:
        while True:
            data: SocketMsg = await websocket.receive_json()

            action = data.get("action")
            msg_data = data.get("data")

            if action == "login_req":
                provided_key = msg_data.get("api_key") if msg_data else None

                if api_key and provided_key == api_key:
                    authenticated = True
                    active_connections.add(websocket)

                    status_data = {
                        "enabled": websocket.app.state.global_config.enable_proxy,
                        "require_auth": websocket.app.state.global_config.require_auth,
                    }
                    await websocket.send_json({
                        "action": "status_notify",
                        "message": "OK",
                        "data": status_data,
                    })

                    rules = await ProxyRule.all()
                    dict_rules: list[dict[str, typing.Any]] = []
                    for rule in rules:
                        pd_rule = PydanticProxyRule.model_validate(rule)
                        dict_rules.append(pd_rule.model_dump(mode='json'))

                    await websocket.send_json({
                        "action": "rules_notify",
                        "message": "OK",
                        "data": dict_rules,
                    })

                    await websocket.send_json({
                        "action": "login_res",
                        "message": "OK",
                        "data": None,
                    })
                else:
                    await websocket.send_json({
                        "action": "error",
                        "message": "Authentication failed",
                        "data": None,
                    })
                    await websocket.close(code=1008, reason="Unauthorized")
                    return

            elif not authenticated:
                await websocket.send_json({
                    "action": "error",
                    "message": "Not authenticated",
                    "data": None,
                })
                await websocket.close(code=1008, reason="Unauthorized")
                return

            elif action == "heartbeat_push":
                websocket.app.state.last_proxy_heartbeat_time = time.time()

    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)
    finally:
        active_connections.discard(websocket)
