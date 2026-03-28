"""In-memory session state for TeachWithMeAI."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.domain.models import (
    BackendEvent,
    CanvasOpBatch,
    OrchestratorDecision,
    TranscriptChunk,
    TranscriptWindow,
    _new_id,
)


class SessionState(BaseModel):
    """All mutable state for a single lecture session."""

    session_id: str = Field(default_factory=_new_id)
    lecture_id: str = ""

    # Transcript accumulation
    transcript_chunks: list[TranscriptChunk] = []
    processed_cursor: int = 0  # index of first unprocessed chunk

    # Most recent window sent to orchestrator
    recent_windows: list[TranscriptWindow] = []

    # Orchestrator memory
    active_topic: str | None = None
    recent_decisions: list[OrchestratorDecision] = []

    # Artifact state
    artifact_registry_version: str = "v1"
    drawn_artifacts: list[dict] = []  # [{artifact_id, family, topic}] — what's on canvas

    # Pending / emitted
    pending_batches: list[CanvasOpBatch] = []
    emitted_events: list[BackendEvent] = []


class SessionStore:
    """Simple in-memory store mapping session_id → SessionState."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, lecture_id: str = "") -> SessionState:
        state = SessionState(lecture_id=lecture_id)
        self._sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def get_or_raise(self, session_id: str) -> SessionState:
        state = self.get(session_id)
        if state is None:
            raise KeyError(f"Session {session_id} not found")
        return state

    def list_ids(self) -> list[str]:
        return list(self._sessions.keys())

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

