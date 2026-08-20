"""Background model downloads from HuggingFace Hub.

Files are pulled into LOCAL_MODELS_DIR so the local (llama.cpp) providers can
load them by filename. Progress is tracked in a module-level registry and
exposed to the frontend for dropdown progress bars.
"""

import os
import threading

from app.core.config import settings
from app.features.models.catalog import (
    HF_BY_KEY,
    load_custom_models,
    parse_hf_url,
    estimate_ram_gb,
    make_custom_model_key,
    register_custom_model,
    get_all_hf_models,
)
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
        info = {m["key"]: m for m in load_custom_models()}.get(key)
    if not info:
        return False
    return os.path.isfile(os.path.join(_models_dir(), info["filename"]))


def _snapshot(key: str) -> dict:
    return dict(_REGISTRY.get(key, {"status": "idle", "progress": 0, "error": None}))


def get_downloads() -> dict:
    """Status of every catalog + custom model (used by the settings dropdown)."""
    with _REGISTRY_LOCK:
        entries = []
        all_models = get_all_hf_models()
        for key, info in all_models.items():
            status = dict(_REGISTRY.get(key, {}))
            status.pop("dest", None)
            is_custom = key.startswith("custom_")
            entries.append({
                "key": key,
                "name": info["name"],
                "kind": info["kind"],
                "tier": info.get("tier", "custom"),
                "size_label": info.get("size_label", ""),
                "note": info.get("note", ""),
                "downloaded": model_installed(key),
                "status": status.get("status", "idle"),
                "progress": status.get("progress", 0),
                "downloaded_bytes": status.get("downloaded", 0),
                "total_bytes": status.get("total", 0),
                "error": status.get("error"),
                "custom": is_custom,
                "url": info.get("url", ""),
                "ram_estimate_gb": info.get("ram_estimate_gb"),
            })
    return {"downloads": entries}


def start_download(key: str) -> dict:
    all_models = get_all_hf_models()
    info = all_models.get(key)
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


def start_custom_download(url: str, name: str | None = None) -> dict:
    """Download an arbitrary GGUF model from a HuggingFace URL."""
    parsed = parse_hf_url(url)
    if not parsed:
        raise ValueError(
            "Invalid HuggingFace URL. Expected format:\n"
            "https://huggingface.co/{owner}/{repo}/resolve/main/{filename}.gguf"
        )

    filename = parsed["filename"]
    if not filename.lower().endswith(".gguf"):
        raise ValueError("Only .gguf files are supported")

    key = make_custom_model_key(filename)

    # Register the custom model entry
    entry = {
        "key": key,
        "name": name or filename.replace(".gguf", "").replace("-", " ").title(),
        "kind": "chat",
        "tier": "custom",
        "repo": parsed["repo"],
        "filename": filename,
        "size_label": "",
        "note": f"Custom model from {parsed['repo']}",
        "url": url,
    }

    # Try to fetch file size for RAM estimate
    try:
        import requests as _requests
        head = _requests.head(url, timeout=10, allow_redirects=True)
        total = int(head.headers.get("Content-Length") or 0)
        if total > 0:
            entry["size_label"] = _format_size(total)
            entry["ram_estimate_gb"] = estimate_ram_gb(total, filename)
    except Exception:
        pass

    register_custom_model(entry)
    return start_download(key)


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"~{size_bytes:.0f} {unit}" if unit == "B" else f"~{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"~{size_bytes:.1f} TB"


def _worker(key: str):
    all_models = get_all_hf_models()
    info = all_models[key]
    state = _REGISTRY[key]
    dest = os.path.join(_models_dir(), info["filename"])
    part = dest + ".part"
    try:
        import requests

        url = info.get("url") or f"https://huggingface.co/{info['repo']}/resolve/main/{info['filename']}"
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
