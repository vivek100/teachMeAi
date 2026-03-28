"""Built-in event subscribers for development and testing."""

from __future__ import annotations

import json
import sys

from backend.domain.models import BackendEvent


class ConsoleSubscriber:
    """Prints events to stdout for development."""

    async def __call__(self, event: BackendEvent) -> None:
        ts = event.ts_ms
        print(f"[{ts}] {event.kind}: {json.dumps(event.payload, default=str)[:200]}", file=sys.stdout)


class RecorderSubscriber:
    """Records events in memory for testing / assertions."""

    def __init__(self) -> None:
        self.events: list[BackendEvent] = []

    async def __call__(self, event: BackendEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def filter_kind(self, kind: str) -> list[BackendEvent]:
        return [e for e in self.events if e.kind == kind]

    @property
    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]

