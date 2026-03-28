# TeachWithMeAI Backend Implementation Plan

## 1. Goal

Build the backend first.

Phase 1 should prove these things before any serious frontend work:

- transcript chunks can be ingested and accumulated
- a Railtracks-based orchestrator can reason over chunk windows
- the agent can choose between `wait`, `draw_artifact`, and `annotate`
- artifact selection and artifact instantiation work with test fixtures
- streaming events work end-to-end from backend logic
- the system is testable without tldraw or a browser

Frontend work starts only after the backend can run realistic simulations.

## 2. Scope of Backend Phase 1

### In scope

- FastAPI backend skeleton
- session lifecycle
- transcript chunk ingestion
- session state store
- Railtracks orchestrator agent
- artifact registry
- artifact instantiation engine
- backend streaming event bus
- replay/simulation runner
- unit tests and scenario tests

### Explicitly out of scope

- tldraw integration
- websocket browser client
- mic capture
- screenshot handling
- custom shapes
- full canvas shadow state synced from frontend

## 3. Backend-First Product Slice

The smallest useful system is:

1. feed transcript chunks into a session
2. batch them into a rolling window
3. ask the orchestrator what should happen
4. select a known artifact if possible
5. emit a stream of backend events representing the planned canvas actions
6. verify those events in tests

This lets us validate the core intelligence before we touch rendering.

## 4. Implementation Strategy

### 4.1 Start with a simulation harness

Do not start with live websocket traffic.

Start with:

- a local runner that replays transcript chunks from fixture files
- deterministic timestamps
- fake artifact registry
- fake event subscriber that records outputs

This will make iteration much faster.

### 4.2 Use Railtracks where it adds value

Use Railtracks for:

- `@rt.function_node` tool definitions
- `rt.agent_node(...)` orchestrator
- `rt.Session(context=...)`
- `await rt.call(...)`
- optional visualizer and saved run traces

Do not force Railtracks to own:

- FastAPI app lifecycle
- queueing layer
- state persistence layer
- event streaming transport

## 5. Phase 1 Architecture

```text
Transcript Fixtures / API Input
            |
            v
Chunk Ingestor
            |
            v
Session State Store
            |
            v
Orchestration Service
  - Railtracks Session
  - Orchestrator agent
  - backend tools
            |
            v
Artifact Resolver
            |
            v
Event Stream Publisher
            |
            v
Test Recorder / Console Subscriber / later WebSocket adapter
```

## 6. Core Data Models

Implement these first as Pydantic models.

### 6.1 TranscriptChunk

```python
class TranscriptChunk(BaseModel):
    chunk_id: str
    session_id: str
    text: str
    ts_start_ms: int
    ts_end_ms: int | None = None
    source: Literal["speech", "user_command", "replay"]
```

### 6.2 TranscriptWindow

```python
class TranscriptWindow(BaseModel):
    session_id: str
    start_chunk_id: str | None
    end_chunk_id: str | None
    chunks: list[TranscriptChunk]
    combined_text: str
```

### 6.3 ArtifactSpec

```python
class ArtifactSpec(BaseModel):
    artifact_id: str
    family: str
    version: str
    title: str
    description: str
    tags: list[str]
    parameters: dict[str, dict] = {}
    shape_template: list[dict]
```

### 6.4 OrchestratorDecision

```python
class OrchestratorDecision(BaseModel):
    intent: Literal["wait", "draw_artifact", "annotate", "review"]
    topic: str | None = None
    rationale: str
    artifact_query: str | None = None
    parameters: dict[str, str | int | float | bool] = {}
    confidence: float = 0.0
```

### 6.5 BackendEvent

```python
class BackendEvent(BaseModel):
    event_id: str
    session_id: str
    kind: Literal[
        "chunk_ingested",
        "window_ready",
        "decision_made",
        "artifact_selected",
        "artifact_instantiated",
        "stream_delta",
        "op_batch_ready",
        "warning",
        "error"
    ]
    payload: dict
    ts_ms: int
```

### 6.6 CanvasOpBatch

Even before frontend integration, define the target output shape.

```python
class CanvasOpBatch(BaseModel):
    batch_id: str
    session_id: str
    ops: list[dict]
    artifact_id: str | None = None
    source: Literal["artifact_engine", "fallback_generator", "annotation"]
```

## 7. Session State Model

Keep the state simple in phase 1.

```python
{
    "session_id": "...",
    "lecture_id": "...",
    "transcript_chunks": [],
    "processed_cursor": 0,
    "recent_windows": [],
    "active_topic": None,
    "recent_decisions": [],
    "artifact_registry_version": "v1",
    "pending_batches": [],
    "emitted_events": []
}
```

In memory is acceptable for phase 1.

## 8. Project Structure

```text
backend/
  app.py
  api/
    routes.py
    sessions.py
  domain/
    models.py
    state.py
  orchestration/
    agents.py
    prompts.py
    service.py
    tools.py
  artifacts/
    models.py
    registry.py
    resolver.py
    compiler.py
    fixtures/
  streaming/
    events.py
    publisher.py
    subscribers.py
  transcript/
    ingest.py
    windowing.py
    fixtures/
  simulation/
    replay.py
    scenarios.py
  tests/
    unit/
    integration/
```

## 9. Backend Components

### 9.1 Chunk ingestor

Responsibilities:

- append chunks to session state
- publish `chunk_ingested`
- determine when a new reasoning window is ready

Rules:

- support fixed-size rolling windows first
- later add semantic/topic-triggered windows

### 9.2 Windowing service

Start with something deterministic:

- window size: 4 to 8 chunks
- overlap: 2 chunks
- trigger reasoning when:
  - minimum new chunk count reached
  - or punctuation/topic boundary detected

### 9.3 Orchestration service

Responsibilities:

- build prompt input from current state
- invoke Railtracks orchestrator agent
- validate structured output
- publish `decision_made`

### 9.4 Artifact registry

Responsibilities:

- load artifact fixture files from disk
- index by `artifact_id`, `family`, `tags`
- return best match for a topic/query

Phase 1 registry can be plain JSON files.

### 9.5 Artifact resolver

Responsibilities:

- map orchestrator decision to concrete artifact
- inject parameters into fixture template
- emit `artifact_selected` and `artifact_instantiated`
- return `CanvasOpBatch`

### 9.6 Event publisher

Responsibilities:

- broadcast all backend events to subscribers
- support:
  - in-memory recorder
  - stdout logger
  - later websocket subscriber

## 10. Railtracks Plan

### 10.1 Initial tools

Build these as `@rt.function_node`.

- `search_notes(query: str) -> str`
- `get_recent_transcript() -> str`
- `get_recent_decisions() -> str`
- `find_matching_artifact(query: str) -> str`

Important:

- tools should return compact, serialization-safe payloads
- keep docstrings explicit so tool schemas are useful

### 10.2 First orchestrator agent

The first agent should be narrow.

Its only job:

- infer current teaching topic
- decide whether there is enough information to draw
- choose an artifact query if drawing is justified

It should not generate shape data.

### 10.3 First output schema

Use `output_schema=OrchestratorDecision`.

That forces the agent into a small decision surface and makes testing far easier.

### 10.4 Session context usage

Initialize Railtracks sessions with:

- lecture title
- note summary
- artifact families available
- session metadata

Use `rt.context` sparingly.

Prefer passing assembled prompts from app code over deep hidden context mutation.

## 11. Artifact Plan for Phase 1

The earlier architecture doc defines the long-term artifact system. For backend-first phase 1, use **test artifacts**.

### 11.1 Required test artifacts

Create 5 fixture artifacts:

- `token_grid_basic`
- `embedding_space_basic`
- `attention_matrix_basic`
- `transformer_stack_basic`
- `loss_curve_basic`

### 11.2 Fixture format

Keep it simple:

```json
{
  "artifact_id": "token_grid_basic",
  "family": "token_grid",
  "version": "v1",
  "tags": ["token", "bpe", "tokenization", "vocabulary"],
  "shape_template": [
    { "type": "frame", "props": { "name": "Tokenization" } }
  ]
}
```

### 11.3 What we are testing

In phase 1, artifacts are not about polished canvas rendering yet.

They are for testing:

- agent selection behavior
- parameter passing
- instantiation pipeline
- event streaming

## 12. Streaming Plan

Streaming should be validated in backend phase 1.

### 12.1 What to stream

Stream these events from the backend pipeline:

- chunk accepted
- reasoning window formed
- orchestrator started
- reasoning delta if supported
- decision completed
- artifact selected
- op batch generated

### 12.2 Transport for phase 1

Do not start with websocket streaming.

Start with:

- async in-memory subscriber
- console stream output
- test recorder

Then add websocket transport as an adapter later.

### 12.3 Why

This lets you prove the product loop without browser complexity.

## 13. API Plan

Keep the API narrow at first.

### 13.1 Initial endpoints

- `POST /sessions`
- `POST /sessions/{session_id}/chunks`
- `POST /sessions/{session_id}/replay`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/events`
- `GET /artifacts`

### 13.2 Initial non-HTTP interface

Also build a direct Python replay entrypoint:

```python
await replay_transcript_fixture(
    session_id="demo",
    fixture_path="backend/transcript/fixtures/intro_to_llms.json"
)
```

This will be the fastest dev loop.

## 14. Testing Strategy

Backend-first only works if it is simulation-heavy.

### 14.1 Unit tests

Write unit tests for:

- chunk ingestion
- rolling window creation
- artifact lookup
- artifact instantiation
- event publication
- decision schema validation

### 14.2 Integration tests

Write scenario tests for:

- tokenization transcript leads to `token_grid_basic`
- attention transcript interrupts previous topic and leads to `attention_matrix_basic`
- vague transcript leads to `wait`
- repeated chunks do not cause repeated duplicate decisions

### 14.3 Golden tests

Store expected `BackendEvent` sequences for a few fixtures.

That gives you regression protection even before the frontend exists.

## 15. Implementation Order

### Step 1

Create backend package structure and domain models.

Deliverable:

- app imports cleanly
- models compile

### Step 2

Build in-memory session store and chunk ingestor.

Deliverable:

- chunks can be posted and retrieved

### Step 3

Build rolling window logic and simulation runner.

Deliverable:

- fixture transcript produces deterministic windows

### Step 4

Build artifact fixture registry and resolver.

Deliverable:

- topic query resolves to known artifact fixture

### Step 5

Build first Railtracks orchestrator agent with structured output.

Deliverable:

- transcript window returns `OrchestratorDecision`

### Step 6

Connect orchestration service to artifact resolver.

Deliverable:

- transcript window produces `CanvasOpBatch`

### Step 7

Build event publisher and streaming recorder.

Deliverable:

- end-to-end replay emits event sequence

### Step 8

Add FastAPI endpoints over the same services.

Deliverable:

- API-driven session replay works

### Step 9

Add Railtracks visualizer-compatible runs and logs.

Deliverable:

- orchestrator runs are inspectable during debugging

## 16. Success Criteria for Backend Phase 1

We are done with backend phase 1 when:

- a transcript fixture can be replayed through the backend
- the orchestrator emits structured decisions
- at least 5 artifact fixtures are selectable by the agent
- event streaming shows the backend pipeline step-by-step
- integration tests cover core scenarios
- no frontend code is required to validate the core loop

## 17. Phase 2 Handoff to Frontend

Only after phase 1 succeeds should frontend phase 2 begin.

Frontend phase 2 will consume:

- `CanvasOpBatch`
- backend event stream
- session metadata

At that point the frontend is mainly:

- websocket adapter
- tldraw op dispatcher
- UI for transcript and agent status

The risk is much lower because the backend semantics are already proven.

## 18. Immediate Next Tasks

The first concrete tasks should be:

1. Create backend folders and base Pydantic models.
2. Add transcript fixture files for two lecture scenarios.
3. Add five artifact fixture files.
4. Implement in-memory session store.
5. Implement replay runner.
6. Build first Railtracks orchestrator with `OrchestratorDecision`.
7. Add event recorder integration test.

## 19. Final Recommendation

Do not build the canvas first.

Build TeachWithMeAI as a backend simulation-first system where:

- transcript chunks are first-class inputs
- artifacts are first-class backend fixtures
- streaming is first-class backend behavior
- Railtracks is used for narrow structured decisions

Then connect the frontend once the agent loop is already trustworthy.
