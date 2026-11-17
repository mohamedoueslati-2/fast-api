"""HTTP endpoints for files."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services import files

router = APIRouter(tags=["files"])


@router.get("/files")
def list_files():
    return files.list_files()


@router.get("/files/{filename}")
def get_file(filename: str):
    return FileResponse(files.get_file(filename))
