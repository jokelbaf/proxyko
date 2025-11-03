from datetime import UTC, datetime, timedelta
from enum import Enum

from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator  # type: ignore
from tortoise.models import Model


class DeviceType(str, Enum):
    DESKTOP = "DESKTOP"
    APPLE = "APPLE"
    ANDROID = "ANDROID"
    TV = "TV"
    OTHER = "OTHER"


class ConfigMode(str, Enum):
    OR = "OR"
    AND = "AND"


class ProxyAction(str, Enum):
    FORWARD = "FORWARD"
    """Forward the request to the specified proxy server."""
    PROXY = "DIRECT"
    """Directly send the request without proxying."""
    BLOCK = "BLOCK"
    """Deny the connection."""


class ProtocolType(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255)
    totp_secret = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    configs: fields.ReverseRelation["Config"]
    devices: fields.ReverseRelation["Device"]
    sessions: fields.ReverseRelation["Session"]
    proxy_rules: fields.ReverseRelation["ProxyRule"]

    class Meta:
        table = "users"


class Session(Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="sessions"
    )
    token = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    def is_expired(self) -> bool:
        """Check if the session is expired (valid for 7 days)."""
        return self.created_at + timedelta(days=7) < datetime.now(tz=UTC)

    class Meta:
        table = "sessions"


class Device(Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="devices"
    )
    name = fields.CharField(max_length=255)
    type = fields.CharEnumField(DeviceType, max_length=20)
    token = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    access_records: fields.ReverseRelation["AccessRecord"]
    configs: fields.ReverseRelation["Config"]

    class Meta:
        table = "devices"


class AccessRecord(Model):
    id = fields.IntField(pk=True)
    ip = fields.CharField(max_length=45)  # IPv6 max length
    user_agent = fields.TextField(null=True)
    device: fields.ForeignKeyNullableRelation["Device"] = fields.ForeignKeyField(
        "models.Device", related_name="access_records", null=True
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "access_records"


class Config(Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="configs"
    )
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    priority = fields.IntField()
    ip_filter = fields.CharField(max_length=500, null=True)
    function = fields.TextField()
    use_builtin_proxy = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    is_active = fields.BooleanField(default=True)
    mode = fields.CharEnumField(ConfigMode, max_length=10, default=ConfigMode.OR)

    devices: fields.ManyToManyRelation["Device"] = fields.ManyToManyField(
        "models.Device", related_name="configs"
    )

    class Meta:
        table = "configs"


class GlobalConfig(Model):
    server_id = fields.IntField(pk=True)
    require_auth = fields.BooleanField(default=False)
    enable_proxy = fields.BooleanField(default=True)

    class Meta:
        table = "global_config"


class ProxyRule(Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="proxy_rules"
    )
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    priority = fields.IntField()
    is_enabled = fields.BooleanField(default=True)
    ip_filter = fields.CharField(max_length=500, null=True)

    protocol_matches = fields.CharEnumField(ProtocolType, null=True)
    host_matches = fields.CharField(max_length=255, null=True)
    port_matches = fields.CharField(max_length=255, null=True)
    path_matches = fields.CharField(max_length=255, null=True)
    query_str_matches = fields.CharField(max_length=255, null=True)

    forward_protocol = fields.CharField(max_length=10, null=True)
    forward_host = fields.CharField(max_length=255, null=True)
    forward_port = fields.IntField(null=True)

    action = fields.CharEnumField(ProxyAction, max_length=10, default=ProxyAction.FORWARD)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "proxy_rules"


PydanticUser = pydantic_model_creator(
    User,
    name="PydanticUser",
    exclude=("password",),
    model_config={"from_attributes": True},
)

PydanticProxyRule = pydantic_model_creator(
    ProxyRule,
    name="PydanticProxyRule",
    model_config={"from_attributes": True},
)
