# ChalkAI — Agent Architecture (Final)

**Pattern:** Blackboard Architecture
**Backend:** FastAPI (async, WebSocket streaming) + Railtracks
**Frontend:** tldraw Agent Starter Kit + assistant-ui
**LLM:** Gemini (large context window, manage via message history)

---

## 1. The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (React / Next.js)                                     │
│                                                                 │
│  ┌──────────────────┐        ┌────────────────────────────────┐ │
│  │  assistant-ui     │        │  tldraw Agent Starter Kit      │ │
│  │  - Mic capture    │        │  - editor.createShapes()       │ │
│  │  - Transcript     │        │  - editor.deleteShapes()       │ │
│  │  - Agent status   │        │  - editor.setCamera()          │ │
│  │  - SSE listener   │        │  - AgentActionUtil (built-in)  │ │
│  └────────┬──────────┘        │  - PromptPartUtil (context)    │ │
│           │                   │  - useTldrawAgent() hook       │ │
│           │                   └──────────┬─────────────────────┘ │
│           └──────────┬───────────────────┘                       │
│                      │                                           │
└──────────────────────┼───────────────────────────────────────────┘
                       │  WebSocket (bidirectional)
                       │  ↑ speech chunks, canvas state snapshots
                       │  ↓ agent actions (SSE stream), status updates
┌──────────────────────┼───────────────────────────────────────────┐
│  BACKEND (FastAPI + Railtracks)                                  │
│                      │                                           │
│   ┌──────────────────▼───────────────────┐                       │
│   │  WebSocket Manager                    │                       │
│   │  /ws/session — handles all comms      │                       │
│   └──────────────────┬───────────────────┘                       │
│                      │                                           │
│   ┌──────────────────▼───────────────────┐                       │
│   │         BLACKBOARD (rt.context)       │                       │
│   │                                       │                       │
│   │  📜 transcript_journal               │                       │
│   │  📋 canvas_state                     │                       │
│   │  📖 lecture_notes                    │                       │
│   │  🧠 orchestrator_memory             │                       │
│   │  🎨 artifact_registry               │                       │
│   └──────┬───────────┬───────────────────┘                       │
│          │           │                                           │
│   ┌──────▼──────┐  ┌─▼─────────────────────┐                    │
│   │ Orchestrator│  │ Worker Pool            │                    │
│   │ Loop        │  │ (asyncio.TaskGroup)    │                    │
│   │ (ReAct-     │  │                        │                    │
│   │  style)     │  │  ┌─────────┐           │                    │
│   │             │──│  │Worker A │ region=X  │                    │
│   │ Maintains   │  │  └─────────┘           │                    │
│   │ message     │  │  ┌─────────┐           │                    │
│   │ history     │  │  │Worker B │ region=Y  │                    │
│   └─────────────┘  │  └─────────┘           │                    │
│                    └────────────────────────┘                    │
│                                                                  │
│   ┌──────────────────────────────────────────┐                   │
│   │  LLM Layer (Gemini via DO GenAI or       │                   │
│   │  direct API — OpenAI-compatible)         │                   │
│   └──────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. The Blackboard — Five Living Documents in rt.context

All agents read and write to shared state. No direct agent-to-agent messaging.

### 2.1 transcript_journal

```python
{
    "chunks": [
        {"text": "today we're going to talk about LLMs", "ts": 0.0, "idx": 0},
        {"text": "let's start with tokens", "ts": 18.0, "idx": 1},
        ...
    ],
    "cursor": 4,           # orchestrator has processed up to here
    "window_size": 8,      # rolling window for orchestrator context
}
```

**Append-only.** Frontend pushes new chunks via WebSocket. Orchestrator advances
cursor after processing. Chunks behind the cursor are NOT deleted — they stay in
the journal for the full session — but the orchestrator only includes the window
in its LLM prompt context.

### 2.2 canvas_state

```python
{
    "camera": {
        "region": "embedding_zone",
        "zoom": 0.8,
        "locked": False,
        "locked_by": None
    },
    "regions": {
        "intro_overview":    {"status": "complete", "shape_count": 3, "locked_by": None},
        "tokenisation_zone": {"status": "complete", "shape_count": 7, "locked_by": None},
        "embedding_zone":    {"status": "active",   "shape_count": 2, "locked_by": "worker_003"},
        "attention_zone":    {"status": "idle",      "shape_count": 0, "locked_by": None},

### 2.3 orchestrator_memory (ReAct History)

This solves the "losing the decision trail" problem. The orchestrator maintains a
full ReAct-style message history — **Thought → Action → Observation** — across
its lifetime. Unlike LangGraph's `StateGraph`, this is a simple list stored in
`rt.context` that gets passed to every orchestrator LLM call.

```python
{
    "history": [
        {
            "role": "system",
            "content": "You are the ChalkAI orchestrator..."
        },
        {
            "role": "user",          # injected from transcript
            "content": "[Chunks 0-3]: 'today we're going to... tokens'",
        },
        {
            "role": "assistant",     # Thought
            "content": "The lecturer is introducing tokenisation. I should draw a BPE grid.",
        },
        {
            "role": "tool_call",     # Action
            "name": "spawn_worker",
            "args": {"region": "tokenisation_zone", "task": "Draw BPE byte-pair grid..."}
        },
        {
            "role": "tool_result",   # Observation
            "content": "worker_001 spawned, ETA 3s"
        },
        {
            "role": "user",          # next transcript window
            "content": "[Chunks 4-7]: 'now embeddings convert tokens into vectors'",
        },
        {
            "role": "assistant",     # Thought
            "content": "Lecturer moved to embeddings. worker_001 finished. Spawn new worker for scatter plot.",
        },
        # ...
    ],
    "max_history_turns": 40,  # prune oldest user+assistant pairs when exceeded
}
```

**Why this works with Gemini's large context:**
- At ~40 turns, the history is still well under 100K tokens.
- We prune by dropping the oldest user+assistant pairs (FIFO) when limit is hit.
- The full history gives the orchestrator *continuity* — it remembers what it
  already drew and what the lecturer already covered.

### 2.4 lecture_notes (Pre-loaded context)

```python
{
    "title": "Intro to Transformers",
    "sections": [
        {
            "topic": "tokenisation",
            "notes": "BPE splits text into sub-word tokens...",
            "keywords": ["token", "BPE", "byte-pair", "vocabulary"],
            "artifact_id": "artifact_bpe_grid"
        },
        {
            "topic": "embeddings",
            "notes": "Each token ID maps to a learned vector...",
            "keywords": ["embedding", "vector", "dimension"],
            "artifact_id": "artifact_scatter_plot"
        },
        # ...
    ]
}
```

**Pre-loaded at session start.** The orchestrator uses keyword matching on
incoming transcript chunks to find relevant sections and pass them to workers.

### 2.5 artifact_registry (Pre-saved tldraw Artifacts)

```python
{
    "artifact_bpe_grid": {
        "description": "A 4x4 grid showing BPE tokenization of 'understanding'",
        "tldraw_shapes": [
            # Pre-defined tldraw shape JSON — can be pasted directly onto canvas
            {"type": "geo", "props": {"geo": "rectangle", "w": 80, "h": 40, ...}},
            {"type": "text", "props": {"text": "un", ...}},
            # ... more shapes
        ],
        "placement": {"region": "tokenisation_zone", "offset_x": 0, "offset_y": 0}
    },
    "artifact_scatter_plot": {
        "description": "A scatter plot of 2D embedding vectors",
        "tldraw_shapes": [...],
        "placement": {"region": "embedding_zone", "offset_x": 0, "offset_y": 0}
    }
}
```

**Why this is fast:** Workers don't need the LLM to *generate* shapes from
scratch. For common visuals, the worker just reads the artifact, applies position
offsets for the target region, and sends the shape JSON over WebSocket. The
tldraw frontend calls `editor.createShapes(shapes)` — instant rendering.

Workers CAN still generate novel shapes via LLM when no artifact matches.

---

## 3. The Orchestrator — ReAct Loop

```python
@rt.agent_node
async def orchestrator(session_ws, blackboard):
    """
    Runs continuously. Wakes on new transcript chunks or worker status changes.
    Uses ReAct pattern: Thought → Action → Observation → repeat.
    """
    tools = [
        spawn_worker,        # start a new drawing worker
        move_camera,         # pan/zoom the canvas
        cancel_worker,       # abort a running worker
        update_worker,       # change a worker's instructions mid-flight
        search_notes,        # lookup lecture_notes by keyword
        find_artifact,       # lookup artifact_registry
        send_message,        # send a text message to the UI
    ]

    while session_active:
        # 1. Check for new transcript chunks
        new_chunks = get_unprocessed_chunks(blackboard["transcript_journal"])
        if not new_chunks:
            await asyncio.sleep(0.5)
            continue

        # 2. Build the prompt with ReAct history
        history = blackboard["orchestrator_memory"]["history"]
        history.append({
            "role": "user",
            "content": format_chunks(new_chunks)
                     + "\n\n" + format_canvas_state(blackboard["canvas_state"])
                     + "\n\n" + format_active_workers(blackboard["canvas_state"]["active_workers"])
        })

        # 3. Call LLM with tool definitions (ReAct-style), STREAM the response
        response = await llm.chat(
            model="gemini-2.0-flash",
            messages=history,
            tools=tools,
            stream=True,
        )

        # 4. Stream thinking to frontend AS IT ARRIVES
        thought_chunks = []
        async for chunk in response:
            if chunk.type == "text_delta":
                thought_chunks.append(chunk.text)
                await session_ws.send_json({
                    "type": "orchestrator_event",
                    "event": "thinking",
                    "content": chunk.text,   # partial, streamed
                    "is_delta": True
                })
        full_thought = "".join(thought_chunks)

        # 5. Record assistant response + execute tool calls
        history.append({"role": "assistant", "content": full_thought})
        if response.tool_calls:
            for tc in response.tool_calls:
                # Stream the action decision to frontend
                await session_ws.send_json({
                    "type": "orchestrator_event",
                    "event": "action",
                    "action": tc.name,
                    "args": tc.args
                })
                # Execute the tool
                result = await execute_tool(tc, blackboard, session_ws)
                # Record observation
                history.append({"role": "tool_call", "name": tc.name, "args": tc.args})
                history.append({"role": "tool_result", "content": str(result)})

        # 6. Advance cursor
        blackboard["transcript_journal"]["cursor"] = new_chunks[-1]["idx"] + 1

        # 7. Prune history if needed
        prune_history(history, max_turns=40)
```

---

## 4. tldraw — What It Is and How We Actually Use It

### The confusion cleared up:

tldraw's Agent Starter Kit is a **frontend React component** that includes its
own LLM agent loop. It has `useTldrawAgent(editor)` which calls an LLM and
manipulates the canvas. **We are NOT using its agent loop.** We are only using:

1. **The tldraw editor API** — `editor.createShapes()`, `editor.updateShapes()`,
   `editor.deleteShapes()`, `editor.setCamera()` — these are just JavaScript
   functions that manipulate the canvas. No LLM involved.
2. **The tldraw shape format** — the JSON structure for shapes (geo, text, arrow,
   draw, etc.) so our backend can generate valid shape definitions.
3. **The canvas itself** — the React `<Tldraw />` component rendered in the browser.

### The architecture is:

```
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND (Python/FastAPI) — THE BRAIN                           │
│                                                                 │
│  Orchestrator decides WHAT to draw                              │
│  Workers decide HOW to draw it (generate tldraw shape JSON)     │
│  Backend sends shape JSON commands over WebSocket               │
└────────────────────────┬────────────────────────────────────────┘
                         │ WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (React) — THE HANDS                                   │
│                                                                 │
│  Receives commands, calls editor.createShapes(shapes)           │
│  No LLM here. Just a dumb executor.                             │
│  Also: captures mic audio, sends speech chunks back             │
└─────────────────────────────────────────────────────────────────┘
```

### tldraw tools available to sub-agents (workers):

Workers generate these as structured JSON. The backend sends them over WebSocket.
The frontend has a simple dispatcher that calls the right editor method.

```python
# These are the TOOL SCHEMAS that the worker LLM can output.
# They map 1:1 to tldraw editor API calls.

TLDRAW_TOOLS = {
    "create_shapes": {
        "description": "Create one or more shapes on the canvas",
        "params": {
            "shapes": [
                {
                    "type": "geo | text | arrow | draw | line | note | frame",
                    "x": "number — canvas x position",
                    "y": "number — canvas y position",
                    "props": {
                        # For geo: {"geo": "rectangle|ellipse|triangle|...", "w": 200, "h": 100, "fill": "solid", "color": "blue"}
                        # For text: {"text": "Hello", "size": "m", "font": "sans", "color": "black"}
                        # For arrow: {"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 50}}
                        # For draw: {"segments": [{"points": [{"x":0,"y":0}, {"x":10,"y":5}...]}], "color": "red"}
                    }
                }
            ]
        }
    },
    "update_shapes": {
        "description": "Update properties of existing shapes by ID",
        "params": {"updates": [{"id": "shape_id", "props": {"color": "red"}}]}
    },
    "delete_shapes": {
        "description": "Delete shapes by ID",
        "params": {"shape_ids": ["id1", "id2"]}
    },
    "group_shapes": {
        "description": "Group shapes together",
        "params": {"shape_ids": ["id1", "id2"]}
    },
    "move_camera": {
        "description": "Pan and zoom the viewport",
        "params": {"x": "number", "y": "number", "zoom": "number (0.1 to 8)"}
    }
}
```

### Frontend dispatcher (simple switch statement):

```typescript
// This is ALL the frontend needs to do with incoming commands
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)

    switch (msg.type) {
        case "create_shapes":
            editor.createShapes(msg.shapes)
            break
        case "update_shapes":
            editor.updateShapes(msg.updates)
            break
        case "delete_shapes":
            editor.deleteShapes(msg.shape_ids.map(id => editor.getShape(id)))
            break
        case "move_camera":
            editor.setCamera({ x: msg.x, y: msg.y, z: msg.zoom })
            break
        case "orchestrator_event":
            // Display in assistant-ui panel (thinking, status, etc.)
            appendToChat(msg)
            break
    }
}
```

---

## 5. Streaming — Everything Gets Streamed

The previous plan only streamed the final status. That's wrong. Here's what
actually needs to stream to the frontend in real-time:

### WebSocket message types (Backend → Frontend):

```python
# 1. Orchestrator thinking (stream as it happens)
{"type": "orchestrator_event", "event": "thinking",
 "content": "Lecturer is discussing tokenisation. I should draw a BPE grid."}

# 2. Orchestrator action (when it decides to spawn/cancel/update)
{"type": "orchestrator_event", "event": "action",
 "action": "spawn_worker", "worker_id": "worker_003",
 "region": "tokenisation_zone", "task": "Draw BPE byte-pair encoding grid"}

# 3. Worker progress (as worker is drawing)
{"type": "worker_event", "worker_id": "worker_003", "event": "progress",
 "message": "Creating grid shapes...", "shapes_created": 4, "shapes_total": 12}

# 4. Canvas commands (actual shape mutations)
{"type": "create_shapes", "worker_id": "worker_003",
 "shapes": [{"type": "geo", "x": 100, "y": 200, ...}]}

# 5. Worker completion
{"type": "worker_event", "worker_id": "worker_003", "event": "done",
 "region": "tokenisation_zone", "summary": "Drew 12 shapes: BPE grid with token IDs"}

# 6. Worker asking for help (escalation)
{"type": "worker_event", "worker_id": "worker_003", "event": "needs_help",
 "reason": "Can't fit diagram in region, need more space or different layout"}

# 7. Camera move
{"type": "move_camera", "x": 500, "y": 0, "zoom": 0.8,
 "reason": "Panning to tokenisation zone"}
```

### WebSocket message types (Frontend → Backend):

```python
# 1. Speech chunk from mic
{"type": "speech_chunk", "text": "now let's talk about embeddings", "ts": 42.5}

# 2. Canvas state report (triggered on demand, not periodic)
{"type": "canvas_report", "shapes": [
    {"id": "shape:abc", "type": "geo", "x": 100, "y": 200, "props": {...}},
    ...
], "camera": {"x": 0, "y": 0, "z": 1}}

# 3. User direct command (typed in assistant-ui)
{"type": "user_command", "text": "draw an arrow from the tokeniser to embeddings"}
```

### What is "canvas_report" and when does it fire?

NOT periodic polling. The backend requests it when it needs visual context:

```python
# Backend sends this when orchestrator needs to "see" the canvas
await ws.send_json({"type": "request_canvas_report"})
# Frontend responds with the shape list + camera position
```

The orchestrator requests a canvas report:
- Before deciding what to draw (to avoid overlapping existing content)
- After a worker finishes (to verify the result)
- When the user asks "what's on the canvas?"

---

## 6. Spawn Worker — Structured Response Schema

The orchestrator's `spawn_worker` tool has a strict input/output schema so the
LLM always provides accurate context to the worker.

### spawn_worker input (what orchestrator provides):

```python
class SpawnWorkerInput(BaseModel):
    """Schema for the orchestrator's spawn_worker tool call."""
    region: str                 # canvas region to draw in (e.g. "tokenisation_zone")
    task: str                   # natural language description of what to draw
    artifact_id: str | None     # if a pre-saved artifact matches, use it
    context: str                # relevant lecture notes / transcript excerpt
    visual_style: str           # "diagram", "flowchart", "scatter_plot", "timeline", "freeform"
    shapes_hint: int            # estimated number of shapes (helps worker plan layout)
    priority: str               # "high" (draw now) | "low" (can wait)
```

### spawn_worker output (what goes back to orchestrator as observation):

```python
class SpawnWorkerResult(BaseModel):
    """Returned immediately when worker is spawned (not when it finishes)."""
    worker_id: str              # "worker_003"
    status: str                 # "spawned" | "blocked" (region locked) | "queued"
    region: str
    task: str
    estimated_duration_s: float # rough estimate based on shapes_hint
    message: str                # human-readable status
```

### Worker completion (written to blackboard, orchestrator reads on next loop):

```python
class WorkerCompletionReport(BaseModel):
    """Written to blackboard.canvas_state.completed_tasks when done."""
    worker_id: str
    region: str
    task: str
    status: str                 # "done" | "failed" | "needs_help"
    shapes_created: int
    shape_ids: list[str]        # IDs of shapes created (for future reference)
    error: str | None           # if failed, why
    help_request: str | None    # if needs_help, what it needs
    duration_s: float
```

### Worker escalation — asking for help:

If a worker gets stuck (e.g. can't figure out how to lay out a complex diagram),
it does NOT just fail silently. It writes a `needs_help` status:

```python
# Inside worker, when stuck:
blackboard["canvas_state"]["completed_tasks"].append({
    "worker_id": worker_id,
    "status": "needs_help",
    "help_request": "The attention matrix diagram needs a 4x4 grid but "
                    "the region only has space for 3 columns. Should I "
                    "resize the region or simplify to 3x3?",
    "region": region,
    ...
})
# Orchestrator sees this on its next loop iteration, decides what to do:
# - spawn a new worker with adjusted instructions
# - expand the region
# - tell the worker to simplify
```

---

## 7. Worker System Prompt — How to Use tldraw

Every worker gets this system prompt so the LLM knows how to generate valid
tldraw shapes:

```python
WORKER_SYSTEM_PROMPT = """
You are a ChalkAI drawing worker. Your job is to create visual diagrams on a
tldraw canvas by outputting structured shape commands.

## Available shape types and their props:

### geo (rectangles, ellipses, etc.)
{"type": "geo", "x": 100, "y": 200, "props": {
    "geo": "rectangle",  // rectangle | ellipse | triangle | diamond | pentagon | hexagon | octagon | star | cloud | heart | x-box | check-box | arrow-left | arrow-up | arrow-down | arrow-right
    "w": 200, "h": 100,  // width and height
    "fill": "solid",     // none | semi | solid | pattern
    "color": "blue",     // black | grey | light-violet | violet | blue | light-blue | yellow | orange | green | light-green | light-red | red | white
    "dash": "draw",      // draw | solid | dashed | dotted
    "size": "m",         // s | m | l | xl
    "text": "",          // optional text inside shape
    "font": "draw"       // draw | sans | serif | mono
}}

### text (standalone text labels)
{"type": "text", "x": 100, "y": 200, "props": {
    "text": "Hello World",
    "size": "m",         // s | m | l | xl
    "font": "sans",      // draw | sans | serif | mono
    "color": "black",
    "textAlign": "middle" // start | middle | end
}}

### arrow (connecting arrows)
{"type": "arrow", "x": 100, "y": 200, "props": {
    "start": {"x": 0, "y": 0},
    "end": {"x": 200, "y": 100},
    "color": "black",
    "arrowheadStart": "none",  // none | arrow | triangle | square | dot | diamond | inverted | bar | pipe
    "arrowheadEnd": "arrow",
    "text": ""                 // optional label on the arrow
}}

### draw (freehand strokes)
{"type": "draw", "x": 100, "y": 200, "props": {
    "segments": [{"type": "free", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 5}]}],
    "color": "red",
    "size": "m"
}}

### note (sticky note)
{"type": "note", "x": 100, "y": 200, "props": {
    "text": "Key concept here",
    "color": "yellow",     // yellow | violet | blue | green | orange | red | white
    "size": "m",
    "font": "sans"
}}

### frame (container/group label)
{"type": "frame", "x": 50, "y": 50, "props": {
    "w": 500, "h": 400,
    "name": "Tokenisation"  // displayed as frame title
}}

## Layout guidelines:
- Each region is approximately 800x600 pixels
- Leave 20px padding from region edges
- Use frames to group related shapes
- Use arrows to show relationships and flow
- Use text labels to annotate key concepts
- Place shapes top-to-bottom, left-to-right
- Keep it clean — fewer shapes with clear labels > many cluttered shapes

## Your output format:
Output a JSON array of shape objects. Each shape will be sent to tldraw's
editor.createShapes() method. Include an "id" field using format "shape:workerXXX_N"
so shapes can be referenced later.

## If you get stuck:
Set your status to "needs_help" and explain what you need. The orchestrator
will provide guidance or adjust your task.
"""
```

---

## 8. FastAPI WebSocket Endpoint (Revised)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
app = FastAPI()

@app.websocket("/ws/session")
async def session_handler(ws: WebSocket):
    await ws.accept()
    blackboard = init_blackboard(lecture_id="transformers_101")

    # Start orchestrator in background
    orch_task = asyncio.create_task(orchestrator(ws, blackboard))

    try:
        while True:
            msg = await ws.receive_json()

            if msg["type"] == "speech_chunk":
                chunk = {"text": msg["text"], "ts": msg["ts"],
                         "idx": len(blackboard["transcript_journal"]["chunks"])}
                blackboard["transcript_journal"]["chunks"].append(chunk)
                # Stream acknowledgment back
                await ws.send_json({"type": "ack", "chunk_idx": chunk["idx"]})

            elif msg["type"] == "canvas_report":
                # Frontend responding to our request_canvas_report
                blackboard["canvas_state"]["last_snapshot"] = {
                    "shapes": msg["shapes"],
                    "camera": msg["camera"],
                    "timestamp": time.time()
                }

            elif msg["type"] == "user_command":
                # Direct user instruction — inject into transcript journal
                # with a special flag so orchestrator treats it as a command
                chunk = {"text": msg["text"], "ts": time.time(),
                         "idx": len(blackboard["transcript_journal"]["chunks"]),
                         "is_command": True}
                blackboard["transcript_journal"]["chunks"].append(chunk)

    except WebSocketDisconnect:
        orch_task.cancel()
```

---

## 9. Data Flow Timeline (Revised)

```
t=0.0s  Lecturer: "today we're going to talk about tokenisation"
t=0.1s  assistant-ui mic → Web Speech API → text chunk
t=0.2s  WS → Backend: {type: "speech_chunk", text: "...tokenisation"}
t=0.3s  Backend appends to transcript_journal[0]

t=0.5s  Orchestrator loop wakes, reads chunk 0
t=0.6s  Backend → WS: {type: "orchestrator_event", event: "thinking",
            content: "Lecturer introducing tokenisation..."}
        [assistant-ui shows: "🤔 Thinking: Lecturer introducing tokenisation..."]

t=0.8s  Orchestrator calls Gemini with ReAct history + tools
t=1.2s  Gemini responds: Thought + tool_call(spawn_worker)
t=1.3s  Backend → WS: {type: "orchestrator_event", event: "action",
            action: "spawn_worker", region: "tokenisation_zone",
            task: "Draw BPE grid"}
        [assistant-ui shows: "🎨 Spawning worker in tokenisation zone..."]

t=1.4s  Worker starts — checks artifact_registry → finds "artifact_bpe_grid"
t=1.5s  Backend → WS: {type: "worker_event", event: "progress",
            message: "Using pre-saved BPE grid artifact"}
t=1.6s  Backend → WS: {type: "create_shapes", shapes: [...12 shapes...]}
        [tldraw canvas: BPE grid appears instantly]

t=1.7s  Backend → WS: {type: "move_camera", x: 0, y: 0, zoom: 0.8}
        [tldraw canvas: viewport pans to show the new diagram]

t=1.8s  Backend → WS: {type: "worker_event", event: "done",
            shapes_created: 12, summary: "BPE grid with token IDs"}
        [assistant-ui shows: "✅ Drew BPE grid (12 shapes)"]

t=1.9s  Worker writes completion to blackboard
t=2.0s  Next orchestrator loop — reads completion, records observation
```

---

## 10. Key Design Decisions

| Decision | Rationale |
|---|---|
| **FastAPI + WebSocket** | Bidirectional streaming. SSE is one-way; we need both speech→backend and actions→frontend |
| **Stream everything** | Orchestrator thinking, worker progress, canvas commands — ALL streamed in real-time |
| **ReAct history in rt.context** | Orchestrator never loses its decision trail. Full audit log of Thought→Action→Observation |
| **Gemini large context** | No need for aggressive pruning. 40 turns ≈ 20K tokens, well within 100K+ limit |
| **Pre-saved artifacts** | Sub-200ms drawing for common visuals. LLM generation is backup for novel content |
| **Region-based locking** | Multiple workers draw concurrently in different canvas regions without conflicts |
| **tldraw = thin executor** | Backend generates shape JSON. Frontend just calls `editor.createShapes()`. No LLM on frontend |
| **Canvas report on-demand** | Not periodic polling. Backend asks for it when orchestrator needs to "see" the canvas |
| **Worker escalation** | Workers can say "needs_help" — orchestrator re-plans instead of silent failure |
| **Structured schemas** | SpawnWorkerInput/Result/CompletionReport — LLM always gets typed, accurate context |
| **Blackboard pattern** | All agents share state via rt.context. No direct messaging = no coupling |

---

## 11. Railtracks Mapping

| Railtracks Primitive | ChalkAI Usage |
|---|---|
| `rt.context` | The Blackboard — all 5 living documents |
| `@rt.agent_node` | Orchestrator loop |
| `@rt.function_node` | Each tool (spawn_worker, move_camera, search_notes, etc.) |
| `rt.call()` | Worker calling LLM for shape generation |
| `rt.metrics` | Track latency per worker, orchestrator decision time |

