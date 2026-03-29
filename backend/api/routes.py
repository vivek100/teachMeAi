"""FastAPI routes for the TeachWithMeAI backend."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.domain.state import SessionStore
from backend.logging_utils import get_logger

router = APIRouter()
logger = get_logger("api.routes")

# These will be injected by the app factory
_store: SessionStore | None = None
_deps: dict = {}


def init_routes(store: SessionStore, deps: dict) -> None:
    """Inject runtime dependencies into the routes module."""
    global _store, _deps
    _store = store
    _deps = deps


class CreateSessionRequest(BaseModel):
    lecture_id: str = ""


class ChunkRequest(BaseModel):
    text: str
    source: str = "speech"


@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    assert _store is not None
    state = _store.create(lecture_id=req.lecture_id)
    logger.info("session created | session_id=%s | lecture_id=%s", state.session_id, state.lecture_id)
    return {"session_id": state.session_id, "lecture_id": state.lecture_id}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    assert _store is not None
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(404, f"Session {session_id} not found")
    return {
        "session_id": state.session_id,
        "lecture_id": state.lecture_id,
        "chunk_count": len(state.transcript_chunks),
        "processed_cursor": state.processed_cursor,
        "active_topic": state.active_topic,
        "decision_count": len(state.recent_decisions),
        "pending_batch_count": len(state.pending_batches),
    }


@router.post("/sessions/{session_id}/chunks")
async def ingest_chunk(session_id: str, req: ChunkRequest):
    assert _store is not None
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(404, f"Session {session_id} not found")

    ingestor = _deps.get("ingestor")
    windower = _deps.get("windower")
    orchestration = _deps.get("orchestration")

    if not ingestor:
        raise HTTPException(500, "Ingestor not configured")

    chunk = await ingestor.ingest(state, req.text, source=req.source)
    logger.info(
        "chunk ingested | session_id=%s | chunk_id=%s | source=%s | text_len=%s",
        session_id,
        chunk.chunk_id,
        req.source,
        len(req.text),
    )

    result = {"chunk_id": chunk.chunk_id, "window_triggered": False, "batch": None}

    force_window = req.source == "user_command"
    if windower and windower.has_ready_window(state, force=force_window):
        window = await windower.build_window(state, force=force_window)
        if window and orchestration:
            logger.info(
                "window ready | session_id=%s | chunk_count=%s | text_len=%s",
                session_id,
                len(window.chunks),
                len(window.combined_text),
            )
            result["window_triggered"] = True
            batch = await orchestration.process_window(state, window)
            if batch:
                logger.info(
                    "batch created | session_id=%s | batch_id=%s | artifact_id=%s | op_count=%s",
                    session_id,
                    batch.batch_id,
                    batch.artifact_id,
                    len(batch.ops),
                )
                result["batch"] = {
                    "batch_id": batch.batch_id,
                    "op_count": len(batch.ops),
                    "artifact_id": batch.artifact_id,
                }

    return result


@router.get("/sessions/{session_id}/events")
async def get_events(session_id: str):
    assert _store is not None
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(404, f"Session {session_id} not found")
    logger.debug("events requested | session_id=%s | count=%s", session_id, len(state.emitted_events))
    return {"events": [e.model_dump() for e in state.emitted_events]}


@router.get("/sessions/{session_id}/batches")
async def get_batches(session_id: str):
    assert _store is not None
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(404, f"Session {session_id} not found")
    logger.debug("batches requested | session_id=%s | count=%s", session_id, len(state.pending_batches))
    return {"batches": [b.model_dump() for b in state.pending_batches]}


@router.get("/artifacts")
async def list_artifacts():
    registry = _deps.get("registry")
    if not registry:
        return {"artifacts": []}
    logger.debug("artifacts requested | count=%s", len(registry.list_all()))
    return {"artifacts": [a.model_dump() for a in registry.list_all()]}


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.websocket("/ws/sessions/{session_id}")
async def session_stream(session_id: str, websocket: WebSocket):
    assert _store is not None

    state = _store.get(session_id)
    if state is None:
        await websocket.close(code=4404, reason=f"Session {session_id} not found")
        return

    stream_hub = _deps.get("stream_hub")
    if stream_hub is None:
        await websocket.close(code=1011, reason="Stream hub not configured")
        return

    logger.info("ws connect | session_id=%s", session_id)
    await stream_hub.connect(session_id, websocket)
    await stream_hub.send_snapshot(
        session_id,
        websocket,
        events=[event.model_dump(mode="json") for event in state.emitted_events],
        batches=[batch.model_dump(mode="json") for batch in state.pending_batches],
    )
    logger.info(
        "ws snapshot sent | session_id=%s | event_count=%s | batch_count=%s",
        session_id,
        len(state.emitted_events),
        len(state.pending_batches),
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("ws disconnect | session_id=%s", session_id)
        await stream_hub.disconnect(session_id, websocket)
