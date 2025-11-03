from fastapi import Request, Response
from fastapi.exceptions import HTTPException, ValidationException
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def rate_limit_exc_handler(request: Request, _: Exception) -> Response:
    """Handle rate limit exceeded errors."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 429,
            "title": "Too Many Requests",
            "details": (
                "Hold on there! You're making requests too quickly. "
                "Please slow down and try again in a moment."
            ),
        },
        status_code=429,
    )


def not_found_exc_handler(request: Request, exc: HTTPException) -> Response:
    """Handle not found errors."""
    details = (
        exc.detail
        if exc.detail and exc.detail != "Not Found"
        else "The requested resource was not found."
    )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 404,
            "title": "Not Found",
            "details": details,
        },
        status_code=404,
    )


def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handle generic HTTP exceptions."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": exc.status_code,
            "title": "Error",
            "details": exc.detail if exc.detail else "An unexpected error occurred.",
        },
        status_code=exc.status_code,
    )


def validation_exception_handler(request: Request, _: ValidationException) -> Response:
    """Handle validation errors."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 422,
            "title": "Validation Error",
            "details": "There was a problem with your input. Please check and try again.",
        },
        status_code=422,
    )


def internal_server_error_handler(request: Request, _: Exception) -> Response:
    """Handle internal server errors."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "request": request,
            "status": 500,
            "title": "Internal Server Error",
            "details": "Oops! Something went seriously wrong. Please try again later.",
        },
        status_code=500,
    )
