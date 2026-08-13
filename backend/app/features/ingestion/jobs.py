"""Background job manager for document processing.

Each ingestion pipeline runs in its own daemon thread. A control event per job
drives pause/resume: the event is *set* while running and *cleared* while
paused, and the pipeline blocks on ``wait()`` between work units. Because the
event outlives the thread, `pause`/`resume`/`reprocess` can be called any time.
"""

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class JobState:
    event: threading.Event
    total_units: int = 0
    done_units: int = 0


class JobManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}

    def submit(self, document_id: str, fn, *args) -> None:
        state = JobState(event=threading.Event())
        state.event.set()  # running by default
        with self._lock:
            self._jobs[document_id] = state
        thread = threading.Thread(
            target=self._run,
            args=(document_id, fn, args),
            daemon=True,
            name=f"ingest-{document_id}",
        )
        thread.start()

    def _run(self, document_id: str, fn, args) -> None:
        try:
            fn(*args)
        except Exception:
            logger.exception("ingestion job %s crashed", document_id)
        finally:
            with self._lock:
                self._jobs.pop(document_id, None)

    def _state(self, document_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(document_id)

    def is_active(self, document_id: str) -> bool:
        return self._state(document_id) is not None

    def is_paused(self, document_id: str) -> bool:
        state = self._state(document_id)
        return bool(state and not state.event.is_set())

    def pause(self, document_id: str) -> bool:
        state = self._state(document_id)
        if state is None:
            return False
        state.event.clear()
        return True

    def resume(self, document_id: str) -> bool:
        state = self._state(document_id)
        if state is None:
            return False
        state.event.set()
        return True

    def checkpoint(self, document_id: str) -> None:
        """Block the calling pipeline until the job is resumed (no-op if idle)."""
        state = self._state(document_id)
        if state is not None:
            state.event.wait()

    def set_progress(self, document_id: str, total: int, done: int) -> None:
        state = self._state(document_id)
        if state is not None:
            state.total_units = total
            state.done_units = done

    def progress(self, document_id: str) -> tuple[int, int] | None:
        state = self._state(document_id)
        if state is None:
            return None
        return state.done_units, state.total_units


# Module-level singleton shared across the app.
job_manager = JobManager()
