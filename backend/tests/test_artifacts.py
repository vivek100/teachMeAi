"""Tests for artifact registry search quality + resolver output correctness.

These test that:
- The keyword search actually disambiguates between artifacts (not just "returns something")
- The resolver produces shapes that tldraw can actually consume
- Parameter injection works
- Event sequencing is correct
"""

import pytest
from backend.artifacts.registry import ArtifactRegistry
from backend.artifacts.resolver import ArtifactResolver
from backend.domain.models import OrchestratorDecision
from backend.streaming.publisher import EventPublisher
from backend.streaming.subscribers import RecorderSubscriber

# Required tldraw shape fields — if any are missing, frontend will crash
REQUIRED_SHAPE_KEYS = {"id", "type"}


@pytest.fixture
def registry():
    reg = ArtifactRegistry()
    reg.load()
    return reg


@pytest.fixture
def resolver_with_recorder(registry):
    pub = EventPublisher()
    rec = RecorderSubscriber()
    pub.subscribe(rec)
    resolver = ArtifactResolver(registry, pub)
    return resolver, rec


class TestRegistrySearchQuality:
    """Verifies the search can distinguish between 5 different artifact types.
    If the search is broken, the orchestrator will draw the wrong thing every time."""

    def test_tokenization_query_finds_token_grid(self, registry):
        result = registry.search("tokenization bpe subword")
        assert result is not None
        assert result.artifact_id == "token_grid_basic"

    def test_attention_query_finds_attention_matrix(self, registry):
        result = registry.search("self-attention matrix query key")
        assert result is not None
        assert result.artifact_id == "attention_matrix_basic"

    def test_embedding_query_finds_embedding_space(self, registry):
        result = registry.search("embedding vector space")
        assert result is not None
        assert result.artifact_id == "embedding_space_basic"

    def test_transformer_query_finds_transformer_stack(self, registry):
        result = registry.search("transformer architecture stack layers")
        assert result is not None
        assert result.artifact_id == "transformer_stack_basic"

    def test_loss_query_finds_loss_curve(self, registry):
        result = registry.search("training loss curve overfitting")
        assert result is not None
        assert result.artifact_id == "loss_curve_basic"

    def test_completely_unrelated_query_returns_none(self, registry):
        # Use words with zero overlap to any artifact tags/descriptions
        result = registry.search("basketball playoff jersey")
        assert result is None

    def test_ambiguous_query_returns_best_match_not_crash(self, registry):
        """The model query like 'deep learning' could match multiple.
        Should return something, not crash."""
        result = registry.search("deep learning neural network")
        # Could match transformer or embedding — just verify it's a valid artifact
        assert result is None or result.artifact_id in {
            a.artifact_id for a in registry.list_all()
        }


class TestResolverOutputValidity:
    """Verifies the resolver produces ops that tldraw can actually render."""

    @pytest.mark.asyncio
    async def test_ops_have_valid_tldraw_shape_structure(self, resolver_with_recorder):
        resolver, rec = resolver_with_recorder
        decision = OrchestratorDecision(
            intent="draw_artifact",
            artifact_query="tokenization bpe token",
            rationale="test",
            confidence=0.9,
        )
        batch = await resolver.resolve(decision, session_id="test")
        assert batch is not None
        assert len(batch.ops) > 0

        for op in batch.ops:
            assert op["op_type"] == "create_shape"
            shape = op["shape"]
            # Every shape must have an id and type for tldraw
            for key in REQUIRED_SHAPE_KEYS:
                assert key in shape, f"Missing required key '{key}' in shape: {shape}"
            # ID must be a string
            assert isinstance(shape["id"], str)
            # Type must be a known tldraw type
            assert shape["type"] in ("geo", "text", "frame", "arrow", "line", "draw")

    @pytest.mark.asyncio
    async def test_each_instantiation_produces_unique_shape_ids(self, resolver_with_recorder):
        """If two batches share shape IDs, tldraw will overwrite the first drawing."""
        resolver, _ = resolver_with_recorder
        decision = OrchestratorDecision(
            intent="draw_artifact",
            artifact_query="tokenization",
            rationale="test",
        )
        b1 = await resolver.resolve(decision, session_id="test")
        b2 = await resolver.resolve(decision, session_id="test")
        assert b1 is not None and b2 is not None

        ids_1 = {op["shape"]["id"] for op in b1.ops}
        ids_2 = {op["shape"]["id"] for op in b2.ops}
        assert ids_1.isdisjoint(ids_2), f"Shared IDs: {ids_1 & ids_2}"

    @pytest.mark.asyncio
    async def test_event_sequence_is_select_then_instantiate(self, resolver_with_recorder):
        """Frontend relies on this order to show progress."""
        resolver, rec = resolver_with_recorder
        decision = OrchestratorDecision(
            intent="draw_artifact",
            artifact_query="tokenization bpe",
            rationale="test",
        )
        await resolver.resolve(decision, session_id="test")
        assert rec.kinds == ["artifact_selected", "artifact_instantiated"]

    @pytest.mark.asyncio
    async def test_no_match_emits_warning_not_crash(self, resolver_with_recorder):
        resolver, rec = resolver_with_recorder
        decision = OrchestratorDecision(
            intent="draw_artifact",
            artifact_query="basketball playoffs",
            rationale="test",
        )
        batch = await resolver.resolve(decision, session_id="test")
        assert batch is None
        assert "warning" in rec.kinds

    @pytest.mark.asyncio
    async def test_wait_intent_produces_nothing(self, resolver_with_recorder):
        resolver, rec = resolver_with_recorder
        decision = OrchestratorDecision(intent="wait", rationale="nothing to draw")
        batch = await resolver.resolve(decision, session_id="test")
        assert batch is None
        assert len(rec.events) == 0

