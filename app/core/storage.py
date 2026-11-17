"""Local storage configuration and shared file lookups."""

import json
import os
from pathlib import Path

from app.core.errors import AppError

ROOT = Path(
    os.environ.get("VIDEO_STORAGE_DIR", Path(__file__).resolve().parents[2] / "storage")
)
ROOT.mkdir(parents=True, exist_ok=True)


def clip_batches():
    """Charge les métadonnées des découpages existants."""
    batches = []
    for path in ROOT.glob("*_clips.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("clips"), list):
                batches.append((path, data))
        except (OSError, ValueError):
            continue
    return batches


def video_file(video_id: str) -> Path:
    if len(video_id) != 32 or any(c not in "0123456789abcdef" for c in video_id):
        raise AppError(404, "Video not found")
    path = ROOT / f"{video_id}.mp4"
    if not path.is_file() or path.is_symlink():
        raise AppError(404, "Video not found")
    return path
