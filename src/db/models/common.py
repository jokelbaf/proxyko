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

    class Meta:
        table = "global_config"


PydanticReadUser = pydantic_model_creator(
    User,
    name="ReadUser",
    exclude=("password",),
    model_config={"from_attributes": True},
)

PydanticUser = pydantic_model_creator(
    User,
    name="User",
    exclude_readonly=True,
    exclude=("totp_secret", "created_at", "updated_at"),
)

PydanticDevice = pydantic_model_creator(
    Device,
    name="Device",
    exclude_readonly=True,
    exclude=("token", "created_at", "updated_at"),
)

PydanticConfig = pydantic_model_creator(Config, name="Config", exclude_readonly=True)
