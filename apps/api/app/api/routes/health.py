from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-novel-studio-api"}


@router.get("/health/db")
async def health_db(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    try:
        await check_database(settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"database unavailable: {exc}",
        ) from exc
    return {"status": "ok", "database": "connected"}
