import threading
import time

from app.features.actions import registry as actions
from app.features.settings.schemas import SettingsUpdate
from app.features.settings.service import SettingsService


def _cleanup(*action_ids: str) -> None:
    for action_id in action_ids:
        actions.update(action_id, status="done")


def test_register_creates_queued_public_view():
    action_id = actions.register("u1", "p1", "literature", "Literature map")
    try:
        item = actions.get(action_id)
        assert item["id"] == action_id
        assert item["status"] == "queued"
        assert item["progress"] == 0
        assert item["stage"] == "Waiting for a slot"
        assert "pause_event" not in item
        assert "_slot_acquired" not in item
    finally:
        _cleanup(action_id)


def test_list_for_user_returns_public_views_newest_first():
    first = actions.register("u1", "p1", "literature", "Lit")
    second = actions.register("u1", "p2", "graph", "Graph")
    actions.update(first, progress=42, stage="Extracting")
    actions.register("u2", "p9", "graph", "Someone else")
    try:
        items = actions.list_for_user("u1")
        mine = [i for i in items if i["id"] in (first, second)]
        assert [i["id"] for i in mine] == [second, first]
        assert all("pause_event" not in i for i in mine)
        assert all("user_id" in i and "project_id" in i for i in mine)
        assert all(i["user_id"] == "u1" for i in mine)
        assert mine[1]["progress"] == 42
    finally:
        _cleanup(first, second)


def test_pause_resume_requires_ownership():
    action_id = actions.register("u1", "p1", "graph", "Graph")
    try:
        assert actions.pause(action_id, "u2") is None
        assert actions.pause(action_id, "u1") is not None
        assert actions.get(action_id)["status"] == "paused"
        assert actions.resume(action_id, "u2") is None
        assert actions.resume(action_id, "u1") is not None
        assert actions.get(action_id)["status"] == "running"
        # pausing/resuming a finished action is a no-op
        actions.update(action_id, status="done")
        assert actions.pause(action_id, "u1") is None
        assert actions.resume(action_id, "u1") is None
    finally:
        _cleanup(action_id)


def test_find_active_and_rebuild_pending():
    action_id = actions.register("u1", "p1", "graph", "G")
    try:
        assert actions.find_active("u1", "p1", "graph") == action_id
        assert actions.find_active("u1", "p1", "literature") is None
        actions.mark_rebuild_pending(action_id)
        assert actions.pop_rebuild_pending(action_id) is True
        assert actions.pop_rebuild_pending(action_id) is False
        actions.update(action_id, status="done")
        assert actions.find_active("u1", "p1", "graph") is None
    finally:
        _cleanup(action_id)


def test_checkpoint_blocks_until_resumed():
    action_id = actions.register("u1", "p1", "literature", "Lit")
    actions.pause(action_id, "u1")
    done: list = []

    def worker():
        actions.checkpoint(action_id)
        done.append(True)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    time.sleep(0.2)
    assert done == []
    actions.resume(action_id, "u1")
    thread.join(timeout=5)
    assert done == [True]
    _cleanup(action_id)


def test_wait_for_slot_limits_running_actions():
    a = actions.register("u1", "p1", "literature", "A")
    actions.wait_for_slot(a, "u1", lambda: 1)
    assert actions.get(a)["status"] == "running"

    b = actions.register("u1", "p2", "graph", "B")
    results: list = []

    def run_b():
        actions.wait_for_slot(b, "u1", lambda: 1)
        results.append(actions.get(b)["status"])

    thread = threading.Thread(target=run_b, daemon=True)
    thread.start()
    try:
        time.sleep(0.3)
        assert actions.get(b)["status"] == "queued"
        actions.update(a, status="done")
        thread.join(timeout=5)
        assert results == ["running"]
    finally:
        _cleanup(a, b)


def test_wait_for_slot_does_not_start_a_paused_action():
    a = actions.register("u1", "p1", "literature", "A")
    actions.wait_for_slot(a, "u1", lambda: 1)

    b = actions.register("u1", "p2", "graph", "B")
    actions.pause(b, "u1")
    results: list = []

    def run_b():
        actions.wait_for_slot(b, "u1", lambda: 1)
        results.append(actions.get(b)["status"])

    thread = threading.Thread(target=run_b, daemon=True)
    thread.start()
    try:
        time.sleep(0.3)
        assert actions.get(b)["status"] == "paused"
        # a freed slot must not start a paused action
        actions.update(a, status="done")
        time.sleep(0.3)
        assert results == []
        actions.resume(b, "u1")
        thread.join(timeout=5)
        assert results == ["running"]
    finally:
        _cleanup(a, b)


def test_configured_limit_reads_setting():
    import sqlite3

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE user_settings (user_id TEXT PRIMARY KEY, settings TEXT NOT NULL DEFAULT '{}')"
    )
    try:
        assert actions.configured_limit(db, "no-such-user") == actions.DEFAULT_MAX_CONCURRENT
        SettingsService(db).update_settings("u1", SettingsUpdate(max_concurrent_actions=5))
        assert actions.configured_limit(db, "u1") == 5
        SettingsService(db).update_settings("u1", SettingsUpdate(max_concurrent_actions=0))
        assert actions.configured_limit(db, "u1") == 1
        SettingsService(db).update_settings("u1", SettingsUpdate(max_concurrent_actions=99))
        assert actions.configured_limit(db, "u1") == 16
    finally:
        db.close()
