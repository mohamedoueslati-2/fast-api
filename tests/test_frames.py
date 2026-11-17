import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import api as main


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_scene_frames(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    video_id = "a" * 32
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=64x64:r=10:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=64x64:r=10:d=1",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v",
            "libx264",
            str(tmp_path / f"{video_id}.mp4"),
        ],
        check=True,
    )
    with TestClient(main.app) as client:
        response = client.post(f"/videos/{video_id}/frames")
        assert response.status_code == 201
        batch = response.json()
        assert batch["total_frames"] >= 1
        frame = client.get(batch["frames"][0]["url"])
        assert frame.status_code == 200
        assert frame.headers["content-type"] == "image/jpeg"
        assert client.get(f"/videos/{video_id}/frames").json()["batches"] == [batch]
        assert client.delete(batch["frames"][0]["url"]).status_code == 204
        assert client.get(batch["frames"][0]["url"]).status_code == 404
        remaining = client.get(f"/videos/{video_id}/frames").json()["batches"][0]
        assert remaining["total_frames"] == batch["total_frames"] - 1
        assert client.delete(batch["frames"][0]["url"]).status_code == 404
        assert client.post(f"/videos/{'b' * 32}/frames").status_code == 404
