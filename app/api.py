import json
import subprocess
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.schemas import AudioRequest, ClipRequest

app = FastAPI(title="FastAPI Backend", version="0.1.0")

# Dans Docker, /data est monté sur le dossier storage/ du projet.
STORAGE = Path("/data") if Path("/data").is_dir() else Path("storage")
STORAGE.mkdir(parents=True, exist_ok=True)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/health")
def health_check():
    """Vérifie que l'API répond."""
    return {"status": "ok"}


@app.get("/files")
def list_files():
    """Liste les fichiers présents dans le dossier de stockage."""
    return {"files": sorted(path.name for path in STORAGE.iterdir() if path.is_file())}


@app.get("/files/{filename}")
def get_file(filename: str):
    """Permet de lire un fichier du dossier de stockage."""
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise HTTPException(404, "File not found")
    path = STORAGE / filename
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


def clip_batches():
    """Charge les métadonnées des découpages existants."""
    batches = []
    for path in STORAGE.glob("*_clips.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("clips"), list):
                batches.append((path, data))
        except (OSError, ValueError):
            continue
    return batches


def video_file(video_id: str) -> Path:
    if len(video_id) != 32 or any(c not in "0123456789abcdef" for c in video_id):
        raise HTTPException(404, "Video not found")
    path = STORAGE / f"{video_id}.mp4"
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "Video not found")
    return path


@app.get("/videos")
def list_videos():
    """Liste les vidéos originales, sans mélanger leurs extraits."""
    clip_names = {
        clip.get("filename")
        for _, batch in clip_batches()
        for clip in batch["clips"]
        if isinstance(clip, dict)
    }
    videos = []
    for path in sorted(STORAGE.glob("*.mp4")):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.name not in clip_names
            and len(path.stem) == 32
            and all(c in "0123456789abcdef" for c in path.stem)
        ):
            videos.append({"video_id": path.stem, "filename": path.name})
    return {"videos": videos}


@app.get("/videos/{video_id}")
def read_video(video_id: str):
    return FileResponse(video_file(video_id), media_type="video/mp4")


@app.get("/videos/{video_id}/clips")
def list_clips(video_id: str):
    video_file(video_id)
    return {
        "clips": [
            clip
            for _, batch in clip_batches()
            if batch.get("video_id") == video_id
            for clip in batch["clips"]
            if isinstance(clip, dict)
        ]
    }


@app.delete("/videos/{video_id}/clips/{clip_id}", status_code=204)
def delete_clip(video_id: str, clip_id: str):
    video_file(video_id)
    clip_path = video_file(clip_id)
    for path, batch in clip_batches():
        if batch.get("video_id") != video_id:
            continue
        clips = batch["clips"]
        matching = [
            c
            for c in clips
            if isinstance(c, dict)
            and c.get("clip_id") == clip_id
            and c.get("filename") == clip_path.name
        ]
        if matching:
            batch["clips"] = [c for c in clips if c not in matching]
            batch["total_clips"] = len(batch["clips"])
            path.write_text(json.dumps(batch, indent=2), encoding="utf-8")
            clip_path.unlink()
            return Response(status_code=204)
    raise HTTPException(404, "Clip not found")


@app.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: str):
    path = video_file(video_id)
    if not any(video["video_id"] == video_id for video in list_videos()["videos"]):
        raise HTTPException(404, "Video not found")
    # Éviter les fichiers orphelins : supprimer d'abord les extraits associés.
    for metadata_path, batch in clip_batches():
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
                    (STORAGE / f"{clip_id}.mp4").unlink(missing_ok=True)
        metadata_path.unlink()
    path.unlink()
    return Response(status_code=204)


@app.post("/videos", status_code=201)
async def upload_video(file: Annotated[UploadFile, File()]):
    """Enregistre un fichier MP4 et renvoie son identifiant."""
    # Pour l'instant, seule l'extension est vérifiée, pas le contenu vidéo.
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(400, "Only MP4 files are allowed")

    # Un identifiant unique évite d'utiliser le nom fourni par le client.
    video_id = uuid4().hex
    destination = STORAGE / f"{video_id}.mp4"
    try:
        with destination.open("wb") as output:
            # Lire par blocs de 1 Mo évite de charger toute la vidéo en mémoire.
            while chunk := await file.read(1024 * 1024):
                output.write(chunk)
    finally:
        # Fermer le fichier reçu, même si son enregistrement échoue.
        await file.close()

    return {"video_id": video_id, "filename": destination.name}


@app.post("/videos/{video_id}/frames", status_code=201)
def extract_frames(video_id: str):
    """Enregistre une image pour chaque changement de scène détecté."""
    source = video_file(video_id)
    batch_id = uuid4().hex
    directory = STORAGE / f"frames_{batch_id}"
    directory.mkdir()
    try:
        subprocess.run(
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
            raise HTTPException(503, "FFmpeg is not installed or not in PATH") from exc
        raise HTTPException(422, "Unable to extract frames from this video") from exc
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


@app.get("/videos/{video_id}/frames")
def list_frames(video_id: str):
    video_file(video_id)
    batches = []
    for directory in sorted(STORAGE.glob("frames_*")):
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            data = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("source_id") == video_id:
                batches.append(data)
        except (OSError, ValueError):
            continue
    return {"batches": batches}


@app.get("/frames/{batch_id}/{filename}")
def read_frame(batch_id: str, filename: str):
    if (
        len(batch_id) != 32
        or any(c not in "0123456789abcdef" for c in batch_id)
        or not filename.startswith("frame_")
        or not filename.endswith(".jpg")
        or not filename[6:-4].isdigit()
    ):
        raise HTTPException(404, "Frame not found")
    directory = STORAGE / f"frames_{batch_id}"
    path = directory / filename
    if directory.is_symlink() or path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Frame not found")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/frames/{batch_id}/{filename}", status_code=204)
def delete_frame(batch_id: str, filename: str):
    """Supprime une capture et met à jour les métadonnées de son lot."""
    read_frame(batch_id, filename)
    directory = STORAGE / f"frames_{batch_id}"
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
            raise HTTPException(404, "Frame not found in metadata")
        metadata["frames"] = remaining
        metadata["total_frames"] = len(remaining)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (directory / filename).unlink()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(500, "Unable to delete frame") from exc
    return Response(status_code=204)


@app.post("/videos/{video_id}/audio", status_code=201)
def extract_audio(video_id: str, request: AudioRequest):
    """Extrait l'audio d'une vidéo originale ou d'un extrait."""
    source = video_file(video_id)
    audio_id = uuid4().hex
    destination = STORAGE / f"{audio_id}.{request.format}"
    codec = "libmp3lame" if request.format == "mp3" else "pcm_s16le"
    try:
        subprocess.run(
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
        raise HTTPException(503, "FFmpeg is not installed or not in PATH") from exc
    except subprocess.CalledProcessError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            422, "Unable to extract audio; check that the video has an audio track"
        ) from exc
    return {
        "audio_id": audio_id,
        "source_id": video_id,
        "format": request.format,
        "filename": destination.name,
        "url": f"/files/{destination.name}",
    }


def to_seconds(value: str) -> int:
    """Convertit un temps MM:SS ou HH:MM:SS en secondes."""
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError as exc:
        raise HTTPException(422, "Invalid time format") from exc
    if len(parts) == 2:
        minutes, seconds = parts
        if minutes < 0 or not 0 <= seconds < 60:
            raise HTTPException(422, "Invalid time format")
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            raise HTTPException(422, "Invalid time format")
        return hours * 3600 + minutes * 60 + seconds
    raise HTTPException(422, "Use MM:SS or HH:MM:SS")


@app.post("/videos/{video_id}/clips", status_code=201)
def create_clips(video_id: str, request: ClipRequest):
    """Découpe une vidéo et conserve les détails de l'opération en JSON."""
    if len(video_id) != 32 or any(c not in "0123456789abcdef" for c in video_id):
        raise HTTPException(404, "Video not found")
    video_path = STORAGE / f"{video_id}.mp4"
    if not video_path.is_file():
        raise HTTPException(404, "Video not found")

    try:
        probe = subprocess.run(
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
        raise HTTPException(503, "FFprobe is not installed or not in PATH") from exc
    except (subprocess.CalledProcessError, ValueError, KeyError) as exc:
        raise HTTPException(422, "Unable to read video duration") from exc

    # Valider tous les intervalles avant de créer le moindre extrait.
    segments = []
    for clip in request.clips:
        start_seconds = to_seconds(clip.start)
        end_seconds = to_seconds(clip.end)
        if end_seconds <= start_seconds or end_seconds > video_duration:
            raise HTTPException(422, "Invalid clip interval")
        segments.append((clip, start_seconds, end_seconds))

    generated_clips = []
    created_paths = []
    metadata_path = STORAGE / f"{uuid4().hex}_clips.json"
    try:
        for clip, start_seconds, end_seconds in segments:
            clip_id = uuid4().hex
            destination = STORAGE / f"{clip_id}.mp4"
            created_paths.append(destination)
            subprocess.run(
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
        raise HTTPException(500, "Unable to create clips") from exc
    return metadata
