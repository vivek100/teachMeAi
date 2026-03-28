"""Tests for session state — the central blackboard that all components read/write.

If state is broken, orchestrator gets stale data, resolver writes to wrong session, etc.
"""

import pytest
from backend.domain.models import OrchestratorDecision, TranscriptChunk
from backend.domain.state import SessionState, SessionStore


class TestSessionState:
    def test_each_session_gets_unique_id(self):
        s1 = SessionState()
        s2 = SessionState()
        assert s1.session_id != s2.session_id

    def test_state_is_mutable_by_reference(self):
        """Components share a reference to state — mutations must be visible."""
        state = SessionState()
        state.transcript_chunks.append(
            TranscriptChunk(session_id=state.session_id, text="hello")
        )
        assert len(state.transcript_chunks) == 1
        state.active_topic = "tokenization"
        assert state.active_topic == "tokenization"

    def test_recent_decisions_are_appendable(self):
        state = SessionState()
        for i in range(25):
            state.recent_decisions.append(
                OrchestratorDecision(intent="wait", rationale=f"reason {i}")
            )
        assert len(state.recent_decisions) == 25  # no auto-trim (service trims)


class TestSessionStore:
    def test_create_and_retrieve(self):
        store = SessionStore()
        state = store.create(lecture_id="test_lecture")
        assert state.lecture_id == "test_lecture"
        retrieved = store.get(state.session_id)
        assert retrieved is state  # same object reference

    def test_get_nonexistent_returns_none(self):
        store = SessionStore()
        assert store.get("doesnt_exist") is None

    def test_get_or_raise_throws_keyerror(self):
        store = SessionStore()
        with pytest.raises(KeyError, match="not found"):
            store.get_or_raise("doesnt_exist")

    def test_delete_removes_session(self):
        store = SessionStore()
        state = store.create()
        store.delete(state.session_id)
        assert store.get(state.session_id) is None

    def test_delete_nonexistent_is_noop(self):
        store = SessionStore()
        store.delete("doesnt_exist")  # should not raise

    def test_list_ids_reflects_mutations(self):
        store = SessionStore()
        s1 = store.create()
        s2 = store.create()
        ids = store.list_ids()
        assert s1.session_id in ids
        assert s2.session_id in ids
        store.delete(s1.session_id)
        assert s1.session_id not in store.list_ids()

    def test_sessions_are_isolated(self):
        """Mutating one session should not affect another."""
        store = SessionStore()
        s1 = store.create()
        s2 = store.create()
        s1.active_topic = "tokenization"
        assert s2.active_topic is None

