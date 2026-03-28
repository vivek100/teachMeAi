import type { BackendBatchRecord, BackendEventRecord, CanvasBatch, FrontendRuntimeEvent } from './types'

export function adaptBackendEvent(event: BackendEventRecord): FrontendRuntimeEvent[] {
  switch (event.kind) {
    case 'decision_made': {
      const messageId = `asst-${event.event_id}`
      const payload = event.payload as {
        topic?: string
        rationale?: string
        intent?: string
      }

      const summary = [
        payload.topic ? `Topic: ${payload.topic}.` : null,
        payload.intent ? `Intent: ${payload.intent}.` : null,
        payload.rationale ?? null,
      ]
        .filter(Boolean)
        .join(' ')

      return [
        { type: 'assistant_start', messageId },
        { type: 'assistant_delta', messageId, delta: summary || 'Processed the latest lecture window.' },
        { type: 'assistant_final', messageId },
      ]
    }
    case 'artifact_selected': {
      const payload = event.payload as { artifact_id?: string; family?: string; query?: string }
      return [
        {
          type: 'tool_message',
          message: {
            id: `tool-${event.event_id}`,
            role: 'assistant',
            createdAt: new Date(event.ts_ms),
            content: [
              {
                type: 'tool-call',
                toolCallId: `tool-${event.event_id}`,
                toolName: 'select_artifact',
                args: { query: payload.query ?? '' },
                result: { artifactId: payload.artifact_id ?? null, family: payload.family ?? null },
              },
            ],
            status: { type: 'complete', reason: 'stop' },
          },
        },
      ]
    }
    case 'artifact_instantiated': {
      const payload = event.payload as { artifact_id?: string; batch_id?: string; op_count?: number }
      return [
        {
          type: 'tool_message',
          message: {
            id: `tool-${event.event_id}`,
            role: 'assistant',
            createdAt: new Date(event.ts_ms),
            content: [
              {
                type: 'tool-call',
                toolCallId: `tool-${event.event_id}`,
                toolName: 'instantiate_artifact',
                args: { artifactId: payload.artifact_id ?? null },
                result: { batchId: payload.batch_id ?? null, opCount: payload.op_count ?? 0 },
              },
            ],
            status: { type: 'complete', reason: 'stop' },
          },
        },
      ]
    }
    case 'warning':
      return [{ type: 'status', message: String(event.payload.message ?? 'Backend warning') }]
    case 'error':
      return [{ type: 'error', message: String(event.payload.message ?? 'Backend error') }]
    case 'window_ready':
      return [{ type: 'status', message: 'Transcript window is ready for orchestration.' }]
    case 'op_batch_ready':
      return [{ type: 'status', message: 'Canvas operations are ready to apply.' }]
    default:
      return []
  }
}

export function adaptBatch(batch: BackendBatchRecord): CanvasBatch {
  return {
    batchId: batch.batch_id,
    artifactId: batch.artifact_id,
    ops: batch.ops.map((op) => ({
      opType: String(op.op_type ?? op.opType ?? ''),
      shape: (op.shape as Record<string, unknown> | undefined) ?? undefined,
      shapeId: typeof op.shape_id === 'string' ? op.shape_id : typeof op.shapeId === 'string' ? op.shapeId : undefined,
      camera: op.camera as { x: number; y: number; z: number } | undefined,
    })),
  }
}
