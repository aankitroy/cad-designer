import pytest

from app import edits
from app.sessions import SessionStore


def test_create_and_get(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    assert store.get(sid) is not None


def test_create_rejects_bad_dxf():
    store = SessionStore()
    with pytest.raises(ValueError):
        store.create(b"this is not a dxf")


def test_snapshot_and_undo(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    handles_before = len(list(store.get(sid).modelspace()))

    store.snapshot(sid)
    edits.add_wall(store.get(sid), 0, 0, 1, 1)
    assert len(list(store.get(sid).modelspace())) == handles_before + 1

    store.undo(sid)
    assert len(list(store.get(sid).modelspace())) == handles_before


def test_undo_with_no_history_is_noop(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    store.undo(sid)  # should not raise
    assert store.get(sid) is not None
