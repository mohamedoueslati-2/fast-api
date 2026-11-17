import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.main import app


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_audio_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    source_id = "a" * 32
    source = tmp_path / f"{source_id}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )
    with TestClient(app) as client:
        for fmt in ("mp3", "wav"):
            response = client.post(f"/videos/{source_id}/audio", json={"format": fmt})
            assert response.status_code == 201
            result = response.json()
            assert result["source_id"] == source_id
            assert (tmp_path / result["filename"]).stat().st_size > 0
            assert client.get(result["url"]).status_code == 200
        assert (
            client.post(
                f"/videos/{source_id}/audio", json={"format": "ogg"}
            ).status_code
            == 422
        )
        assert (
            client.post(f"/videos/{'b' * 32}/audio", json={"format": "mp3"}).status_code
            == 404
        )


def test_audio_rejects_video_without_audio(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is required")
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    source_id = "c" * 32
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:d=1",
            "-c:v",
            "libx264",
            str(tmp_path / f"{source_id}.mp4"),
        ],
        check=True,
    )
    with TestClient(app) as client:
        assert (
            client.post(
                f"/videos/{source_id}/audio", json={"format": "wav"}
            ).status_code
            == 422
        )
    assert not list(tmp_path.glob("*.wav"))
