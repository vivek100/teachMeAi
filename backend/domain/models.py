"""Core domain models for TeachWithMeAI backend."""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

class TranscriptChunk(BaseModel):
    """A single chunk of transcribed speech or user command."""
    chunk_id: str = Field(default_factory=_new_id)
    session_id: str
    text: str
    ts_start_ms: int = Field(default_factory=_now_ms)
    ts_end_ms: int | None = None
    source: Literal["speech", "user_command", "replay"] = "speech"


class TranscriptWindow(BaseModel):
    """A rolling window of transcript chunks sent to the orchestrator."""
    session_id: str
    start_chunk_id: str | None = None
    end_chunk_id: str | None = None
    chunks: list[TranscriptChunk] = []
    combined_text: str = ""


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

class ArtifactSpec(BaseModel):
    """A reusable, parameterized visual artifact definition."""
    artifact_id: str
    family: str
    version: str = "v1"
    title: str = ""
    description: str = ""
    tags: list[str] = []
    parameters: dict[str, dict] = {}
    shape_template: list[dict] = []


# ---------------------------------------------------------------------------
# Orchestrator decision
# ---------------------------------------------------------------------------

class OrchestratorDecision(BaseModel):
    """Structured output from the orchestrator agent."""
    intent: Literal["wait", "draw_artifact", "annotate", "review"] = "wait"
    topic: str | None = None
    rationale: str = ""
    artifact_query: str | None = None
    annotation_text: str | None = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Canvas operations (target shape – used before frontend exists)
# ---------------------------------------------------------------------------

class CanvasOpBatch(BaseModel):
    """A batch of canvas operations to be applied on the frontend."""
    batch_id: str = Field(default_factory=_new_id)
    session_id: str
    ops: list[dict] = []
    artifact_id: str | None = None
    source: Literal["artifact_engine", "fallback_generator", "annotation"] = "artifact_engine"


# ---------------------------------------------------------------------------
# Backend events
# ---------------------------------------------------------------------------

class BackendEvent(BaseModel):
    """An event emitted by the backend pipeline."""
    event_id: str = Field(default_factory=_new_id)
    session_id: str
    kind: Literal[
        "chunk_ingested",
        "window_ready",
        "decision_made",
        "artifact_selected",
        "artifact_instantiated",
        "op_batch_ready",
        "annotation_added",
        "warning",
        "error",
    ]
    payload: dict = {}
    ts_ms: int = Field(default_factory=_now_ms)

