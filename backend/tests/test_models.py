"""Tests for domain models — validates constraints, serialization, and edge cases."""

import pytest
from pydantic import ValidationError
from backend.domain.models import (
    ArtifactSpec,
    BackendEvent,
    CanvasOpBatch,
    OrchestratorDecision,
    TranscriptChunk,
    TranscriptWindow,
)


class TestOrchestratorDecision:
    """The core output schema — must be strict about valid intents and confidence range."""

    def test_rejects_invalid_intent(self):
        with pytest.raises(ValidationError):
            OrchestratorDecision(intent="explode")

    def test_all_valid_intents_accepted(self):
        for intent in ("wait", "draw_artifact", "annotate", "review"):
            d = OrchestratorDecision(intent=intent, rationale="test")
            assert d.intent == intent

    def test_draw_decision_round_trips_through_json(self):
        """Ensures the structured output can serialize/deserialize —
        critical since this goes over the wire from Gemini."""
        original = OrchestratorDecision(
            intent="draw_artifact",
            topic="tokenization",
            artifact_query="token grid bpe",
            rationale="Lecturer explaining BPE",
            confidence=0.85,
        )
        json_str = original.model_dump_json()
        restored = OrchestratorDecision.model_validate_json(json_str)
        assert restored.intent == original.intent
        assert restored.artifact_query == original.artifact_query
        assert restored.confidence == 0.85

    def test_confidence_accepts_boundary_values(self):
        # Gemini might return 0.0 or 1.0
        OrchestratorDecision(confidence=0.0)
        OrchestratorDecision(confidence=1.0)


class TestCanvasOpBatch:
    """Validates that batches get unique IDs — critical for idempotent frontend application."""

    def test_two_batches_get_different_ids(self):
        b1 = CanvasOpBatch(session_id="s1", ops=[])
        b2 = CanvasOpBatch(session_id="s1", ops=[])
        assert b1.batch_id != b2.batch_id

    def test_rejects_invalid_source(self):
        with pytest.raises(ValidationError):
            CanvasOpBatch(session_id="s1", ops=[], source="magic")


class TestTranscriptChunk:
    """Validates chunk ID generation and source constraints."""

    def test_two_chunks_get_different_ids(self):
        c1 = TranscriptChunk(session_id="s1", text="hello")
        c2 = TranscriptChunk(session_id="s1", text="world")
        assert c1.chunk_id != c2.chunk_id

    def test_rejects_invalid_source(self):
        with pytest.raises(ValidationError):
            TranscriptChunk(session_id="s1", text="hi", source="telepathy")

    def test_replay_source_accepted(self):
        c = TranscriptChunk(session_id="s1", text="hi", source="replay")
        assert c.source == "replay"


class TestBackendEvent:
    """Validates event kind constraints."""

    def test_rejects_invalid_kind(self):
        with pytest.raises(ValidationError):
            BackendEvent(session_id="s1", kind="explosion", payload={})

