"""Health check and web interface."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).resolve().parents[1] / "index.html")
