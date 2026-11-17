"""Frames business operations."""

import json
import subprocess
from uuid import uuid4

from app.core import storage
from app.core.errors import AppError
from app.services import media


def extract_frames(video_id: str):
    """Enregistre une image pour chaque changement de scène détecté."""
    source = storage.video_file(video_id)
    batch_id = uuid4().hex
    directory = storage.ROOT / f"frames_{batch_id}"
    directory.mkdir()
    try:
        media.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(source),
                "-vf",
                "select='gt(scene,0.3)'",
                "-fps_mode",
                "vfr",
                str(directory / "frame_%05d.jpg"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        for path in directory.iterdir():
            path.unlink()
        directory.rmdir()
        if isinstance(exc, FileNotFoundError):
            raise AppError(503, "FFmpeg is not installed or not in PATH") from exc
        raise AppError(422, "Unable to extract frames from this video") from exc
    frames = sorted(path.name for path in directory.glob("frame_*.jpg"))
    result = {
        "batch_id": batch_id,
        "source_id": video_id,
        "total_frames": len(frames),
        "frames": [
            {"filename": name, "url": f"/frames/{batch_id}/{name}"} for name in frames
        ],
    }
    (directory / "metadata.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def list_frames(video_id: str):
    storage.video_file(video_id)
    batches = []
    for directory in sorted(storage.ROOT.glob("frames_*")):
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            data = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("source_id") == video_id:
                batches.append(data)
        except (OSError, ValueError):
            continue
    return {"batches": batches}


def read_frame(batch_id: str, filename: str):
    if (
        len(batch_id) != 32
        or any(c not in "0123456789abcdef" for c in batch_id)
        or (not filename.startswith("frame_"))
        or (not filename.endswith(".jpg"))
        or (not filename[6:-4].isdigit())
    ):
        raise AppError(404, "Frame not found")
    directory = storage.ROOT / f"frames_{batch_id}"
    path = directory / filename
    if directory.is_symlink() or path.is_symlink() or (not path.is_file()):
        raise AppError(404, "Frame not found")
    return path


def delete_frame(batch_id: str, filename: str):
    """Supprime une capture et met à jour les métadonnées de son lot."""
    read_frame(batch_id, filename)
    directory = storage.ROOT / f"frames_{batch_id}"
    metadata_path = directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        frames = metadata["frames"]
        if not isinstance(frames, list):
            raise TypeError("Invalid metadata")
        remaining = [
            frame
            for frame in frames
            if isinstance(frame, dict) and frame.get("filename") != filename
        ]
        if len(remaining) == len(frames):
            raise AppError(404, "Frame not found in metadata")
        metadata["frames"] = remaining
        metadata["total_frames"] = len(remaining)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (directory / filename).unlink()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AppError(500, "Unable to delete frame") from exc
