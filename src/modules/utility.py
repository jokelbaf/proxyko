import os
import typing


@typing.overload
def get_env_var(name: str, required: typing.Literal[True]) -> str: ...


@typing.overload
def get_env_var(name: str, required: typing.Literal[False] = ...) -> str | None: ...


def get_env_var(name: str, required: bool = False) -> str | None:
    """Get an environment variable, raising an error if not found and required is True."""
    if (value := os.getenv(name)) is not None or not required:
        return value
    raise RuntimeError(f"Required environment variable '{name}' is not set.")
