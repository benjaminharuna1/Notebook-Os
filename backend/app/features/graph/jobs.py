import json
import threading
from typing import Callable, List, Optional

from app.features.actions import registry as actions
from app.features.graph.builder import layout_nodes
from app.features.graph.schemas import GraphEdge, GraphNode, GraphResponse
from app.features.graph.service import _BUILD_CACHE, _build_key, _fingerprint

# Graph generations are background *actions* tracked in the shared actions
# registry, so they can be paused/resumed from anywhere and are limited by the
# user's ``max_concurrent_actions`` setting.
KIND = "graph"


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
    existing = actions.find_active(user_id, project_id, KIND)
    if existing:
        return existing

    job_id = actions.register(user_id, project_id, KIND, "Knowledge graph")
    thread = threading.Thread(
        target=_run,
        args=(job_id, service_factory, user_id, project_id, document_ids or [], depth, force),
        daemon=True,
    )
    actions.set_thread(job_id, thread)
    thread.start()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return actions.get(job_id)


def wait_for_job(job_id: str, timeout: float = 10.0) -> Optional[dict]:
    """Blocks until the job's thread finishes, then returns its final state."""
    return actions.join(job_id, timeout)


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
        actions.wait_for_slot(
            job_id, user_id, lambda: actions.configured_limit(service.db, user_id)
        )

        actions.update(job_id, progress=5, stage="Loading documents")
        doc_ids = service._documents_for_graph(user_id, project_id, document_ids)
        if not doc_ids:
            response = GraphResponse(nodes=[], edges=[])
            checkpoint = service._save_checkpoint(user_id, project_id, response, "", "[]")
            actions.update(job_id, progress=100, status="done", stage="Done", checkpoint=checkpoint)
            return

        actions.update(job_id, progress=15, stage="Loading chunks")
        chunks = service._chunks_for(doc_ids)
        preferences = service._tracked_preferences(user_id, project_id)
        total = len(chunks) or 1

        def on_progress(done: int, _total: int) -> None:
            actions.checkpoint(job_id)
            frac = 20 + (done / total) * 55
            actions.update(job_id, progress=int(frac), stage="Extracting concepts")

        actions.update(job_id, progress=20, stage="Extracting concepts")
        nodes, edges = service.builder.build(chunks, preferences, on_progress=on_progress)

        actions.update(job_id, progress=80, stage="Computing layout")
        actions.checkpoint(job_id)
        nodes = layout_nodes(nodes, edges)

        actions.update(job_id, progress=90, stage="Saving checkpoint")
        actions.checkpoint(job_id)
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

        actions.update(job_id, progress=100, status="done", stage="Done", checkpoint=checkpoint)
    except Exception as exc:  # noqa: BLE001 - surfaced to the frontend
        actions.update(job_id, status="error", error=str(exc))
    finally:
        service.db.close()
