# TeachWithMeAI Frontend Event Contract

## 1. Purpose

This document defines the frontend-facing event contract for TeachWithMeAI.

It exists so:

- frontend can be built before backend transport is finalized
- backend can change safely as long as it converges to this contract
- assistant-ui and tldraw wiring are based on stable message shapes

This contract is the target.

The current backend does not need to match it yet.

## 2. Design Goals

The contract should support:

- assistant-ui streaming text
- assistant-ui tool/status rendering
- tldraw canvas batch application
- clear session lifecycle
- compatibility with a mock transport in early frontend work

## 3. Transport Model

Preferred production transport:

- WebSocket

Temporary development transport:

- mock server
- local JSON replay
- polling bridge if absolutely needed

The message envelope should be the same regardless of transport.

## 4. Envelope

Every event sent to the frontend should use a common envelope.

```json
{
  "type": "message.assistant.delta",
  "sessionId": "sess_123",
  "eventId": "evt_456",
  "ts": 1743200000000,
  "payload": {}
}
```

### Required top-level fields

- `type`: event type string
- `sessionId`: session identifier
- `eventId`: unique event identifier
- `ts`: event timestamp in milliseconds
- `payload`: event-specific object

## 5. Event Families

The frontend should support these event families first.

### 5.1 Session

- `session.created`
- `session.ready`
- `session.error`

### 5.2 User message/input

- `message.user`
- `message.user.transcript`

### 5.3 Assistant streaming

- `message.assistant.start`
- `message.assistant.delta`
- `message.assistant.final`
- `message.assistant.error`

### 5.4 Assistant reasoning / status

- `reasoning.delta`
- `status.update`

### 5.5 Tool / artifact events

- `tool.call`
- `tool.result`
- `artifact.selected`

### 5.6 Canvas events

- `canvas.batch`
- `canvas.ack`
- `canvas.error`

## 6. Session Events

### 6.1 `session.created`

Sent after session creation.

```json
{
  "type": "session.created",
  "sessionId": "sess_123",
  "eventId": "evt_1",
  "ts": 1743200000000,
  "payload": {
    "lectureId": "intro_to_llms",
    "streamUrl": "/ws/sessions/sess_123"
  }
}
```

### 6.2 `session.ready`

Sent when the backend is ready to accept events for the session.

```json
{
  "type": "session.ready",
  "sessionId": "sess_123",
  "eventId": "evt_2",
  "ts": 1743200000100,
  "payload": {
    "capabilities": {
      "dictation": true,
      "canvas": true,
      "streaming": true
    }
  }
}
```

## 7. User Input Events

### 7.1 `message.user`

Canonical user input event.

```json
{
  "type": "message.user",
  "sessionId": "sess_123",
  "eventId": "evt_3",
  "ts": 1743200001000,
  "payload": {
    "messageId": "msg_user_1",
    "text": "Explain attention",
    "source": "composer"
  }
}
```

### 7.2 `message.user.transcript`

Optional event if partial/final transcript should appear separately in the UI.

```json
{
  "type": "message.user.transcript",
  "sessionId": "sess_123",
  "eventId": "evt_4",
  "ts": 1743200001100,
  "payload": {
    "messageId": "msg_user_1",
    "text": "Explain attention",
    "isFinal": true
  }
}
```

## 8. Assistant Message Events

These are the most important for assistant-ui.

### 8.1 `message.assistant.start`

Signals a new assistant message stream.

```json
{
  "type": "message.assistant.start",
  "sessionId": "sess_123",
  "eventId": "evt_5",
  "ts": 1743200001200,
  "payload": {
    "messageId": "msg_asst_1"
  }
}
```

### 8.2 `message.assistant.delta`

Incremental text append.

```json
{
  "type": "message.assistant.delta",
  "sessionId": "sess_123",
  "eventId": "evt_6",
  "ts": 1743200001300,
  "payload": {
    "messageId": "msg_asst_1",
    "delta": "Attention lets each token compare itself to other tokens. "
  }
}
```

### 8.3 `message.assistant.final`

Marks assistant completion.

```json
{
  "type": "message.assistant.final",
  "sessionId": "sess_123",
  "eventId": "evt_7",
  "ts": 1743200001500,
  "payload": {
    "messageId": "msg_asst_1"
  }
}
```

### 8.4 `message.assistant.error`

```json
{
  "type": "message.assistant.error",
  "sessionId": "sess_123",
  "eventId": "evt_8",
  "ts": 1743200001600,
  "payload": {
    "messageId": "msg_asst_1",
    "error": "LLM request failed"
  }
}
```

## 9. Reasoning and Status Events

These are optional but useful.

### 9.1 `reasoning.delta`

Used for a reasoning block or streamed status section.

```json
{
  "type": "reasoning.delta",
  "sessionId": "sess_123",
  "eventId": "evt_9",
  "ts": 1743200001400,
  "payload": {
    "messageId": "msg_asst_1",
    "delta": "Matching transcript to artifact families."
  }
}
```

### 9.2 `status.update`

Short system/backend state updates.

```json
{
  "type": "status.update",
  "sessionId": "sess_123",
  "eventId": "evt_10",
  "ts": 1743200001450,
  "payload": {
    "stage": "artifact_selected",
    "message": "Selected attention_matrix_basic"
  }
}
```

## 10. Tool and Artifact Events

These can be rendered as assistant-ui tool-call parts.

### 10.1 `tool.call`

```json
{
  "type": "tool.call",
  "sessionId": "sess_123",
  "eventId": "evt_11",
  "ts": 1743200001460,
  "payload": {
    "messageId": "msg_asst_1",
    "toolCallId": "tool_1",
    "toolName": "select_artifact",
    "args": {
      "query": "attention matrix"
    }
  }
}
```

### 10.2 `tool.result`

```json
{
  "type": "tool.result",
  "sessionId": "sess_123",
  "eventId": "evt_12",
  "ts": 1743200001470,
  "payload": {
    "messageId": "msg_asst_1",
    "toolCallId": "tool_1",
    "toolName": "select_artifact",
    "result": {
      "artifactId": "attention_matrix_basic"
    },
    "isError": false
  }
}
```

### 10.3 `artifact.selected`

Optional if we want a dedicated artifact event separate from generic tool events.

```json
{
  "type": "artifact.selected",
  "sessionId": "sess_123",
  "eventId": "evt_13",
  "ts": 1743200001480,
  "payload": {
    "artifactId": "attention_matrix_basic",
    "family": "attention_matrix",
    "reason": "matched attention, query, key, value"
  }
}
```

## 11. Canvas Events

These are for the tldraw side, not the assistant-ui side.

### 11.1 `canvas.batch`

This is the main canvas application event.

```json
{
  "type": "canvas.batch",
  "sessionId": "sess_123",
  "eventId": "evt_14",
  "ts": 1743200001490,
  "payload": {
    "batchId": "batch_1",
    "artifactId": "attention_matrix_basic",
    "ops": [
      {
        "opType": "create_shape",
        "shape": {
          "id": "shape:123",
          "type": "frame",
          "x": 0,
          "y": 0,
          "props": {
            "name": "Attention"
          }
        }
      }
    ]
  }
}
```

### 11.2 `canvas.ack`

Frontend sends this back after applying a batch.

```json
{
  "type": "canvas.ack",
  "sessionId": "sess_123",
  "eventId": "evt_15",
  "ts": 1743200001600,
  "payload": {
    "batchId": "batch_1",
    "ok": true,
    "createdIds": ["shape:123"]
  }
}
```

### 11.3 `canvas.error`

Frontend sends this if the batch fails.

```json
{
  "type": "canvas.error",
  "sessionId": "sess_123",
  "eventId": "evt_16",
  "ts": 1743200001610,
  "payload": {
    "batchId": "batch_1",
    "error": "Unknown shape type"
  }
}
```

## 12. assistant-ui Mapping Rules

Map backend events to assistant-ui like this:

- `message.user` -> user message
- `message.assistant.start/delta/final` -> one assistant message with streaming text
- `reasoning.delta` -> reasoning part on the active assistant message
- `tool.call` + `tool.result` -> tool-call part
- `status.update` -> lightweight assistant/system status presentation

Do not map `canvas.batch` into the chat as the source of truth.

It may also be shown in chat, but the real execution path should remain separate.

## 13. tldraw Mapping Rules

Map canvas events like this:

- `canvas.batch` -> op dispatcher
- `canvas.ack` -> backend confirmation
- `canvas.error` -> backend + UI error handling

Supported first-pass operation types:

- `create_shape`
- `update_shape`
- `delete_shape`
- `set_camera`

## 14. Mock Server / JSON Replay Plan

We can add this in frontend step 2.

That is a good idea.

### 14.1 Goal

Let the frontend use the real event contract before backend streaming is finished.

### 14.2 Acceptable temporary implementations

- a local mock WebSocket server
- a local JSON event replay file
- a dev-only adapter that emits the exact same event envelope

### 14.3 Requirements

The mock layer must emit the same event contract as production.

Do not invent separate frontend-only message shapes.

### 14.4 Suggested mock scenarios

- session created
- user asks about tokenization
- assistant streams response
- tool/artifact selection event appears
- canvas batch event appears
- assistant final arrives

## 15. Versioning

Add a version field later if needed, but for now keep the envelope small.

If versioning is introduced:

```json
{
  "version": 1,
  "type": "message.assistant.delta",
  "sessionId": "sess_123",
  "eventId": "evt_1",
  "ts": 1743200000000,
  "payload": {}
}
```

## 16. Recommendation

Use this event contract as the target for:

- frontend runtime design
- mock transport design
- backend streaming redesign

This lets us build the frontend now and still change the backend safely.
