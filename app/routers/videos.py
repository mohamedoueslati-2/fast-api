"""HTTP endpoints for videos."""

from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from fastapi.responses import FileResponse

from app.services import videos

router = APIRouter(tags=["videos"])


@router.get("/videos")
def list_videos():
    return videos.list_videos()


@router.get("/videos/{video_id}")
def read_video(video_id: str):
    return FileResponse(videos.read_video(video_id))


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: str):
    videos.delete_video(video_id)
    return Response(status_code=204)


@router.post("/videos", status_code=201)
async def upload_video(file: Annotated[UploadFile, File()]):
    return await videos.upload_video(file)
