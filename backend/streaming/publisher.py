"""Event publisher with pluggable subscribers."""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from backend.domain.models import BackendEvent


# Subscriber is any async callable that takes a BackendEvent
Subscriber = Callable[[BackendEvent], Awaitable[None]]


class EventPublisher:
    """Broadcasts BackendEvents to registered subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self._subscribers = [s for s in self._subscribers if s is not subscriber]

    async def publish(self, event: BackendEvent) -> None:
        """Broadcast event to all subscribers concurrently."""
        if not self._subscribers:
            return
        await asyncio.gather(
            *(sub(event) for sub in self._subscribers),
            return_exceptions=True,
        )

