# TeachWithMeAI Frontend Implementation Plan

## 1. Goal

Create a new frontend app for TeachWithMeAI.

This plan is about:

- setting up a new `frontend/` folder
- choosing the right assistant-ui starting point
- choosing the right tldraw setup
- defining the frontend architecture before integration
- preparing the frontend to connect cleanly to a stream-friendly backend API

This is **not** the final backend/frontend wiring plan.

That should come after:

- frontend scaffold exists
- assistant-ui is running
- tldraw is running
- backend streaming event shapes are stable enough to target

## 2. Current Situation

We already have:

- backend work in progress under `teachMeAi/backend`
- a local assistant-ui reference repo
- a sibling project that already uses assistant-ui with a custom runtime
- a backend-first architecture and backend-first implementation plan

We do **not** yet have:

- a dedicated `frontend/` app in this repo
- a chosen assistant-ui bootstrap path
- a tldraw shell in this repo
- a finalized stream contract from backend to frontend

So the next correct step is frontend implementation planning with a stream-first contract in mind, not locking the UI to the current REST prototype.

## 3. High-Level Frontend Goal

The frontend should eventually provide:

- a narrow chat/voice panel on the left
- a large tldraw canvas on the right
- a clean assistant-ui-based composer and thread built primarily with assistant-ui primitives and built-in runtime support
- a place to show backend streaming status
- a thin adapter layer for future backend integration

But phase 1 frontend work should only prove:

- assistant-ui app boots
- dictation works
- tldraw canvas renders
- layout feels right
- the frontend state model is compatible with real streaming integration

## 4. Recommended Build Order

Build the frontend in this order:

1. create `frontend/`
2. bootstrap a real Vite + React frontend
3. strip it down to the layout we want
4. add tldraw pane
5. define the frontend runtime around stream events, not hardcoded REST responses
6. add dictation
7. add real canvas operation dispatcher
8. only then finalize the backend/frontend integration contract

## 5. Local References

These are the best local references to use while building.

### assistant-ui reference repo

- [assistant-ui repo](/c:/Users/shukl/Desktop/projects/claudeUIWithAssisstantUI/references/assistant-ui)

### assistant-ui external-store example

- [with-external-store](/c:/Users/shukl/Desktop/projects/claudeUIWithAssisstantUI/references/assistant-ui/examples/with-external-store/app/MyRuntimeProvider.tsx)

Why:

- smallest custom-runtime example
- best fit for a backend-owned app

### assistant-ui dictation example

- [with-elevenlabs-scribe page](/c:/Users/shukl/Desktop/projects/claudeUIWithAssisstantUI/references/assistant-ui/examples/with-elevenlabs-scribe/app/page.tsx)

### sibling app using assistant-ui with a real custom backend

- [useClaudeRuntime.ts](/c:/Users/shukl/Desktop/projects/claudeUIWithAssisstantUI/client/src/runtime/useClaudeRuntime.ts)
- [thread.tsx](/c:/Users/shukl/Desktop/projects/claudeUIWithAssisstantUI/client/src/components/assistant-ui/thread.tsx)

Why:

- best proof that a non-standard backend can be adapted cleanly to assistant-ui

## 6. Online References

### assistant-ui

- starter repo:
  - https://github.com/assistant-ui/assistant-ui-starter
- external store runtime:
  - https://www.assistant-ui.com/docs/runtimes/custom/external-store
- dictation guide:
  - https://www.assistant-ui.com/docs/guides/dictation
- composer primitives:
  - https://www.assistant-ui.com/docs/primitives/composer

### tldraw

- editor docs:
  - https://tldraw.dev/docs/editor
- starter kits overview:
  - https://tldraw.dev/starter-kits/overview
- agent starter kit:
  - https://tldraw.dev/starter-kits/agent

## 7. Frontend Setup Decision

### 7.1 Recommended foundation

Use a fresh Vite React app in `frontend/` and bring in:

- assistant-ui primitives/runtime
- tldraw directly

Do not start from the tldraw agent starter kit.

Do not start from the sibling app wholesale.

### 7.2 Why

The sibling app is a useful reference, but it contains Claude-specific behavior we do not want to inherit.

The tldraw agent starter kit is useful for ideas, but it centers an in-frontend agent loop we do not want.

The cleanest path is:

- fresh Vite frontend app
- assistant-ui setup
- tldraw setup
- TeachWithMeAI-specific layout and state

## 8. Bootstrap Options

There are three realistic bootstrap paths.

### Option A: Start from assistant-ui starter repo

Good when:

- you want a fast assistant-ui baseline
- you are okay trimming starter assumptions

Pros:

- official
- likely quickest way to get a polished thread/composer running

Cons:

- may include assumptions you later remove

### Option B: Start from assistant-ui CLI example if available

Good when:

- the CLI supports a close-enough example like external-store or dictation

Pros:

- fastest for prototyping

Cons:

- example choice may not match our exact architecture

### Option C: Start from plain Vite/Next app and copy only what we need

Good when:

- you want maximum control

Pros:

- cleanest repo
- least accidental baggage

Cons:

- more setup work

### Recommendation

Use:

1. a fresh Vite app as the base
2. assistant-ui primitives and runtime directly
3. patterns copied selectively from the local assistant-ui references
4. tldraw added as a sibling pane

That gives maximum control while still reusing assistant-ui heavily.

## 9. Framework Choice

Recommended:

- `frontend/` as a standalone React app
- either Vite or Next.js

### Recommendation

Use Vite.

Why:

- faster local iteration
- simpler setup for canvas-heavy UI
- cleaner for early-stage websocket frontend work

If the repo later needs Next.js, migration is still manageable.

## 10. Frontend Directory Plan

Target structure:

```text
frontend/
  src/
    main.tsx
    App.tsx
    styles/
    runtime/
      useTeachWithMeRuntime.ts
      mockRuntime.ts
      types.ts
    components/
      layout/
        AppShell.tsx
        SplitPane.tsx
      assistant/
        ThreadPanel.tsx
        ComposerBar.tsx
        MessageParts.tsx
      canvas/
        CanvasPane.tsx
        opDispatcher.ts
        editorState.ts
    providers/
      RuntimeProvider.tsx
```

## 11. Layout Plan

The first UI to build should be simple.

### 11.1 App shell

- full-height viewport
- two-column layout
- dark theme acceptable for now

### 11.2 Left panel

Contains:

- assistant-ui thread
- composer
- mic/dictation control
- small session/status strip

### 11.3 Right panel

Contains:

- tldraw canvas
- optional small top overlay for canvas status

## 12. Backend Contract Assumption

The frontend should assume the backend API can still change.

That is a good thing.

We should define the UI around the contract we actually want:

- streamable assistant updates
- streamable backend status
- streamable canvas operation batches
- explicit session lifecycle

### 12.1 Preferred transport

Preferred:

- WebSocket

Acceptable fallback:

- SSE for assistant/status stream + HTTP for user actions

Do not optimize the frontend around:

- request/response-only REST for chat updates
- polling as the long-term architecture

Polling may be useful temporarily during local development, but it should not shape the runtime design.

### 12.2 Preferred backend event families

The frontend should be designed to consume a small number of stable event families:

- `session.created`
- `message.user`
- `message.assistant.delta`
- `message.assistant.final`
- `status.update`
- `artifact.selected`
- `canvas.batch`
- `canvas.ack`
- `error`

### 12.3 Why this matters

assistant-ui works best when:

- the frontend receives incremental message updates
- it can maintain a stable message identity
- it can distinguish streaming assistant text from final completion

tldraw works best when:

- canvas mutations arrive as explicit operation batches
- the canvas executor is separate from chat message rendering

So the API should reflect that split directly.

## 13. assistant-ui Plan

### 12.1 Runtime choice

Use `useExternalStoreRuntime`.

Reason:

- backend will own true state later
- frontend needs custom message mapping
- assistant-ui supports this pattern directly

### 13.2 Runtime design goal

Do not design the runtime around fake local messages.

Design it around a real external store shape that expects:

- session creation
- user message submission
- assistant delta events
- assistant completion events
- tool/status events

If the initial implementation temporarily uses a local bridge while the backend evolves, that bridge should still emit the same event contract the real backend will emit later.

### 13.3 assistant-ui reuse policy

Use assistant-ui primitives and built-in runtime support as much as possible:

- `AssistantRuntimeProvider`
- `useExternalStoreRuntime`
- `ThreadPrimitive`
- `MessagePrimitive`
- `ComposerPrimitive`
- `LexicalComposerInput`
- `WebSpeechDictationAdapter`
- `StreamdownTextPrimitive`

Only add custom wrappers where TeachWithMeAI needs app-specific styling or backend adaptation.

### 13.4 Dictation

Use assistant-ui dictation primitives.

Start with:

- `WebSpeechDictationAdapter`

Reason:

- no extra infra
- easy to test in browser

### 13.5 Message model

The thread should be designed to support:

- text user message
- streaming assistant text
- assistant completion state
- optional reasoning part
- optional tool-call part
- optional backend status/info message

## 14. tldraw Plan

### 13.1 Initial use

Use plain `Tldraw` with direct editor access.

The goal for phase 1 is only:

- canvas renders
- editor can be accessed
- mock operations can create/update/delete shapes

### 13.2 No agent starter kit yet

Do not use:

- `useTldrawAgent`
- PromptPartUtil/AgentActionUtil runtime loop

Use only:

- canvas component
- editor API

### 14.3 Real operation dispatcher

Add a real dispatcher abstraction now, even if the first backend transport is temporary.

It should expect:

- `canvas.batch` events
- explicit operation types
- batch IDs
- future backend acknowledgements

The dispatcher should not be designed around demo-only local buttons or fake batches.

## 15. Phase 1 Frontend Deliverables

Frontend phase 1 is done when:

- `frontend/` exists and runs
- assistant-ui thread renders
- composer renders
- dictation button works
- tldraw canvas renders
- left/right layout feels correct
- the runtime is structured around streaming backend events
- the canvas dispatcher is structured around real batch application

The backend connection may still be evolving, but the frontend architecture should already match the intended streaming contract.

## 16. Phase 2 Frontend Deliverables

Only after phase 1:

- WebSocket connection to backend
- message mapping from backend stream
- canvas op batch consumption
- session status integration

That phase should be planned after we inspect the real frontend scaffold and current backend event shapes together.

## 17. Risks

### 16.1 Starting from the wrong example

Mitigation:

- use examples as references, not as architecture commitments

### 16.2 Bringing too much from sibling app

Mitigation:

- copy patterns, not app-specific code

### 17.3 Premature backend coupling

Mitigation:

- couple the frontend to the intended event contract, not the temporary REST prototype

### 17.4 Dictation UX complexity

Mitigation:

- use browser dictation first
- postpone advanced speech improvements

## 18. Proposed Stream-Friendly API Shape

This is the kind of backend contract the frontend should target.

### Session creation

HTTP:

- `POST /sessions`

Returns:

```json
{
  "sessionId": "abc123",
  "streamUrl": "/ws/sessions/abc123",
  "lectureId": "intro_to_llms"
}
```

### User message / transcript submission

Over WebSocket:

```json
{
  "type": "message.user",
  "sessionId": "abc123",
  "messageId": "msg-1",
  "text": "Explain attention"
}
```

### Assistant streaming delta

```json
{
  "type": "message.assistant.delta",
  "sessionId": "abc123",
  "messageId": "asst-1",
  "delta": "The system is matching this to self-attention."
}
```

### Assistant final

```json
{
  "type": "message.assistant.final",
  "sessionId": "abc123",
  "messageId": "asst-1"
}
```

### Canvas batch

```json
{
  "type": "canvas.batch",
  "sessionId": "abc123",
  "batchId": "batch-1",
  "artifactId": "attention_matrix_basic",
  "ops": [...]
}
```

### Status update

```json
{
  "type": "status.update",
  "sessionId": "abc123",
  "stage": "artifact_selected",
  "message": "Selected attention_matrix_basic"
}
```

This is the kind of shape the frontend should be built around.

## 19. Concrete Next Steps

1. Create `frontend/`.
2. Pick bootstrap path:
   - assistant-ui starter or fresh Vite app.
3. Install assistant-ui packages.
4. Install tldraw.
5. Build split layout.
6. Build `useTeachWithMeRuntime` around the stream contract above.
7. Add dictation button using assistant-ui.
8. Add real tldraw batch dispatcher abstraction.
9. Review resulting frontend structure.
10. Then update backend API to match the frontend contract where needed.

## 20. Final Recommendation

The right order is:

- frontend implementation plan
- frontend scaffold
- stream-first frontend runtime
- real canvas dispatcher
- review real frontend structure
- then align backend API to the intended frontend contract

That is cleaner than hard-coding the frontend to a temporary REST API and then undoing it later.
