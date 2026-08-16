import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from app.features.literature.llm_service import LiteratureLLMService
from app.features.literature.schemas import ClusterInfo
from app.shared.id_utils import generate_id

# In-memory build jobs, mirroring the graph generation pattern. Each entry
# tracks a background thread's progress so the frontend can poll for status
# while a literature map is being (re)built.
_jobs: dict = {}
_jobs_lock = threading.Lock()


def start_build(
    service_factory: Callable[[], object],
    user_id: str,
    project_id: str,
) -> str:
    """Starts a background literature map build for the project.

    Only one build may run per project at a time. If one is already running,
    ``rebuild_pending`` is set so the worker re-runs as soon as it finishes
    (papers that arrived mid-build are picked up). `service_factory` must hand
    back a fresh `LiteratureService` (with its own DB connection) for use
    inside the thread.
    """
    with _jobs_lock:
        for job in _jobs.values():
            if (
                job["status"] == "running"
                and job["user_id"] == user_id
                and job["project_id"] == project_id
            ):
                job["rebuild_pending"] = True
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
            "error": None,
        }
    thread = threading.Thread(
        target=_run,
        args=(job_id, service_factory, user_id, project_id),
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
        return {
            k: v
            for k, v in job.items()
            if not k.startswith("_") and k not in ("user_id", "project_id", "rebuild_pending")
        }


def wait_for_job(job_id: str, timeout: float = 15.0) -> Optional[dict]:
    """Blocks until the job's thread finishes, then returns its final state."""
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


def _run(job_id: str, service_factory: Callable[[], object], user_id: str, project_id: str) -> None:
    service = service_factory()
    try:
        def on_progress(percent: int, stage: str) -> None:
            _update(job_id, progress=int(percent), stage=stage)

        response = service.build_map(user_id, project_id, on_progress=on_progress)
        fingerprint = json.dumps(sorted(n.id for n in response.nodes))

        if response.nodes:
            _update(job_id, progress=84, stage="Summarizing papers")
            llm = LiteratureLLMService(service.db)
            llm.summarize_papers(
                user_id,
                project_id,
                on_paper=lambda done, total: _update(
                    job_id,
                    progress=84 + int(done / max(total, 1) * 4),
                    stage="Summarizing papers",
                ),
            )

            _update(job_id, progress=88, stage="Labelling clusters")
            inputs = [
                {
                    "id": cluster.id,
                    "titles": [n.label for n in response.nodes if n.cluster == cluster.id],
                }
                for cluster in response.clusters
            ]
            labeled = asyncio.run(llm.label_clusters(user_id, project_id, inputs))
            by_id = {item["id"]: item for item in labeled}
            response.clusters = [
                ClusterInfo(
                    id=cluster.id,
                    label=by_id.get(cluster.id, {}).get("label") or cluster.label,
                    summary=by_id.get(cluster.id, {}).get("summary") or cluster.summary,
                    size=cluster.size,
                )
                for cluster in response.clusters
            ]

        _update(job_id, progress=92, stage="Saving checkpoint")
        response.generated_at = datetime.now(timezone.utc).isoformat()
        service.save_checkpoint(user_id, project_id, response, fingerprint)
        _update(job_id, progress=100, status="done", stage="Done")
    except Exception as exc:  # noqa: BLE001 - surfaced to the frontend
        _update(job_id, status="error", error=str(exc))
    finally:
        with _jobs_lock:
            job = _jobs.get(job_id)
            pending = bool(job and job.pop("rebuild_pending", False))
        service.db.close()
        if pending:
            start_build(service_factory, user_id, project_id)
