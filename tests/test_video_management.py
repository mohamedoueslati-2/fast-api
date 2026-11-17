import json

from fastapi.testclient import TestClient

from app.core import storage
from app.main import app


def test_video_and_clip_management(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    video_id = "a" * 32
    clip_id = "b" * 32
    batch_id = "c" * 32
    (tmp_path / f"{video_id}.mp4").write_bytes(b"video")
    (tmp_path / f"{clip_id}.mp4").write_bytes(b"clip")
    metadata = {
        "batch_id": batch_id,
        "video_id": video_id,
        "total_clips": 1,
        "clips": [
            {
                "clip_id": clip_id,
                "filename": f"{clip_id}.mp4",
                "start": "00:00",
                "end": "00:01",
            }
        ],
    }
    metadata_path = tmp_path / f"{batch_id}_clips.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with TestClient(app) as client:
        assert client.get("/videos").json() == {
            "videos": [{"video_id": video_id, "filename": f"{video_id}.mp4"}]
        }
        assert client.get(f"/videos/{video_id}").content == b"video"
        assert (
            client.get(f"/videos/{video_id}/clips").json()["clips"] == metadata["clips"]
        )
        assert client.delete(f"/videos/{clip_id}").status_code == 404
        assert client.delete(f"/videos/{video_id}/clips/{clip_id}").status_code == 204
        assert not (tmp_path / f"{clip_id}.mp4").exists()
        assert json.loads(metadata_path.read_text(encoding="utf-8"))["total_clips"] == 0
        assert client.delete(f"/videos/{video_id}").status_code == 204
        assert not metadata_path.exists()
        assert client.get(f"/videos/{video_id}").status_code == 404
