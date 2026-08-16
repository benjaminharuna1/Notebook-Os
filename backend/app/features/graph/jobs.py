import json
import threading
import time
from typing import Callable, List, Optional

from app.features.graph.builder import layout_nodes
from app.features.graph.schemas import GraphEdge, GraphNode, GraphResponse
from app.features.graph.service import _BUILD_CACHE, _build_key, _fingerprint
from app.shared.id_utils import generate_id

# In-memory generation jobs. Each entry tracks a background thread's progress
# so the frontend can poll for status while a graph is being (re)generated.
_jobs: dict = {}
_jobs_lock = threading.Lock()


def start_generation(
    service_factory: Callable[[], object],
    user_id: str,
    project_id: str,
    document_ids: Optional[List[str]] = None,
    depth: int = 2,
    force: bool = True,
) -> str:
    """Starts a background generation for the project.

    Only one generation may run per project at a time; starting another
    returns the in-flight job id. `service_factory` must hand back a fresh
    `GraphService` (with its own DB connection) for use inside the thread.
    """
    with _jobs_lock:
        for job in _jobs.values():
            if (
                job["status"] == "running"
                and job["user_id"] == user_id
                and job["project_id"] == project_id
            ):
                return job["id"]

    job_id = generate_id()
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "user_id": user_id,
            "project_id": project_id,
            "status": "running",
            "progress": 0,
            "stage": "Starting",
            "checkpoint": None,
            "error": None,
        }
    thread = threading.Thread(
        target=_run,
        args=(job_id, service_factory, user_id, project_id, document_ids or [], depth, force),
        daemon=True,
    )
    with _jobs_lock:
        _jobs[job_id]["_thread"] = thread
    thread.start()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        return {k: v for k, v in job.items() if not k.startswith("_") and k not in ("user_id", "project_id")}


def wait_for_job(job_id: str, timeout: float = 10.0) -> Optional[dict]:
    """Blocks until the job's thread finishes, then returns its final state.

    Useful for tests (and any caller that wants the result synchronously)
    without racing the background thread's connection teardown.
    """
    deadline = time.monotonic() + timeout
    with _jobs_lock:
        thread = _jobs[job_id].get("_thread") if job_id in _jobs else None
    if thread is not None:
        thread.join(max(0.0, deadline - time.monotonic()))
    return get_job(job_id)


def _update(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _run(
    job_id: str,
    service_factory: Callable[[], object],
    user_id: str,
    project_id: str,
    document_ids: List[str],
    depth: int,
    force: bool,
) -> None:
    service = service_factory()
    try:
        _update(job_id, progress=5, stage="Loading documents")
        doc_ids = service._documents_for_graph(user_id, project_id, document_ids)
        if not doc_ids:
            response = GraphResponse(nodes=[], edges=[])
            checkpoint = service._save_checkpoint(user_id, project_id, response, "", "[]")
            _update(job_id, progress=100, status="done", stage="Done", checkpoint=checkpoint)
            return

        _update(job_id, progress=15, stage="Loading chunks")
        chunks = service._chunks_for(doc_ids)
        preferences = service._tracked_preferences(user_id, project_id)
        total = len(chunks) or 1

        def on_progress(done: int, _total: int) -> None:
            frac = 20 + (done / total) * 55
            _update(job_id, progress=int(frac), stage="Extracting concepts")

        _update(job_id, progress=20, stage="Extracting concepts")
        nodes, edges = service.builder.build(chunks, preferences, on_progress=on_progress)

        _update(job_id, progress=80, stage="Computing layout")
        nodes = layout_nodes(nodes, edges)

        _update(job_id, progress=90, stage="Saving checkpoint")
        response = GraphResponse(
            nodes=[GraphNode(**node) for node in nodes],
            edges=[GraphEdge(**edge) for edge in edges],
        )
        fingerprint = _fingerprint(chunks)
        prefs_key = json.dumps(sorted(preferences))
        checkpoint = service._save_checkpoint(user_id, project_id, response, fingerprint, prefs_key)

        key = _build_key(user_id, project_id, doc_ids, depth, preferences, chunks)
        if len(_BUILD_CACHE) >= 32:
            _BUILD_CACHE.clear()
        _BUILD_CACHE[key] = response

        _update(job_id, progress=100, status="done", stage="Done", checkpoint=checkpoint)
    except Exception as exc:  # noqa: BLE001 - surfaced to the frontend
        _update(job_id, status="error", error=str(exc))
    finally:
        service.db.close()
