"""Transcript chunk ingestion service."""

from __future__ import annotations

from backend.domain.models import BackendEvent, TranscriptChunk
from backend.domain.state import SessionState
from backend.streaming.publisher import EventPublisher


class ChunkIngestor:
    """Appends transcript chunks to session state and publishes events."""

    def __init__(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    async def ingest(self, state: SessionState, text: str, source: str = "speech") -> TranscriptChunk:
        """Ingest a single text chunk into the session.

        Returns the created TranscriptChunk.
        """
        chunk = TranscriptChunk(
            session_id=state.session_id,
            text=text,
            source=source,  # type: ignore[arg-type]
        )
        state.transcript_chunks.append(chunk)

        await self._publisher.publish(BackendEvent(
            session_id=state.session_id,
            kind="chunk_ingested",
            payload={"chunk_id": chunk.chunk_id, "text": text, "source": source},
        ))

        return chunk

