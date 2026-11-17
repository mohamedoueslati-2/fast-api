import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.errors import AppError
from app.main import app
from app.services.clips import to_seconds


def test_time_conversion():
    assert to_seconds("05:30") == 330
    assert to_seconds("01:20:00") == 4800
    with pytest.raises(AppError):
        to_seconds("01:60")


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required",
)
def test_clips_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    video_id = "a" * 32
    video = tmp_path / f"{video_id}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10:d=3",
            "-c:v",
            "libx264",
            str(video),
        ],
        check=True,
    )
    with TestClient(app) as client:
        invalid = client.post(
            f"/videos/{video_id}/clips",
            json={"clips": [{"start": "00:02", "end": "00:04"}]},
        )
        assert invalid.status_code == 422
        assert list(tmp_path.glob("*_clips.json")) == []
        response = client.post(
            f"/videos/{video_id}/clips",
            json={
                "clips": [
                    {"start": "00:00", "end": "00:01"},
                    {"start": "00:01", "end": "00:02"},
                ]
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["total_clips"] == 2
    assert (
        json.loads(
            (tmp_path / f"{data['batch_id']}_clips.json").read_text(encoding="utf-8")
        )
        == data
    )
    for clip in data["clips"]:
        assert (tmp_path / clip["filename"]).is_file()
