import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from app.features.actions import registry as actions
from app.features.literature.llm_service import LiteratureLLMService
from app.features.literature.schemas import ClusterInfo

# Literature map builds are background *actions* tracked in the shared actions
# registry, so they can be paused/resumed from anywhere and are limited by the
# user's ``max_concurrent_actions`` setting. These helpers keep the same
# signatures used by the routers/tests.
KIND = "literature"


def start_build(
    service_factory: Callable[[], object],
    user_id: str,
    project_id: str,
) -> str:
    """Starts a background literature map build for the project.

    Only one build may run per project at a time. If one is already in flight
    (queued/running/paused), ``rebuild_pending`` is set so the worker re-runs
    as soon as it finishes (papers that arrived mid-build are picked up).
    `service_factory` must hand back a fresh `LiteratureService` (with its own
    DB connection) for use inside the thread.
    """
    existing = actions.find_active(user_id, project_id, KIND)
    if existing:
        actions.mark_rebuild_pending(existing)
        return existing

    job_id = actions.register(user_id, project_id, KIND, "Literature map")
    thread = threading.Thread(
        target=_run,
        args=(job_id, service_factory, user_id, project_id),
        daemon=True,
    )
    actions.set_thread(job_id, thread)
    thread.start()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return actions.get(job_id)


def wait_for_job(job_id: str, timeout: float = 15.0) -> Optional[dict]:
    """Blocks until the job's thread finishes, then returns its final state."""
    return actions.join(job_id, timeout)


def _run(job_id: str, service_factory: Callable[[], object], user_id: str, project_id: str) -> None:
    service = service_factory()
    try:
        actions.wait_for_slot(
            job_id, user_id, lambda: actions.configured_limit(service.db, user_id)
        )

        def on_progress(percent: int, stage: str) -> None:
            actions.checkpoint(job_id)
            actions.update(job_id, progress=int(percent), stage=stage)

        response = service.build_map(user_id, project_id, on_progress=on_progress)
        fingerprint = json.dumps(sorted(n.id for n in response.nodes))

        if response.nodes:
            actions.update(job_id, progress=84, stage="Summarizing papers")
            llm = LiteratureLLMService(service.db)
            if not llm.active_model(user_id):
                actions.update(
                    job_id,
                    stage="Summarizing papers (LLM unavailable — using abstracts)",
                )
            llm.summarize_papers(
                user_id,
                project_id,
                on_paper=lambda done, total: _on_summarize_progress(job_id, done, total),
            )

            actions.update(job_id, progress=88, stage="Labelling clusters")
            actions.checkpoint(job_id)
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

        actions.update(job_id, progress=92, stage="Saving checkpoint")
        actions.checkpoint(job_id)
        response.generated_at = datetime.now(timezone.utc).isoformat()
        service.save_checkpoint(user_id, project_id, response, fingerprint)
        actions.update(job_id, progress=100, status="done", stage="Done")
    except Exception as exc:  # noqa: BLE001 - surfaced to the frontend
        actions.update(job_id, status="error", error=str(exc))
    finally:
        pending = actions.pop_rebuild_pending(job_id)
        service.db.close()
        if pending:
            start_build(service_factory, user_id, project_id)


def _on_summarize_progress(job_id: str, done: int, total: int) -> None:
    actions.checkpoint(job_id)
    actions.update(
        job_id,
        progress=84 + int(done / max(total, 1) * 4),
        stage="Summarizing papers",
    )
