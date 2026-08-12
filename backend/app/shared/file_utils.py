import mimetypes
from pathlib import Path


def get_mime_type(file_path: str) -> str:
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


def get_file_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower()


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
