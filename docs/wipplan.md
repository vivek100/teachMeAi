# AI Lecture Whiteboard — Requirements & Agent Architecture

**Project codename:** ChalkAI  
**Type:** Hackathon demo  
**Stack:** AssistantUI · RailTracks · tldraw · DigitalOcean GenAI  

---

## 1. Overview

ChalkAI is a real-time AI co-presenter tool. While a lecturer speaks, an AI agent listens to the voice stream and autonomously draws annotations, diagrams, and visual aids on an infinite tldraw canvas — functioning like an AI operating a whiteboard on the lecturer's behalf.

The primary demo scenario is an "Intro to LLMs" lecture in the style of Andrej Karpathy: dense with diagrams, arrows, annotated neural network layers, token visualisations, and matrix illustrations drawn progressively as topics are introduced.

---

## 2. Goals

| Goal | Description |
|---|---|
| Real-time | Agent reacts to live speech within 2–4 seconds of a new concept being introduced |
| Context-aware | Agent knows the full lecture notes and uses them to predict/prepare visuals |
| Interruptible | When the lecture shifts topic, the agent stops the current drawing task and redirects |
| Spatially coherent | Related visuals are grouped in canvas regions; the camera navigates meaningfully |
| Demo-ready | Single-screen UI that is visually impressive for a hackathon audience |

---

## 3. Non-Goals (for hackathon scope)

- Multi-user / collaborative sessions
- Persistent session storage across page reloads
- Full production error handling and retry logic
- Mobile support
- Authentication / user accounts

---

## 4. Functional Requirements

### 4.1 Voice Input

- FR-01: System continuously captures microphone audio via browser Web Speech API in streaming mode
- FR-02: Partial transcripts are emitted as chunks and sent to the backend in real time over WebSocket
- FR-03: The full transcript for the session is accumulated and visible in the UI sidebar
- FR-04: Lecturer can pause/resume voice capture with a single button
- FR-05: A visual "listening" indicator shows when voice capture is active

### 4.2 Canvas

- FR-06: tldraw infinite canvas is the primary display, occupying ~70% of the UI
- FR-07: AI can create text annotations, geometric shapes, arrows, and frames on the canvas
- FR-08: AI can place pre-designed visual assets (neural net diagrams, matrix illustrations, token grids) from the asset library
- FR-09: AI can control the camera — zoom to fit a region, pan to a new area, zoom into a specific shape
- FR-10: Canvas is divided into named spatial regions that map to lecture sections (e.g. "Tokenisation Zone", "Attention Zone", "Training Zone")
- FR-11: The structured state of the canvas (all shapes, positions, labels) is available as JSON to the agent at all times
- FR-12: A screenshot of the current viewport is available to the agent on demand

### 4.3 Agent Behaviour

- FR-13: Agent receives continuous speech stream and decides whether to act, continue current task, or redirect
- FR-14: Agent can spawn a canvas-drawing sub-task and let it run independently while monitoring new speech
- FR-15: Agent can cancel an in-progress drawing task if the lecture has moved on
- FR-16: Agent has the full lecture notes loaded as context for all decisions
- FR-17: Agent uses canvas structure JSON as its primary spatial reference
- FR-18: Agent uses canvas screenshot as secondary visual verification
- FR-19: Agent streams its drawing tool calls back to the frontend over WebSocket

### 4.4 Asset Library

- FR-20: A library of pre-designed SVG visuals for LLM concepts is stored on DigitalOcean Spaces
- FR-21: Agent can reference and place any asset by name
- FR-22: Assets include: transformer block diagram, attention matrix, tokenisation grid, softmax curve, embedding space scatter, feedforward network, training loss curve

---

## 5. System Architecture

```
┌────────────────────────────────────────────────────┐
│  FRONTEND  (React / Next.js)                       │
│                                                    │
│  ┌──────────────────┐   ┌───────────────────────┐  │
│  │  AssistantUI     │   │  tldraw Canvas        │  │
│  │  - Mic capture   │   │  - Infinite canvas    │  │
│  │  - Transcript    │   │  - Shape API          │  │
│  │    sidebar       │   │  - Camera control     │  │
│  │  - Agent status  │   │  - Store snapshot     │  │
│  └────────┬─────────┘   └──────────┬────────────┘  │
│           │                        │               │
│           └──────────┬─────────────┘               │
│                      │  WebSocket bridge            │
└──────────────────────┼────────────────────────────┘
                       │ ↑ speech chunks, canvas state
                       │ ↓ tool calls (createShapes, camera)
┌──────────────────────┼────────────────────────────┐
│  BACKEND  (Python / RailTracks)                   │
│                      │                            │
│        ┌─────────────▼────────────┐               │
│        │  Transcript Buffer       │               │
│        │  asyncio.Queue           │               │
│        │  append-only, full log   │               │
│        └─────────────┬────────────┘               │
│                      │ new chunk event             │
│        ┌─────────────▼────────────┐               │
│        │  Orchestrator Agent      │               │
│        │  - Vision model          │               │
│        │  - Reads transcript      │               │
│        │  - Reads canvas JSON     │               │
│        │  - Reads screenshot      │               │
│        │  - Decides action        │               │
│        └──┬──────────┬────────────┘               │
│           │          │                            │
│    spawn  │   cancel │ + redirect                 │
│           │          │                            │
│        ┌──▼──────────▼────────────┐               │
│        │  Canvas Worker           │               │
│        │  (asyncio task)          │               │
│        │  - Calls drawing tools   │               │
│        │  - Streams results back  │               │
│        └──────────────────────────┘               │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │  DO GenAI Inference (OpenAI-compatible)     │  │
│  │  Orchestrator: vision model (Claude/GPT-4o) │  │
│  │  Workers: lightweight model (Llama 3)       │  │
│  └─────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

---

## 6. Agent Architecture (Deep Dive)

### 6.1 Core Design Philosophy

The agent is **reactive and always-on**, not request/response. It behaves like a skilled co-presenter who is always listening and decides when to act — not someone waiting for explicit commands.

Three principles:

1. **Non-blocking:** The agent never waits. It acts on new speech chunks immediately and lets drawing tasks run in the background.
2. **Interruptible:** Any in-flight drawing task can be cancelled the moment the orchestrator detects a topic shift. No drawing task is more important than the current lecture direction.
3. **Spatially intentional:** The agent knows the canvas layout ahead of time (from the lecture notes mapping) and navigates deliberately, not randomly.

---

### 6.2 The Two-Agent Model

#### Orchestrator Agent

The orchestrator is a **long-running loop** — it never terminates during the lecture. It is the only component that holds the full picture: current transcript, canvas state, active tasks, and lecture notes context.

**Responsibilities:**
- Decide whether to do nothing, spawn a new worker, or cancel-and-redirect the current worker
- Determine which canvas region is relevant for the current topic
- Frame the right task description for the worker
- Track what has already been drawn so it does not repeat

**Model requirements:**
- Needs vision (to read canvas screenshots)
- Needs strong instruction following (to map transcript concepts to visual tasks)
- Recommended: Claude Sonnet or GPT-4o via direct API (or DO GenAI if vision endpoint is available)

**Context window on every invocation:**
```
System:
  - Full lecture notes (pre-loaded, static)
  - Canvas region map (static layout of zones)
  - Asset library manifest (list of available pre-made visuals)

User (built fresh each invocation):
  - Last 30 speech chunks (~45 seconds of transcript)
  - Canvas structure JSON (full shape tree, current)
  - Canvas screenshot (base64, current viewport)
  - Currently active worker task (name + description, or null)
  - Recently completed tasks (last 5, to avoid repetition)
```

**Output — one of three decisions:**
```json
{ "action": "idle" }

{ "action": "spawn",
  "task": "Draw a 3-layer neural network in the Tokenisation Zone",
  "region": "tokenisation_zone",
  "assets": ["feedforward_network"] }

{ "action": "interrupt",
  "reason": "Lecture moved to attention mechanism",
  "new_task": "Draw query-key-value attention diagram",
  "new_region": "attention_zone",
  "assets": ["attention_matrix"] }
```

---

#### Canvas Worker Agent

The worker is a **short-lived, focused agent**. It receives a single task description and executes it using the tldraw tool suite. It does not reason about the lecture — it only executes what the orchestrator instructs.

**Responsibilities:**
- Interpret the task description into a sequence of tldraw tool calls
- Use the canvas structure JSON to avoid placing shapes on top of existing content
- Stream each tool call result back to the frontend as it is generated
- Signal completion or failure back to the orchestrator

**Model requirements:**
- Text-only (no vision needed — it receives structured JSON, not screenshots)
- Needs reliable tool/function calling
- Recommended: Llama 3.1 70B or similar on DO GenAI inference (cheaper, fast)

**Available tools:**
```python
draw_text(text, x, y, font_size, color)
draw_shape(shape_type, x, y, width, height, label, color)
  # shape_type: "rectangle" | "ellipse" | "arrow" | "frame"
draw_arrow(x1, y1, x2, y2, label)
place_asset(asset_id, x, y, scale)
  # from DO Spaces asset library
group_shapes(shape_ids, frame_label)
move_camera(x, y, zoom)
get_canvas_structure()   # returns current JSON snapshot
get_viewport_screenshot()  # returns base64 PNG
```

---

### 6.3 The Streaming Loop (Detailed)

```python
class TranscriptBuffer:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.history = []      # full append-only log

    async def push(self, chunk: str):
        self.history.append(chunk)
        await self.queue.put(chunk)

    def recent(self, n=30) -> list[str]:
        return self.history[-n:]


@function_node
async def orchestrator_loop(
    transcript: TranscriptBuffer,
    canvas: CanvasBridge,
    notes: str
):
    active_task: asyncio.Task | None = None
    completed_tasks: list[str] = []

    while True:
        # Wake on new speech chunk
        await transcript.queue.get()

        # Build fresh context
        canvas_json   = await canvas.get_structure()
        canvas_img    = await canvas.get_screenshot()

        # Ask orchestrator LLM
        decision = await call(OrchestratorLLM, {
            "transcript_window": transcript.recent(30),
            "canvas_structure":  canvas_json,
            "canvas_screenshot": canvas_img,
            "active_task":       active_task.get_name() if active_task and not active_task.done() else None,
            "completed_tasks":   completed_tasks[-5:],
            "lecture_notes":     notes,
        })

        if decision.action == "idle":
            continue

        elif decision.action == "spawn":
            if not (active_task and not active_task.done()):
                active_task = asyncio.create_task(
                    canvas_worker(decision.task, decision.region, canvas),
                    name=decision.task
                )

        elif decision.action == "interrupt":
            if active_task and not active_task.done():
                active_task.cancel()
                try:
                    await active_task
                except asyncio.CancelledError:
                    completed_tasks.append(f"[cancelled] {active_task.get_name()}")

            active_task = asyncio.create_task(
                canvas_worker(decision.new_task, decision.new_region, canvas),
                name=decision.new_task
            )

        # Track completions
        if active_task and active_task.done() and not active_task.cancelled():
            completed_tasks.append(active_task.get_name())
            active_task = None
```

---

### 6.4 Canvas State — Two Layers of Awareness

The orchestrator has two views of the canvas at all times. Using both together gives more reliable spatial reasoning than either alone.

**Layer 1 — Structural JSON** (primary, always fresh)

tldraw's `editor.store.getSnapshot()` returns every shape as structured data:

```json
{
  "shapes": [
    {
      "id": "shape:abc123",
      "type": "geo",
      "x": 200, "y": 400,
      "props": { "geo": "rectangle", "w": 300, "h": 120, "text": "Embedding layer" }
    },
    {
      "id": "shape:def456",
      "type": "arrow",
      "x": 350, "y": 520,
      "props": { "text": "token → vector" }
    }
  ]
}
```

This tells the agent exactly what is on the canvas, where it is, and what it says — without needing vision. The worker uses this to place new shapes without collisions.

**Layer 2 — Viewport Screenshot** (secondary, for verification)

A base64 PNG of the current visible viewport. The orchestrator uses this to verify visual coherence and catch layout issues that don't show up in the JSON (e.g. two shapes that are technically non-overlapping but visually crowded).

Screenshot is captured every ~10 seconds or when the orchestrator is about to spawn a new worker — not on every transcript chunk, to keep latency low.

---

### 6.5 Canvas Region Map

Lecture sections are pre-mapped to canvas coordinates before the session starts. The orchestrator uses this map to navigate and place content in the right area.

Example region map for an Intro to LLMs lecture:

```python
CANVAS_REGIONS = {
    "intro_overview":     {"x": 0,     "y": 0,    "w": 2000, "h": 1500},
    "tokenisation_zone":  {"x": 2200,  "y": 0,    "w": 2000, "h": 1500},
    "embedding_zone":     {"x": 4400,  "y": 0,    "w": 2000, "h": 1500},
    "attention_zone":     {"x": 0,     "y": 1700, "w": 2000, "h": 1500},
    "transformer_zone":   {"x": 2200,  "y": 1700, "w": 2000, "h": 1500},
    "training_zone":      {"x": 4400,  "y": 1700, "w": 2000, "h": 1500},
    "inference_zone":     {"x": 0,     "y": 3400, "w": 2000, "h": 1500},
}
```

When the orchestrator decides to work in a region, it first calls `move_camera()` to navigate there, giving the audience a clear visual transition.

---

### 6.6 Lecture Notes as Agent Context

The lecture notes loaded at session start serve as the agent's "cheat sheet" — they tell the orchestrator what visual should appear for which concept, before the lecturer even finishes the sentence.

Recommended notes format:

```markdown
## Tokenisation
Key concept: text is split into subword tokens via BPE.
Visual cue: when lecturer says "token", "BPE", "vocabulary", "subword"
→ Draw: tokenisation grid showing "Hello world" → ["Hello", " world"] → [token IDs]
→ Asset: tokenisation_grid.svg
→ Region: tokenisation_zone

## Self-Attention
Key concept: each token attends to all other tokens with learned weights.
Visual cue: when lecturer says "attention", "query", "key", "value", "QKV"
→ Draw: attention matrix heatmap with query row highlighted
→ Asset: attention_matrix.svg
→ Region: attention_zone
```

This structured mapping dramatically improves orchestrator decision quality and speeds up the hackathon demo.

---

## 7. Technical Stack

| Component | Technology | Notes |
|---|---|---|
| Frontend framework | React / Next.js | |
| UI components | AssistantUI | Transcript sidebar, mic controls |
| Canvas | tldraw (embedded React component) | Uses `editor` ref for all API calls |
| Speech-to-text | Browser Web Speech API | Continuous mode, no external API needed |
| WebSocket | Native WebSocket or socket.io | Bidirectional: speech in, tool calls out |
| Agent harness | RailTracks (Python) | Flows as pure Python, asyncio-native |
| Orchestrator model | Claude Sonnet / GPT-4o | Via Anthropic or OpenAI API (needs vision) |
| Worker model | Llama 3.1 70B | Via DO GenAI inference endpoint |
| Asset storage | DigitalOcean Spaces | SVG lecture visuals, public CDN URLs |
| Hosting | DigitalOcean App Platform | Deploys Next.js frontend + Python backend |

---

## 8. WebSocket Message Protocol

### Frontend → Backend

```json
{ "type": "speech_chunk",   "text": "...and this is where attention comes in",
                             "timestamp": 1711234567890 }

{ "type": "canvas_snapshot", "structure": { ...tldraw store JSON... },
                              "screenshot": "data:image/png;base64,..." }

{ "type": "control",         "action": "pause" | "resume" | "reset" }
```

### Backend → Frontend

```json
{ "type": "tool_call",  "tool": "draw_shape",
                         "args": { "type": "rectangle", "x": 2400, "y": 200,
                                   "w": 300, "h": 120, "label": "Embedding layer" } }

{ "type": "tool_call",  "tool": "move_camera",
                         "args": { "x": 2200, "y": 0, "zoom": 0.8 } }

{ "type": "agent_status", "state": "idle" | "drawing" | "interrupted",
                           "task": "Drawing attention diagram in attention_zone" }
```

---

## 9. Build Order (Hackathon Sequence)

1. **Scaffold** — Next.js app with tldraw + AssistantUI side by side in split pane
2. **Voice pipeline** — Web Speech API → console.log transcript chunks (verify streaming works)
3. **WebSocket bridge** — Connect frontend to Python backend, verify bidirectional messages
4. **tldraw tool functions** — Implement and test all 7 drawing tools against the `editor` ref
5. **Worker agent** — RailTracks agent that calls drawing tools, verify shapes appear on canvas
6. **Orchestrator agent** — Add vision model, lecture notes context, decision output format
7. **Loop integration** — Wire transcript buffer → orchestrator → worker spawn/cancel
8. **Camera navigation** — Implement region map, test camera moves between zones
9. **Asset library** — Upload SVG lecture visuals to DO Spaces, implement `place_asset`
10. **Polish** — Agent status indicator, lecture notes pre-load UI, demo run-through

---

## 10. Open Questions

| # | Question | Impact | Status |
|---|---|---|---|
| OQ-1 | Does DO GenAI inference support vision input? If not, orchestrator needs direct Anthropic/OpenAI API | High — affects model selection | Needs verification |
| OQ-2 | Does Web Speech API have sufficient accuracy for technical vocabulary (LLM, transformer, BPE)? May need Whisper or Deepgram as fallback | Medium — affects transcript quality | Needs testing |
| OQ-3 | What is tldraw `editor.store.getSnapshot()` payload size for a dense canvas? May need pruning before sending to LLM | Medium — affects context window usage | Needs measurement |
| OQ-4 | RailTracks orchestrator/worker architecture is marked "coming soon" — is agents-as-tools sufficient? | Medium — affects implementation approach | Needs verification with docs |
| OQ-5 | Should the orchestrator always request a fresh screenshot, or cache it for N seconds? | Low — latency vs accuracy tradeoff | Design decision |

---

## 11. Key Risks

**Latency:** The full loop (speech → WebSocket → orchestrator LLM call with vision → worker → tool call back) could be 3–6 seconds. This is acceptable for the demo but needs measurement. Mitigation: keep orchestrator context window lean, use screenshot only every ~10 seconds.

**Over-drawing:** The agent may draw too much too fast, cluttering the canvas before the lecturer has finished explaining a concept. Mitigation: lecture notes mapping acts as a governor — agent only draws what is explicitly mapped to the current topic, not everything the LLM can imagine.

**Topic detection accuracy:** The orchestrator must reliably detect when the lecture topic shifts to trigger the interrupt/redirect. Mitigation: structured lecture notes with clear visual cue phrases dramatically improve this. Evaluation on a dry run before the demo is essential.