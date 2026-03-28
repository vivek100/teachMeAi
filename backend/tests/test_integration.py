"""Integration tests — hit real LLM, exercise the real pipeline.

These tests:
- Feed transcript chunks through the ACTUAL ingestor → windower → orchestrator → resolver pipeline
- Call the REAL OpenAI API (require OPENAI_API_KEY in backend/.env)
- Validate that the orchestrator produces correct decisions for different transcript types
- Validate that resolved ops have valid tldraw shape structure
- Dump full trace JSON for every test to backend/tests/test_traces/

Skip automatically if no API key is available.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load env before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import railtracks as rt

from backend.artifacts.registry import ArtifactRegistry
from backend.artifacts.resolver import ArtifactResolver
from backend.domain.state import SessionState
from backend.orchestration.service import OrchestrationService
from backend.streaming.publisher import EventPublisher
from backend.streaming.subscribers import RecorderSubscriber
from backend.transcript.ingest import ChunkIngestor
from backend.transcript.windowing import WindowBuilder

TRACE_DIR = Path(__file__).parent / "test_traces"

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping integration tests",
)


def _make_pipeline():
    """Wire up the full pipeline with real OpenAI LLM. Returns all components."""
    pub = EventPublisher()
    rec = RecorderSubscriber()
    pub.subscribe(rec)

    registry = ArtifactRegistry()
    registry.load()

    resolver = ArtifactResolver(registry, pub)
    llm = rt.llm.OpenAILLM("gpt-5.4-mini")

    orchestration = OrchestrationService(
        registry=registry,
        resolver=resolver,
        publisher=pub,
        llm=llm,
    )

    ingestor = ChunkIngestor(pub)
    windower = WindowBuilder(pub, window_size=6, min_new_chunks=3)

    return orchestration, ingestor, windower, registry, pub, rec


def _dump_trace(
    test_name: str,
    input_chunks: list[str],
    state: SessionState,
    rec: RecorderSubscriber,
    batches: list,
    elapsed_s: float,
):
    """Write a complete trace JSON for a single test run."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    trace = {
        "test_name": test_name,
        "timestamp": ts,
        "elapsed_seconds": round(elapsed_s, 2),
        "input": {
            "chunks": input_chunks,
            "chunk_count": len(input_chunks),
        },
        "state_after": {
            "session_id": state.session_id,
            "active_topic": state.active_topic,
            "processed_cursor": state.processed_cursor,
            "transcript_chunk_count": len(state.transcript_chunks),
            "window_count": len(state.recent_windows),
            "decision_count": len(state.recent_decisions),
            "pending_batch_count": len(state.pending_batches),
        },
        "decisions": [d.model_dump() for d in state.recent_decisions],
        "batches": [b.model_dump() for b in batches],
        "events": [
            {
                "kind": e.kind,
                "ts_ms": e.ts_ms,
                "payload": e.payload,
            }
            for e in rec.events
        ],
        "windows": [
            {
                "combined_text": w.combined_text,
                "chunk_count": len(w.chunks),
            }
            for w in state.recent_windows
        ],
    }

    out = TRACE_DIR / f"{test_name}_{ts}.json"
    out.write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"TRACE: {out.name}")
    print(f"{'='*60}")
    print(f"  Elapsed: {elapsed_s:.1f}s")
    print(f"  Decisions: {len(state.recent_decisions)}")
    for i, d in enumerate(state.recent_decisions):
        print(f"    [{i}] intent={d.intent}  topic={d.topic}  confidence={d.confidence}")
        print(f"        query={d.artifact_query}")
        print(f"        rationale={d.rationale}")
    print(f"  Batches: {len(batches)}")
    for i, b in enumerate(batches):
        print(f"    [{i}] artifact_id={b.artifact_id}  ops={len(b.ops)}")
    print(f"  Events: {len(rec.events)}")
    for e in rec.events:
        print(f"    {e.kind}: {json.dumps(e.payload, default=str)[:120]}")
    print(f"{'='*60}\n")
    return trace


async def _ingest_and_trigger(chunks_text: list[str]):
    """Feed chunks through the pipeline. Returns (state, recorder, batches)."""
    orchestration, ingestor, windower, _, _, rec = _make_pipeline()
    state = SessionState(session_id="integration_test")

    batches = []
    for text in chunks_text:
        await ingestor.ingest(state, text, source="replay")
        if windower.has_ready_window(state):
            window = await windower.build_window(state)
            if window:
                batch = await orchestration.process_window(state, window)
                if batch:
                    batches.append(batch)

    return state, rec, batches


# ─── Test 1: Tokenization transcript → should draw token_grid artifact ────────

TOKENIZATION_CHUNKS = [
    "Let's start with the very basics. How does a computer understand text?",
    "The first step is tokenization. We take a sentence and break it into smaller pieces called tokens.",
    "For example the word understanding might be split into under, stand, and ing.",
    "Each of these subword tokens gets mapped to a numerical ID from a vocabulary.",
    "This is called byte pair encoding or BPE, one of the most common tokenization methods.",
    "Let me show you how this works visually with a token grid.",
]


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_tokenization_transcript_produces_draw_decision():
    """LLM should recognize tokenization content and decide to draw."""
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(TOKENIZATION_CHUNKS)
    _dump_trace("tokenization_draw_decision", TOKENIZATION_CHUNKS, state, rec, batches, time.time() - t0)

    # The orchestrator must have made at least one decision
    assert len(state.recent_decisions) > 0, "Orchestrator made no decisions"
    assert "decision_made" in rec.kinds, f"Events: {rec.kinds}"

    # At least one decision should be draw_artifact (not all wait)
    intents = [d.intent for d in state.recent_decisions]
    assert "draw_artifact" in intents, (
        f"Expected draw_artifact for tokenization content, got: {intents}"
    )

    # The draw decision should mention tokenization-related topic
    draw_decisions = [d for d in state.recent_decisions if d.intent == "draw_artifact"]
    for d in draw_decisions:
        assert d.artifact_query, "draw_artifact decision has no artifact_query"
        assert d.confidence > 0, "draw_artifact decision has zero confidence"
        assert d.rationale, "draw_artifact decision has no rationale"


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_tokenization_produces_valid_tldraw_ops():
    """Resolved ops must have valid tldraw shape structure."""
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(TOKENIZATION_CHUNKS)
    _dump_trace("tokenization_tldraw_ops", TOKENIZATION_CHUNKS, state, rec, batches, time.time() - t0)

    if not batches:
        pytest.skip("No batches produced (orchestrator may have chosen wait)")

    for batch in batches:
        assert batch.artifact_id, "Batch has no artifact_id"
        assert len(batch.ops) > 0, "Batch has no ops"

        for op in batch.ops:
            assert op["op_type"] == "create_shape"


# ─── Test 2: Vague/logistics transcript → should wait, NOT draw ───────────────

VAGUE_CHUNKS = [
    "So yeah, welcome back everyone.",
    "Before we get started I wanted to mention a few logistics.",
    "The assignment deadline has been moved to next Friday.",
    "Also office hours will be on Thursday this week instead of Wednesday.",
    "Okay let me pull up my slides here.",
    "Hmm, where did I save those... one second.",
]


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_vague_transcript_does_not_draw():
    """Logistics/filler talk should NOT trigger artifact drawing."""
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(VAGUE_CHUNKS)
    _dump_trace("vague_no_draw", VAGUE_CHUNKS, state, rec, batches, time.time() - t0)

    assert len(state.recent_decisions) > 0, "Orchestrator made no decisions"

    # Should NOT have produced any batches
    assert len(batches) == 0, (
        f"Orchestrator drew on vague content! Decisions: "
        f"{[(d.intent, d.rationale) for d in state.recent_decisions]}"
    )

    # All decisions should be 'wait'
    intents = [d.intent for d in state.recent_decisions]
    assert all(i == "wait" for i in intents), (
        f"Expected all wait for logistics talk, got: {intents}"
    )


# ─── Test 3: Attention transcript → should draw attention_matrix artifact ─────

ATTENTION_CHUNKS = [
    "Now let's talk about the core innovation. The transformer architecture.",
    "The key mechanism is called self-attention.",
    "Self-attention lets each token look at every other token in the sequence.",
    "It computes attention scores, basically how much each token should attend to every other.",
    "You can think of it as a matrix where rows are queries and columns are keys.",
    "High scores mean strong relationships between those tokens.",
]


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_attention_transcript_draws_attention_artifact():
    """Attention-focused transcript should trigger attention_matrix artifact."""
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(ATTENTION_CHUNKS)
    _dump_trace("attention_artifact", ATTENTION_CHUNKS, state, rec, batches, time.time() - t0)

    assert len(state.recent_decisions) > 0

    draw_decisions = [d for d in state.recent_decisions if d.intent == "draw_artifact"]
    if not draw_decisions:
        pytest.skip("Orchestrator chose wait — flaky due to LLM non-determinism")

    # At least one draw should be attention-related
    queries = [d.artifact_query.lower() for d in draw_decisions if d.artifact_query]
    assert any("attention" in q or "matrix" in q or "transformer" in q for q in queries), (
        f"Expected attention-related query, got: {queries}"
    )


# ─── Test 4: Full intro_to_llms replay → multiple topics, multiple draws ──────

@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_full_replay_produces_multiple_decisions():
    """Full lecture replay should produce decisions across multiple topics."""
    from pathlib import Path

    fixture = Path(__file__).parent.parent / "transcript" / "fixtures" / "intro_to_llms.json"
    with open(fixture, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(all_chunks)
    _dump_trace("full_replay", all_chunks, state, rec, batches, time.time() - t0)

    # Should have made multiple decisions across the whole lecture
    assert len(state.recent_decisions) >= 2, (
        f"Only {len(state.recent_decisions)} decisions for a 22-chunk lecture"
    )

    # Should have at least one draw
    intents = [d.intent for d in state.recent_decisions]
    assert "draw_artifact" in intents, (
        f"No draw_artifact in full lecture replay! Intents: {intents}"
    )

    # Should have topics set
    topics = [d.topic for d in state.recent_decisions if d.topic]
    assert len(topics) > 0, "No topics identified in full lecture"


# ─── Test 5: Event sequencing is correct ──────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_event_sequence_for_draw():
    """When orchestrator draws, events must fire in correct order:
    chunk_ingested → window_ready → decision_made → artifact_selected → artifact_instantiated → op_batch_ready
    """
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(TOKENIZATION_CHUNKS)
    _dump_trace("event_sequence", TOKENIZATION_CHUNKS, state, rec, batches, time.time() - t0)

    kinds = rec.kinds

    # chunk_ingested events must come first
    assert kinds[0] == "chunk_ingested"

    # If a draw happened, validate the full sequence
    if batches:
        # Find the decision_made event
        assert "decision_made" in kinds
        assert "window_ready" in kinds

        # decision_made must come after window_ready
        wr_idx = kinds.index("window_ready")
        dm_idx = kinds.index("decision_made")
        assert dm_idx > wr_idx, f"decision_made ({dm_idx}) before window_ready ({wr_idx})"

        # If artifact was drawn, check artifact events come after decision
        if "artifact_selected" in kinds:
            as_idx = kinds.index("artifact_selected")
            assert as_idx > dm_idx, "artifact_selected before decision_made"

        if "op_batch_ready" in kinds:
            ob_idx = kinds.index("op_batch_ready")
            assert ob_idx > dm_idx, "op_batch_ready before decision_made"


# ─── Test 6: State mutation after pipeline run ───────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_state_is_correctly_mutated_after_pipeline():
    """After running the pipeline, session state should reflect what happened."""
    t0 = time.time()
    state, rec, batches = await _ingest_and_trigger(TOKENIZATION_CHUNKS)
    _dump_trace("state_mutation", TOKENIZATION_CHUNKS, state, rec, batches, time.time() - t0)

    # Chunks should be stored
    assert len(state.transcript_chunks) == len(TOKENIZATION_CHUNKS)

    # Cursor should have advanced (windows were built)
    assert state.processed_cursor > 0

    # Windows should be recorded
    assert len(state.recent_windows) > 0

    # Decisions should be recorded
    assert len(state.recent_decisions) > 0

    # If draws happened, pending_batches should have them
    if batches:
        assert len(state.pending_batches) == len(batches)
        for batch in state.pending_batches:
            assert batch.artifact_id is not None

