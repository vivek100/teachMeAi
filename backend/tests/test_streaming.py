"""Tests for session event persistence and websocket streaming."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.domain.models import BackendEvent
from backend.domain.state import SessionStore
from backend.streaming.subscribers import SessionStoreSubscriber


class TestSessionStoreSubscriber:
    def test_published_events_are_persisted_on_session_state(self):
        store = SessionStore()
        state = store.create("lecture")
        subscriber = SessionStoreSubscriber(store, max_events=3)

        async def publish_events():
            for index in range(5):
                await subscriber(BackendEvent(
                    session_id=state.session_id,
                    kind="chunk_ingested",
                    payload={"index": index},
                ))

        asyncio.run(publish_events())

        assert len(state.emitted_events) == 3
        assert [event.payload["index"] for event in state.emitted_events] == [2, 3, 4]


class TestWebsocketStreaming:
    def test_websocket_receives_live_chunk_event(self):
        app = create_app()

        with TestClient(app) as client:
            created = client.post("/sessions", json={"lecture_id": "intro_to_llms"})
            assert created.status_code == 200
            session_id = created.json()["session_id"]

            with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
                snapshot = websocket.receive_json()
                assert snapshot["type"] == "snapshot"
                assert snapshot["session_id"] == session_id
                assert snapshot["events"] == []
                assert snapshot["batches"] == []

                ingested = client.post(
                    f"/sessions/{session_id}/chunks",
                    json={"text": "hello live stream", "source": "user_command"},
                )
                assert ingested.status_code == 200

                streamed = websocket.receive_json()
                assert streamed["type"] == "event"
                assert streamed["session_id"] == session_id
                assert streamed["event"]["kind"] == "chunk_ingested"
                assert streamed["event"]["payload"]["text"] == "hello live stream"
