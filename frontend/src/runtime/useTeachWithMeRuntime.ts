import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  WebSpeechDictationAdapter,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { createSession, getBatches, getEvents, getSessionWebSocketUrl, sendChunk } from './api-client'
import { runtimeDebug } from './debug'
import { adaptBackendEvent, adaptBatch } from './event-adapter'
import type { BackendBatchRecord, BackendEventRecord, BackendStreamMessage, CanvasBatch, FrontendRuntimeEvent } from './types'

function createUserMessage(text: string): ThreadMessageLike {
  return {
    id: `user-${crypto.randomUUID()}`,
    role: 'user',
    createdAt: new Date(),
    content: [{ type: 'text', text }],
    attachments: [],
    metadata: {
      custom: {},
    },
  }
}

export function useTeachWithMeRuntime() {
  const [messages, setMessages] = useState<readonly ThreadMessageLike[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [backendStatus, setBackendStatus] = useState('Waiting for first session')
  const [error, setError] = useState<string | null>(null)
  const [canvasBatches, setCanvasBatches] = useState<readonly CanvasBatch[]>([])

  const seenEventIds = useRef<Set<string>>(new Set())
  const seenBatchIds = useRef<Set<string>>(new Set())
  const isSendingRef = useRef(false)

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId
    runtimeDebug.info('runtime', 'ensuring session')
    const created = await createSession()
    setSessionId(created.session_id)
    setBackendStatus(`Session created: ${created.session_id}`)
    return created.session_id
  }, [sessionId])

  const applyRuntimeEvent = useCallback((event: FrontendRuntimeEvent) => {
    runtimeDebug.debug('runtime', 'applying frontend event', { type: event.type })
    if (event.type === 'status') {
      setBackendStatus(event.message)
      return
    }

    if (event.type === 'error') {
      setError(event.message)
      setBackendStatus('Backend error')
      setIsRunning(false)
      return
    }

    if (event.type === 'tool_message') {
      setMessages((current) => [...current, event.message])
      return
    }

    if (event.type === 'assistant_start') {
      setMessages((current) => {
        if (current.some((message) => message.id === event.messageId)) return current
        return [
          ...current,
          {
            id: event.messageId,
            role: 'assistant',
            createdAt: new Date(),
            content: [{ type: 'text', text: '' }],
            status: { type: 'running' },
          },
        ]
      })
      return
    }

    if (event.type === 'assistant_delta') {
      setMessages((current) =>
        current.map((message) => {
          if (message.id !== event.messageId || message.role !== 'assistant') return message
          const content = Array.isArray(message.content) ? [...message.content] : [{ type: 'text', text: String(message.content) }]
          const existing = content.find((part) => part.type === 'text')
          if (existing && existing.type === 'text') {
            existing.text += event.delta
          } else {
            content.push({ type: 'text', text: event.delta })
          }
          return { ...message, content, status: { type: 'running' as const } }
        }),
      )
      return
    }

    if (event.type === 'reasoning_delta') {
      setMessages((current) =>
        current.map((message) => {
          if (message.id !== event.messageId || message.role !== 'assistant') return message
          const content = Array.isArray(message.content) ? [...message.content] : [{ type: 'text', text: String(message.content) }]
          const existing = content.find((part) => part.type === 'reasoning')
          if (existing && existing.type === 'reasoning') {
            existing.text += event.delta
          } else {
            content.push({ type: 'reasoning', text: event.delta })
          }
          return { ...message, content, status: { type: 'running' as const } }
        }),
      )
      return
    }

    if (event.type === 'assistant_final') {
      setMessages((current) =>
        current.map((message) =>
          message.id === event.messageId && message.role === 'assistant'
            ? { ...message, status: { type: 'complete' as const, reason: 'stop' as const } }
            : message,
        ),
      )
      setIsRunning(false)
    }
  }, [])

  const ingestBackendEvent = useCallback(
    (event: BackendEventRecord) => {
      if (seenEventIds.current.has(event.event_id)) return
      seenEventIds.current.add(event.event_id)
      runtimeDebug.info('stream', 'backend event received', {
        eventId: event.event_id,
        kind: event.kind,
      })

      const adapted = adaptBackendEvent(event)
      adapted.forEach(applyRuntimeEvent)

      if (event.kind !== 'op_batch_ready') return
      const maybeBatch = event.payload.batch
      if (!maybeBatch || typeof maybeBatch !== 'object') return

      const batch = maybeBatch as BackendBatchRecord
      if (seenBatchIds.current.has(batch.batch_id)) return
      seenBatchIds.current.add(batch.batch_id)
      runtimeDebug.info('stream', 'embedded batch received', {
        batchId: batch.batch_id,
        artifactId: batch.artifact_id,
        opCount: batch.ops.length,
      })
      setCanvasBatches((current) => [...current, adaptBatch(batch)])
    },
    [applyRuntimeEvent],
  )

  const ingestBackendBatch = useCallback((batch: BackendBatchRecord) => {
    if (seenBatchIds.current.has(batch.batch_id)) return
    seenBatchIds.current.add(batch.batch_id)
    runtimeDebug.info('stream', 'batch received', {
      batchId: batch.batch_id,
      artifactId: batch.artifact_id,
      opCount: batch.ops.length,
    })
    setCanvasBatches((current) => [...current, adaptBatch(batch)])
  }, [])

  const submitTranscriptChunk = useCallback(
    async (rawText: string) => {
      const text = rawText.trim()
      if (!text) return
      if (isSendingRef.current) return
      runtimeDebug.info('runtime', 'submitting transcript chunk', { textLength: text.length })

      isSendingRef.current = true
      setError(null)
      setMessages((current) => [...current, createUserMessage(text)])
      setIsRunning(true)
      setBackendStatus('Sending transcript chunk to backend')

      try {
        const ensuredSessionId = await ensureSession()
        const result = await sendChunk(ensuredSessionId, text)
        if (!result.window_triggered) {
          setBackendStatus('Chunk accepted. Waiting for more transcript before orchestration.')
          setIsRunning(false)
        } else {
          setBackendStatus('Backend is orchestrating the latest window')
        }
      } catch (err) {
        const messageText = err instanceof Error ? err.message : 'Failed to send transcript chunk'
        runtimeDebug.error('runtime', 'submit failed', { message: messageText })
        setError(messageText)
        setBackendStatus('Request failed')
        setIsRunning(false)
      } finally {
        isSendingRef.current = false
      }
    },
    [ensureSession],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const textPart = message.content.find((part) => part.type === 'text')
      if (!textPart || textPart.type !== 'text') {
        throw new Error('TeachWithMeAI currently supports text messages only.')
      }

      await submitTranscriptChunk(textPart.text)
    },
    [submitTranscriptChunk],
  )

  const onCancel = useCallback(async () => {
    setIsRunning(false)
    setBackendStatus('Cancelled locally')
  }, [])

  useEffect(() => {
    if (!sessionId) return

    let stopped = false

    const hydrateFromHttp = async () => {
      try {
        runtimeDebug.info('stream', 'hydrating session from http', { sessionId })
        const [events, batches] = await Promise.all([getEvents(sessionId), getBatches(sessionId)])
        if (stopped) return
        events.forEach(ingestBackendEvent)
        batches.forEach(ingestBackendBatch)
      } catch (err) {
        if (stopped) return
        const messageText = err instanceof Error ? err.message : 'Initial sync failed'
        runtimeDebug.error('stream', 'initial sync failed', { message: messageText })
        setError(messageText)
        setBackendStatus('Initial sync failed')
      }
    }

    hydrateFromHttp()

    const websocket = new WebSocket(getSessionWebSocketUrl(sessionId))
    runtimeDebug.info('stream', 'opening websocket', {
      sessionId,
      url: getSessionWebSocketUrl(sessionId),
    })

    websocket.onopen = () => {
      if (stopped) return
      runtimeDebug.info('stream', 'websocket open', { sessionId })
      setBackendStatus('Live stream connected')
    }

    websocket.onmessage = (messageEvent) => {
      if (stopped) return

      let payload: BackendStreamMessage
      try {
        payload = JSON.parse(messageEvent.data) as BackendStreamMessage
      } catch {
        runtimeDebug.warn('stream', 'failed to parse websocket payload')
        return
      }

      if (payload.type === 'snapshot') {
        runtimeDebug.info('stream', 'websocket snapshot received', {
          sessionId,
          eventCount: payload.events.length,
          batchCount: payload.batches.length,
        })
        payload.events.forEach(ingestBackendEvent)
        payload.batches.forEach(ingestBackendBatch)
        return
      }

      if (payload.type === 'event') {
        ingestBackendEvent(payload.event)
      }
    }

    websocket.onerror = () => {
      if (stopped) return
      runtimeDebug.error('stream', 'websocket error', { sessionId })
      setBackendStatus('Live stream error, using HTTP sync')
    }

    websocket.onclose = () => {
      if (stopped) return
      runtimeDebug.warn('stream', 'websocket closed', { sessionId })
      setBackendStatus('Live stream disconnected')
    }

    return () => {
      stopped = true
      websocket.close()
    }
  }, [ingestBackendBatch, ingestBackendEvent, sessionId])

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    onNew,
    onCancel,
    convertMessage: (message: ThreadMessageLike) => message,
    adapters: {
      dictation: new WebSpeechDictationAdapter(),
    },
  })

  const markBatchApplied = useCallback((batchId: string) => {
    setCanvasBatches((current) => current.filter((batch) => batch.batchId !== batchId))
  }, [])

  return useMemo(
    () => ({
      runtime,
      sessionId,
      isRunning,
      backendStatus,
      error,
      canvasBatches,
      markBatchApplied,
      submitTranscriptChunk,
    }),
    [runtime, sessionId, isRunning, backendStatus, error, canvasBatches, markBatchApplied, submitTranscriptChunk],
  )
}
