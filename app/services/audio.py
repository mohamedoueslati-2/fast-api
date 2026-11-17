"""Audio business operations."""

import subprocess
from uuid import uuid4

from app.core import storage
from app.core.errors import AppError
from app.schemas import AudioRequest
from app.services import media


def extract_audio(video_id: str, request: AudioRequest):
    """Extrait l'audio d'une vidéo originale ou d'un extrait."""
    source = storage.video_file(video_id)
    audio_id = uuid4().hex
    destination = storage.ROOT / f"{audio_id}.{request.format}"
    codec = "libmp3lame" if request.format == "mp3" else "pcm_s16le"
    try:
        media.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                codec,
                str(destination),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        destination.unlink(missing_ok=True)
        raise AppError(503, "FFmpeg is not installed or not in PATH") from exc
    except subprocess.CalledProcessError as exc:
        destination.unlink(missing_ok=True)
        raise AppError(
            422, "Unable to extract audio; check that the video has an audio track"
        ) from exc
    return {
        "audio_id": audio_id,
        "source_id": video_id,
        "format": request.format,
        "filename": destination.name,
        "url": f"/files/{destination.name}",
    }
