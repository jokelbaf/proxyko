from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check() -> Response:
    """Health check."""
    return PlainTextResponse("OK")
