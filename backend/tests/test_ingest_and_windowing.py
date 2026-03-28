"""Tests for transcript ingestion and windowing — the core pipeline feeding the orchestrator.

Tests verify:
- Chunks are stored correctly and events fire
- Windowing math (cursor advancement, overlap) is correct
- Edge cases: empty text, rapid ingestion, cursor doesn't go backwards
"""

import pytest
from backend.domain.state import SessionState
from backend.streaming.publisher import EventPublisher
from backend.streaming.subscribers import RecorderSubscriber
from backend.transcript.ingest import ChunkIngestor
from backend.transcript.windowing import WindowBuilder


@pytest.fixture
def wired():
    """Returns (publisher, recorder, ingestor) wired together."""
    pub = EventPublisher()
    rec = RecorderSubscriber()
    pub.subscribe(rec)
    ingestor = ChunkIngestor(pub)
    return pub, rec, ingestor


class TestChunkIngestor:
    @pytest.mark.asyncio
    async def test_chunk_stored_in_state(self, wired):
        _, _, ingestor = wired
        state = SessionState(session_id="test")
        chunk = await ingestor.ingest(state, "hello world")
        assert state.transcript_chunks == [chunk]
        assert chunk.text == "hello world"
        assert chunk.source == "speech"

    @pytest.mark.asyncio
    async def test_chunk_ingested_event_fires(self, wired):
        _, rec, ingestor = wired
        state = SessionState(session_id="test")
        await ingestor.ingest(state, "hello")
        assert rec.kinds == ["chunk_ingested"]
        assert rec.events[0].payload["text"] == "hello"

    @pytest.mark.asyncio
    async def test_multiple_chunks_accumulate_in_order(self, wired):
        _, _, ingestor = wired
        state = SessionState(session_id="test")
        for t in ["first", "second", "third"]:
            await ingestor.ingest(state, t)
        assert [c.text for c in state.transcript_chunks] == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_replay_source_stored(self, wired):
        _, _, ingestor = wired
        state = SessionState(session_id="test")
        chunk = await ingestor.ingest(state, "replayed", source="replay")
        assert chunk.source == "replay"


class TestWindowBuilder:
    @pytest.mark.asyncio
    async def test_does_not_fire_below_min_chunks(self, wired):
        pub, _, ingestor = wired
        windower = WindowBuilder(pub, window_size=4, min_new_chunks=3)
        state = SessionState(session_id="test")
        await ingestor.ingest(state, "only one")
        await ingestor.ingest(state, "only two")
        assert not windower.has_ready_window(state)
        assert await windower.build_window(state) is None

    @pytest.mark.asyncio
    async def test_fires_at_min_chunks_with_correct_text(self, wired):
        pub, rec, ingestor = wired
        windower = WindowBuilder(pub, window_size=4, min_new_chunks=3, overlap=1)
        state = SessionState(session_id="test")
        for i in range(3):
            await ingestor.ingest(state, f"chunk {i}")

        assert windower.has_ready_window(state)
        window = await windower.build_window(state)
        assert window is not None
        # Window must contain the actual text from all 3 chunks
        for i in range(3):
            assert f"chunk {i}" in window.combined_text
        assert "window_ready" in rec.kinds

    @pytest.mark.asyncio
    async def test_cursor_advances_preventing_duplicate_windows(self, wired):
        """After building a window, calling build again with same chunks should return None."""
        pub, _, ingestor = wired
        windower = WindowBuilder(pub, window_size=4, min_new_chunks=3, overlap=0)
        state = SessionState(session_id="test")
        for i in range(3):
            await ingestor.ingest(state, f"chunk {i}")

        w1 = await windower.build_window(state)
        assert w1 is not None
        cursor_after = state.processed_cursor
        assert cursor_after > 0

        # No new chunks — should not fire again
        w2 = await windower.build_window(state)
        assert w2 is None, "Window fired twice on same chunks"

    @pytest.mark.asyncio
    async def test_cursor_never_goes_backwards(self, wired):
        pub, _, ingestor = wired
        windower = WindowBuilder(pub, window_size=4, min_new_chunks=2, overlap=1)
        state = SessionState(session_id="test")

        prev_cursor = 0
        for batch in range(3):
            for i in range(3):
                await ingestor.ingest(state, f"batch{batch}_chunk{i}")
            window = await windower.build_window(state)
            if window:
                assert state.processed_cursor >= prev_cursor
                prev_cursor = state.processed_cursor

    @pytest.mark.asyncio
    async def test_overlap_includes_previous_tail(self, wired):
        """With overlap=2, consecutive windows should share 2 chunks."""
        pub, _, ingestor = wired
        windower = WindowBuilder(pub, window_size=4, min_new_chunks=2, overlap=2)
        state = SessionState(session_id="test")

        for i in range(8):
            await ingestor.ingest(state, f"word{i}")

        w1 = await windower.build_window(state)
        assert w1 is not None
        w2 = await windower.build_window(state)
        assert w2 is not None

        # The two windows should share some text (the overlapping chunks)
        w1_texts = set(w1.combined_text.split())
        w2_texts = set(w2.combined_text.split())
        shared = w1_texts & w2_texts
        assert len(shared) > 0, "No overlap between consecutive windows"

    @pytest.mark.asyncio
    async def test_recent_windows_capped_at_5(self, wired):
        """Memory safety: state shouldn't accumulate unlimited windows."""
        pub, _, ingestor = wired
        windower = WindowBuilder(pub, window_size=3, min_new_chunks=2, overlap=0)
        state = SessionState(session_id="test")

        for i in range(20):
            await ingestor.ingest(state, f"chunk {i}")
            if windower.has_ready_window(state):
                await windower.build_window(state)

        assert len(state.recent_windows) <= 5

