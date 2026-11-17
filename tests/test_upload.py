from fastapi.testclient import TestClient

from app import api as main


def test_upload_video(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    with TestClient(main.app) as client:
        response = client.post(
            "/videos", files={"file": ("video.MP4", b"video content", "video/mp4")}
        )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == f"{data['video_id']}.mp4"
    assert (tmp_path / data["filename"]).read_bytes() == b"video content"


def test_upload_rejects_other_extensions(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    with TestClient(main.app) as client:
        response = client.post("/videos", files={"file": ("video.txt", b"content")})

    assert response.status_code == 400
    assert response.json() == {"detail": "Only MP4 files are allowed"}
    assert list(tmp_path.iterdir()) == []
