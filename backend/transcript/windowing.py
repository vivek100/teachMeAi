"""Rolling window logic over transcript chunks."""

from __future__ import annotations

from backend.domain.models import BackendEvent, TranscriptWindow
from backend.domain.state import SessionState
from backend.streaming.publisher import EventPublisher


class WindowBuilder:
    """Creates rolling windows over transcript chunks.

    A new window is ready when at least `min_new_chunks` unprocessed
    chunks have accumulated since the last window.
    """

    def __init__(
        self,
        publisher: EventPublisher,
        window_size: int = 6,
        min_new_chunks: int = 3,
        overlap: int = 2,
    ) -> None:
        self._publisher = publisher
        self.window_size = window_size
        self.min_new_chunks = min_new_chunks
        self.overlap = overlap

    def has_ready_window(self, state: SessionState, force: bool = False) -> bool:
        """Check whether enough new chunks exist to form a window.

        If *force* is True (e.g. for user_command sources), a single
        unprocessed chunk is sufficient.
        """
        unprocessed = len(state.transcript_chunks) - state.processed_cursor
        if force:
            return unprocessed >= 1
        return unprocessed >= self.min_new_chunks

    async def build_window(self, state: SessionState, force: bool = False) -> TranscriptWindow | None:
        """Build the next window if enough chunks are available.

        Advances the processed_cursor by (window_size - overlap) so
        subsequent windows overlap by `overlap` chunks.
        """
        if not self.has_ready_window(state, force=force):
            return None

        total = len(state.transcript_chunks)
        # Start from cursor, take up to window_size chunks
        start = max(0, state.processed_cursor - self.overlap)
        end = min(total, start + self.window_size)
        chunks = state.transcript_chunks[start:end]

        window = TranscriptWindow(
            session_id=state.session_id,
            start_chunk_id=chunks[0].chunk_id if chunks else None,
            end_chunk_id=chunks[-1].chunk_id if chunks else None,
            chunks=chunks,
            combined_text=" ".join(c.text for c in chunks),
        )

        # Advance cursor past the non-overlapping portion
        advance = max(1, len(chunks) - self.overlap)
        state.processed_cursor = min(total, state.processed_cursor + advance)

        state.recent_windows.append(window)
        # Keep only last 5 windows in memory
        if len(state.recent_windows) > 5:
            state.recent_windows = state.recent_windows[-5:]

        await self._publisher.publish(BackendEvent(
            session_id=state.session_id,
            kind="window_ready",
            payload={
                "combined_text": window.combined_text,
                "chunk_count": len(chunks),
                "start_chunk_id": window.start_chunk_id,
                "end_chunk_id": window.end_chunk_id,
            },
        ))

        return window

