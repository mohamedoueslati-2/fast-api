"""HTTP endpoints for audio."""

from fastapi import APIRouter

from app.schemas import AudioRequest
from app.services import audio

router = APIRouter(tags=["audio"])


@router.post("/videos/{video_id}/audio", status_code=201)
def extract_audio(video_id: str, request: AudioRequest):
    return audio.extract_audio(video_id, request)
