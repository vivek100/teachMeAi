"""WebSocket fanout for per-session backend events."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket

from backend.domain.models import BackendEvent
from backend.logging_utils import get_logger

logger = get_logger("stream.ws")


class SessionStreamHub:
    """Broadcasts backend events to all connected sockets for a session."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)
            logger.debug(
                "client connected | session_id=%s | client_count=%s",
                session_id,
                len(self._connections[session_id]),
            )

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(session_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(session_id, None)
                logger.debug("client disconnected | session_id=%s | client_count=0", session_id)
            else:
                logger.debug(
                    "client disconnected | session_id=%s | client_count=%s",
                    session_id,
                    len(sockets),
                )

    async def send_snapshot(
        self,
        session_id: str,
        websocket: WebSocket,
        *,
        events: list[dict],
        batches: list[dict],
    ) -> None:
        logger.debug(
            "sending snapshot | session_id=%s | event_count=%s | batch_count=%s",
            session_id,
            len(events),
            len(batches),
        )
        await websocket.send_json({
            "type": "snapshot",
            "session_id": session_id,
            "events": events,
            "batches": batches,
        })

    async def __call__(self, event: BackendEvent) -> None:
        payload = {
            "type": "event",
            "session_id": event.session_id,
            "event": event.model_dump(mode="json"),
        }

        async with self._lock:
            sockets = list(self._connections.get(event.session_id, ()))

        if not sockets:
            return

        logger.debug(
            "broadcast event | session_id=%s | kind=%s | socket_count=%s",
            event.session_id,
            event.kind,
            len(sockets),
        )

        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                active = self._connections.get(event.session_id)
                if not active:
                    return
                for websocket in stale:
                    active.discard(websocket)
                if not active:
                    self._connections.pop(event.session_id, None)
