"""Global in-memory registry of long-running background actions.

An action is a background worker (literature map build, graph generation, ...)
that can report progress, be paused/resumed from any page, and is capped by
the user's configured ``max_concurrent_actions`` setting so a lot of parallel
work never overwhelms the machine.

All state lives in process memory (like the old per-feature job dicts) — the
DB is untouched by this module.
"""

import itertools
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from app.shared.id_utils import generate_id

DEFAULT_MAX_CONCURRENT = 2
MAX_ACTIONS_PER_USER = 50

_lock = threading.Lock()
_actions: Dict[str, dict] = {}
_seq = itertools.count()


def register(
    user_id: str,
    project_id: str,
    kind: str,
    title: str,
) -> str:
    """Registers a new action in ``queued`` state and returns its id."""
    action_id = generate_id()
    event = threading.Event()
    event.set()
    with _lock:
        _prune(user_id)
        _actions[action_id] = {
            "id": action_id,
            "user_id": user_id,
            "project_id": project_id,
            "kind": kind,
            "title": title,
            "status": "queued",
            "progress": 0,
            "stage": "Waiting for a slot",
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pause_event": event,
            "_thread": None,
            "_slot_acquired": False,
            "_rebuild_pending": False,
            "_seq": next(_seq),
        }
    return action_id


def get(action_id: str) -> Optional[dict]:
    """Returns the public view of an action, or ``None`` if unknown."""
    with _lock:
        action = _actions.get(action_id)
        if action is None:
            return None
        return _public(action)


def list_for_user(user_id: str) -> List[dict]:
    """Returns all actions for a user, newest first (public view)."""
    with _lock:
        _prune(user_id)
        mine = [a for a in _actions.values() if a["user_id"] == user_id]
    mine.sort(key=lambda a: a["_seq"], reverse=True)
    with _lock:
        return [_public(a) for a in mine]


def update(action_id: str, **kwargs) -> None:
    """Updates progress/status fields on an action (safe to call from workers)."""
    with _lock:
        if action_id in _actions:
            _actions[action_id].update(kwargs)


def set_thread(action_id: str, thread: threading.Thread) -> None:
    update(action_id, _thread=thread)


def get_thread(action_id: str) -> Optional[threading.Thread]:
    with _lock:
        action = _actions.get(action_id)
        return action["_thread"] if action else None


def join(action_id: str, timeout: float = 10.0) -> Optional[dict]:
    """Blocks until the action's worker thread finishes, then returns its state."""
    deadline = time.monotonic() + timeout
    thread = get_thread(action_id)
    if thread is not None:
        thread.join(max(0.0, deadline - time.monotonic()))
    return get(action_id)


def pause(action_id: str, user_id: str) -> Optional[dict]:
    """Pauses an action owned by ``user_id`` (queued or running only)."""
    with _lock:
        action = _actions.get(action_id)
        if action is None or action["user_id"] != user_id:
            return None
        if action["status"] not in ("queued", "running"):
            return None
        action["status"] = "paused"
        action["pause_event"].clear()
        return _public(action)


def resume(action_id: str, user_id: str) -> Optional[dict]:
    """Resumes an action owned by ``user_id`` (paused only)."""
    with _lock:
        action = _actions.get(action_id)
        if action is None or action["user_id"] != user_id:
            return None
        if action["status"] != "paused":
            return None
        action["status"] = "running"
        action["pause_event"].set()
        return _public(action)


def checkpoint(action_id: str) -> None:
    """Blocks the calling worker while the action is paused.

    Called between work stages; returns immediately when the action is not
    paused. A worker that is mid-LLM-call keeps running until the next
    checkpoint — pause is cooperative, not pre-emptive.
    """
    with _lock:
        action = _actions.get(action_id)
        if action is None:
            return
        event = action["pause_event"]
    if not event.is_set():
        event.wait()


def wait_for_slot(action_id: str, user_id: str, limit_provider: Callable[[], int]) -> None:
    """Blocks until fewer than the user's max concurrent actions are running.

    ``limit_provider`` is called fresh on every retry so a user changing the
    Settings concurrency value takes effect without a restart. Queued actions
    that are paused while waiting block until they are resumed.
    """
    while True:
        limit = max(1, int(limit_provider()))
        event = None
        with _lock:
            action = _actions.get(action_id)
            if action is None:
                return
            if action.get("_slot_acquired"):
                return
            running = sum(
                1
                for a in _actions.values()
                if a["user_id"] == user_id
                and a["status"] == "running"
                and a.get("_slot_acquired")
            )
            if running < limit and action["status"] != "paused":
                action["_slot_acquired"] = True
                action["status"] = "running"
                action["stage"] = "Starting"
                return
            if action["status"] == "paused":
                event = action["pause_event"]
        if event is not None:
            event.wait()
        else:
            time.sleep(0.5)


def find_active(user_id: str, project_id: str, kind: str) -> Optional[str]:
    """Returns the id of an in-flight (queued/running/paused) action, if any."""
    with _lock:
        for action in _actions.values():
            if (
                action["user_id"] == user_id
                and action["project_id"] == project_id
                and action["kind"] == kind
                and action["status"] in ("queued", "running", "paused")
            ):
                return action["id"]
    return None


def mark_rebuild_pending(action_id: str) -> None:
    """Flags an in-flight action to re-run once it finishes."""
    with _lock:
        action = _actions.get(action_id)
        if action:
            action["_rebuild_pending"] = True


def pop_rebuild_pending(action_id: str) -> bool:
    """Consumes and returns the rebuild flag (used by workers in ``finally``)."""
    with _lock:
        action = _actions.get(action_id)
        if action:
            return bool(action.pop("_rebuild_pending", False))
    return False


def configured_limit(db, user_id: str) -> int:
    """The user's ``max_concurrent_actions`` setting (default when unset)."""
    try:
        from app.features.settings.service import SettingsService

        settings = SettingsService(db).get_settings(user_id).settings
        value = settings.get("max_concurrent_actions")
        if value is None:
            return DEFAULT_MAX_CONCURRENT
        return max(1, min(int(value), 16))
    except Exception:
        return DEFAULT_MAX_CONCURRENT


def _public(action: dict) -> dict:
    out = {
        "id": action["id"],
        "user_id": action["user_id"],
        "project_id": action["project_id"],
        "kind": action["kind"],
        "title": action["title"],
        "status": action["status"],
        "progress": action["progress"],
        "stage": action["stage"],
        "error": action["error"],
        "created_at": action["created_at"],
    }
    for key, value in action.items():
        if not key.startswith("_") and key not in out and key != "pause_event":
            out[key] = value
    return out


def _prune(user_id: str) -> None:
    mine = [a for a in _actions.values() if a["user_id"] == user_id]
    terminal = [a for a in mine if a["status"] in ("done", "error")]
    terminal.sort(key=lambda a: a["created_at"], reverse=True)
    for action in terminal[MAX_ACTIONS_PER_USER:]:
        _actions.pop(action["id"], None)
