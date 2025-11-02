from loguru import logger
from tortoise import Tortoise

from db.models import GlobalConfig
from modules.utility import get_env_var


def generate_db_url_from_env() -> str | None:
    """Generate the database URL from individual environment variables."""
    db_user = get_env_var("MARIADB_USER")
    db_password = get_env_var("MARIADB_PASSWORD")
    db_name = get_env_var("MARIADB_DATABASE")
    db_host = get_env_var("MARIADB_HOST") or "localhost"
    db_port = get_env_var("MARIADB_PORT") or "3306"

    if db_user and db_password and db_name:
        return f"mysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return None


async def init() -> GlobalConfig:
    """Initialize Tortoise ORM with MariaDB connection."""
    database_url = generate_db_url_from_env() or get_env_var("DB_URL", required=True)

    logger.info("Connecting to database...")

    await Tortoise.init(
        db_url=database_url,
        modules={"models": ["db.models.common"]},
    )

    logger.info("Database connected successfully")

    await Tortoise.generate_schemas()
    logger.info("Database schemas generated")

    config, _ = await GlobalConfig.get_or_create(  # type: ignore[misc]
        server_id=1, defaults={"require_auth": False}
    )
    return config


async def close():
    """Close all database connections."""
    await Tortoise.close_connections()
    logger.info("Database connections closed")
