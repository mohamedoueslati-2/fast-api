"""HTTP endpoints for frames."""

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.services import frames

router = APIRouter(tags=["frames"])


@router.post("/videos/{video_id}/frames", status_code=201)
def extract_frames(video_id: str):
    return frames.extract_frames(video_id)


@router.get("/videos/{video_id}/frames")
def list_frames(video_id: str):
    return frames.list_frames(video_id)


@router.get("/frames/{batch_id}/{filename}")
def read_frame(batch_id: str, filename: str):
    return FileResponse(frames.read_frame(batch_id, filename))


@router.delete("/frames/{batch_id}/{filename}", status_code=204)
def delete_frame(batch_id: str, filename: str):
    frames.delete_frame(batch_id, filename)
    return Response(status_code=204)
