import type { ThreadMessageLike } from '@assistant-ui/react'

export type BackendEventRecord = {
  event_id: string
  session_id: string
  kind: string
  payload: Record<string, unknown>
  ts_ms: number
}

export type BackendBatchRecord = {
  batch_id: string
  session_id: string
  ops: Array<Record<string, unknown>>
  artifact_id: string | null
  source: string
}

export type BackendStreamMessage =
  | {
      type: 'snapshot'
      session_id: string
      events: BackendEventRecord[]
      batches: BackendBatchRecord[]
    }
  | {
      type: 'event'
      session_id: string
      event: BackendEventRecord
    }

export type BackendArtifactRecord = {
  artifact_id: string
  family: string
  version: string
  title: string
  description: string
  tags: string[]
  parameters: Record<string, Record<string, unknown>>
  shape_template: Array<Record<string, unknown>>
}

export type FrontendRuntimeEvent =
  | { type: 'assistant_start'; messageId: string }
  | { type: 'assistant_delta'; messageId: string; delta: string }
  | { type: 'assistant_final'; messageId: string }
  | { type: 'reasoning_delta'; messageId: string; delta: string }
  | { type: 'tool_message'; message: ThreadMessageLike }
  | { type: 'status'; message: string }
  | { type: 'error'; message: string }

export type CanvasBatch = {
  batchId: string
  artifactId: string | null
  ops: Array<{
    opType: string
    shape?: Record<string, unknown>
    shapeId?: string
    camera?: { x: number; y: number; z: number }
  }>
}
