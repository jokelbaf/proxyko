from .dashboard import (
    configs_router,
    devices_router,
    home_router,
    logs_router,
    settings_router,
    users_router,
)
from .dashboard import (
    router as dashboard_router,
)
from .index import router as index_router
from .login import PendingLogins
from .login import router as login_router
from .logout import router as logout_router
from .pac import router as pac_router
from .register import router as register_router

__all__ = [
    "dashboard_router",
    "configs_router",
    "devices_router",
    "logs_router",
    "index_router",
    "login_router",
    "PendingLogins",
    "logout_router",
    "pac_router",
    "register_router",
    "settings_router",
    "users_router",
    "home_router",
]
