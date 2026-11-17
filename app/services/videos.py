"""Videos business operations."""

from typing import Protocol
from uuid import uuid4

from app.core import storage
from app.core.errors import AppError


class UploadedFile(Protocol):
    """Only the file operations required by the upload service."""

    filename: str | None

    async def read(self, size: int) -> bytes: ...

    async def close(self) -> None: ...


def list_videos():
    """Liste les vidéos originales, sans mélanger leurs extraits."""
    clip_names = {
        clip.get("filename")
        for _, batch in storage.clip_batches()
        for clip in batch["clips"]
        if isinstance(clip, dict)
    }
    videos = []
    for path in sorted(storage.ROOT.glob("*.mp4")):
        if (
            path.is_file()
            and (not path.is_symlink())
            and (path.name not in clip_names)
            and (len(path.stem) == 32)
            and all(c in "0123456789abcdef" for c in path.stem)
        ):
            videos.append({"video_id": path.stem, "filename": path.name})
    return {"videos": videos}


def read_video(video_id: str):
    return storage.video_file(video_id)


def delete_video(video_id: str):
    path = storage.video_file(video_id)
    if not any(video["video_id"] == video_id for video in list_videos()["videos"]):
        raise AppError(404, "Video not found")
    for metadata_path, batch in storage.clip_batches():
        if batch.get("video_id") != video_id:
            continue
        for clip in batch["clips"]:
            if isinstance(clip, dict):
                clip_id = clip.get("clip_id", "")
                if (
                    isinstance(clip_id, str)
                    and len(clip_id) == 32
                    and all(c in "0123456789abcdef" for c in clip_id)
                ):
                    (storage.ROOT / f"{clip_id}.mp4").unlink(missing_ok=True)
        metadata_path.unlink()
    path.unlink()


async def upload_video(file: UploadedFile):
    """Enregistre un fichier MP4 et renvoie son identifiant."""
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise AppError(400, "Only MP4 files are allowed")
    video_id = uuid4().hex
    destination = storage.ROOT / f"{video_id}.mp4"
    try:
        with destination.open("wb") as output:
            while chunk := (await file.read(1024 * 1024)):
                output.write(chunk)
    finally:
        await file.close()
    return {"video_id": video_id, "filename": destination.name}
