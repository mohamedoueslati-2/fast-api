"""HTTP endpoints for clips."""

from fastapi import APIRouter, Response

from app.schemas import ClipRequest
from app.services import clips

router = APIRouter(tags=["clips"])


@router.get("/videos/{video_id}/clips")
def list_clips(video_id: str):
    return clips.list_clips(video_id)


@router.delete("/videos/{video_id}/clips/{clip_id}", status_code=204)
def delete_clip(video_id: str, clip_id: str):
    clips.delete_clip(video_id, clip_id)
    return Response(status_code=204)


@router.post("/videos/{video_id}/clips", status_code=201)
def create_clips(video_id: str, request: ClipRequest):
    return clips.create_clips(video_id, request)
