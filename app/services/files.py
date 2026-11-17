"""Files business operations."""

from app.core import storage
from app.core.errors import AppError


def list_files():
    """Liste les fichiers présents dans le dossier de stockage."""
    return {
        "files": sorted(path.name for path in storage.ROOT.iterdir() if path.is_file())
    }


def get_file(filename: str):
    """Permet de lire un fichier du dossier de stockage."""
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise AppError(404, "File not found")
    path = storage.ROOT / filename
    if not path.is_file() or path.is_symlink():
        raise AppError(404, "File not found")
    return path
