"""Replay runner — feeds transcript fixtures through the full pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from backend.artifacts.registry import ArtifactRegistry
from backend.artifacts.resolver import ArtifactResolver
from backend.domain.state import SessionState, SessionStore
from backend.orchestration.service import OrchestrationService
from backend.streaming.publisher import EventPublisher
from backend.streaming.subscribers import ConsoleSubscriber, RecorderSubscriber
from backend.transcript.ingest import ChunkIngestor
from backend.transcript.windowing import WindowBuilder


class ReplayRunner:
    """Replays a transcript fixture through the full backend pipeline.

    Usage:
        runner = ReplayRunner(llm=my_llm)
        recorder = await runner.run("backend/transcript/fixtures/intro_to_llms.json")
        print(recorder.kinds)
    """

    def __init__(self, llm=None, verbose: bool = True) -> None:
        self._llm = llm
        self._verbose = verbose

    async def run(
        self,
        fixture_path: str | Path,
        lecture_id: str = "replay",
    ) -> RecorderSubscriber:
        """Run a full replay from a fixture file.

        The fixture file should be a JSON array of strings (transcript chunks).

        Returns the RecorderSubscriber with all emitted events.
        """
        # Load fixture
        fixture_path = Path(fixture_path)
        with open(fixture_path, "r", encoding="utf-8") as f:
            chunks_text: list[str] = json.load(f)

        # Wire up components
        publisher = EventPublisher()
        recorder = RecorderSubscriber()
        publisher.subscribe(recorder)
        if self._verbose:
            publisher.subscribe(ConsoleSubscriber())

        store = SessionStore()
        state = store.create(lecture_id=lecture_id)

        ingestor = ChunkIngestor(publisher)
        windower = WindowBuilder(publisher, window_size=6, min_new_chunks=3)
        registry = ArtifactRegistry()
        registry.load()
        resolver = ArtifactResolver(registry, publisher)
        orchestration = OrchestrationService(
            registry=registry,
            resolver=resolver,
            publisher=publisher,
            llm=self._llm,
        )

        # Replay chunks
        for text in chunks_text:
            await ingestor.ingest(state, text, source="replay")

            # Check if a window is ready
            if windower.has_ready_window(state):
                window = await windower.build_window(state)
                if window:
                    await orchestration.process_window(state, window)

        return recorder

