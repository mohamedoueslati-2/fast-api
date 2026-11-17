"""Clips business operations."""

import json
import subprocess
from uuid import uuid4

from app.core import storage
from app.core.errors import AppError
from app.schemas import ClipRequest
from app.services import media


def list_clips(video_id: str):
    storage.video_file(video_id)
    return {
        "clips": [
            clip
            for _, batch in storage.clip_batches()
            if batch.get("video_id") == video_id
            for clip in batch["clips"]
            if isinstance(clip, dict)
        ]
    }


def delete_clip(video_id: str, clip_id: str):
    storage.video_file(video_id)
    clip_path = storage.video_file(clip_id)
    for path, batch in storage.clip_batches():
        if batch.get("video_id") != video_id:
            continue
        clips = batch["clips"]
        matching = [
            c
            for c in clips
            if isinstance(c, dict)
            and c.get("clip_id") == clip_id
            and (c.get("filename") == clip_path.name)
        ]
        if matching:
            batch["clips"] = [c for c in clips if c not in matching]
            batch["total_clips"] = len(batch["clips"])
            path.write_text(json.dumps(batch, indent=2), encoding="utf-8")
            clip_path.unlink()
            return
    raise AppError(404, "Clip not found")


def to_seconds(value: str) -> int:
    """Convertit un temps MM:SS ou HH:MM:SS en secondes."""
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError as exc:
        raise AppError(422, "Invalid time format") from exc
    if len(parts) == 2:
        minutes, seconds = parts
        if minutes < 0 or not 0 <= seconds < 60:
            raise AppError(422, "Invalid time format")
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        if hours < 0 or not 0 <= minutes < 60 or (not 0 <= seconds < 60):
            raise AppError(422, "Invalid time format")
        return hours * 3600 + minutes * 60 + seconds
    raise AppError(422, "Use MM:SS or HH:MM:SS")


def create_clips(video_id: str, request: ClipRequest):
    """Découpe une vidéo et conserve les détails de l'opération en JSON."""
    video_path = storage.video_file(video_id)
    try:
        probe = media.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        video_duration = float(json.loads(probe.stdout)["format"]["duration"])
    except FileNotFoundError as exc:
        raise AppError(503, "FFprobe is not installed or not in PATH") from exc
    except (subprocess.CalledProcessError, ValueError, KeyError) as exc:
        raise AppError(422, "Unable to read video duration") from exc
    segments = []
    for clip in request.clips:
        start_seconds = to_seconds(clip.start)
        end_seconds = to_seconds(clip.end)
        if end_seconds <= start_seconds or end_seconds > video_duration:
            raise AppError(422, "Invalid clip interval")
        segments.append((clip, start_seconds, end_seconds))
    generated_clips = []
    created_paths = []
    metadata_path = storage.ROOT / f"{uuid4().hex}_clips.json"
    try:
        for clip, start_seconds, end_seconds in segments:
            clip_id = uuid4().hex
            destination = storage.ROOT / f"{clip_id}.mp4"
            created_paths.append(destination)
            media.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-ss",
                    str(start_seconds),
                    "-i",
                    str(video_path),
                    "-t",
                    str(end_seconds - start_seconds),
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    str(destination),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            generated_clips.append(
                {
                    "clip_id": clip_id,
                    "filename": destination.name,
                    "start": clip.start,
                    "end": clip.end,
                }
            )
        metadata = {
            "batch_id": metadata_path.name.removesuffix("_clips.json"),
            "video_id": video_id,
            "total_clips": len(generated_clips),
            "clips": generated_clips,
        }
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)
    except (OSError, subprocess.CalledProcessError) as exc:
        for path in [*created_paths, metadata_path]:
            path.unlink(missing_ok=True)
        raise AppError(500, "Unable to create clips") from exc
    return metadata
