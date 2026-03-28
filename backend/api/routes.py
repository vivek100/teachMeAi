"""FastAPI routes for the TeachWithMeAI backend."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.domain.state import SessionStore

router = APIRouter()

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

    result = {"chunk_id": chunk.chunk_id, "window_triggered": False, "batch": None}

    if windower and windower.has_ready_window(state):
        window = await windower.build_window(state)
        if window and orchestration:
            result["window_triggered"] = True
            batch = await orchestration.process_window(state, window)
            if batch:
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
    return {"events": [e.model_dump() for e in state.emitted_events]}


@router.get("/sessions/{session_id}/batches")
async def get_batches(session_id: str):
    assert _store is not None
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(404, f"Session {session_id} not found")
    return {"batches": [b.model_dump() for b in state.pending_batches]}


@router.get("/artifacts")
async def list_artifacts():
    registry = _deps.get("registry")
    if not registry:
        return {"artifacts": []}
    return {"artifacts": [a.model_dump() for a in registry.list_all()]}


@router.get("/health")
async def health():
    return {"status": "ok"}
