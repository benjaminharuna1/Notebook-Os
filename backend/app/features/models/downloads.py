"""Background model downloads from HuggingFace Hub.

Files are pulled into LOCAL_MODELS_DIR so the local (llama.cpp) providers can
load them by filename. Progress is tracked in a module-level registry and
exposed to the frontend for dropdown progress bars.
"""

import os
import threading

from app.core.config import settings
from app.features.models.catalog import HF_BY_KEY
from app.shared.logger import logger

_REGISTRY = {}
_REGISTRY_LOCK = threading.Lock()
_ACTIVE = set()


def _models_dir() -> str:
    path = os.path.abspath(settings.LOCAL_MODELS_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def model_installed(key: str) -> bool:
    info = HF_BY_KEY.get(key)
    if not info:
        return False
    return os.path.isfile(os.path.join(_models_dir(), info["filename"]))


def _snapshot(key: str) -> dict:
    return dict(_REGISTRY.get(key, {"status": "idle", "progress": 0, "error": None}))


def get_downloads() -> dict:
    """Status of every catalog model (used by the settings dropdown)."""
    with _REGISTRY_LOCK:
        entries = []
        for key in HF_BY_KEY:
            info = HF_BY_KEY[key]
            status = dict(_REGISTRY.get(key, {}))
            status.pop("dest", None)
            entries.append({
                "key": key,
                "name": info["name"],
                "kind": info["kind"],
                "tier": info["tier"],
                "size_label": info["size_label"],
                "note": info["note"],
                "downloaded": model_installed(key),
                "status": status.get("status", "idle"),
                "progress": status.get("progress", 0),
                "downloaded_bytes": status.get("downloaded", 0),
                "total_bytes": status.get("total", 0),
                "error": status.get("error"),
            })
    return {"downloads": entries}


def start_download(key: str) -> dict:
    info = HF_BY_KEY.get(key)
    if not info:
        raise ValueError(f"Unknown model to download: {key}")

    with _REGISTRY_LOCK:
        if key in _ACTIVE:
            return _snapshot(key)
        if model_installed(key):
            _REGISTRY[key] = {"status": "done", "progress": 100, "error": None}
            return _snapshot(key)

        _REGISTRY[key] = {"status": "downloading", "progress": 0, "error": None}
        _ACTIVE.add(key)

    thread = threading.Thread(target=_worker, args=(key,), daemon=True)
    thread.start()
    return _snapshot(key)


def _worker(key: str):
    info = HF_BY_KEY[key]
    state = _REGISTRY[key]
    dest = os.path.join(_models_dir(), info["filename"])
    part = dest + ".part"
    try:
        import requests

        url = f"https://huggingface.co/{info['repo']}/resolve/main/{info['filename']}"
        logger.info("Downloading model %s from %s", key, info["repo"])

        with requests.get(url, stream=True, timeout=(15, 60), allow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0) or int(
                response.headers.get("X-Linked-Size") or 0
            )
            state["total"] = total

            written = 0
            with open(part, "wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    written += len(chunk)
                    state["downloaded"] = written
                    state["progress"] = int(written * 100 / total) if total else 0

        if not os.path.isfile(part):
            raise RuntimeError("Download finished but the GGUF file is missing")
        os.replace(part, dest)
        state["status"] = "done"
        state["progress"] = 100
        logger.info("Downloaded model %s", key)
    except Exception as exc:  # surface the failure to the UI
        logger.error("Failed to download model %s: %s", key, exc)
        state["status"] = "error"
        state["error"] = str(exc)
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass
        _ACTIVE.discard(key)
