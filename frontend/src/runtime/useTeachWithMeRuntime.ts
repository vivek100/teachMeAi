import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  WebSpeechDictationAdapter,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { mockArtifacts } from '../demo/mock-artifacts'
import { createSession, getArtifacts, getBatches, getEvents, sendChunk } from './api-client'
import { adaptBackendEvent, adaptBatch } from './event-adapter'
import type { BackendArtifactRecord, CanvasBatch, FrontendRuntimeEvent } from './types'

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

const DEMO_MODE = (import.meta.env.VITE_RUNTIME_MODE ?? 'demo') === 'demo'

const DEMO_SUMMARIES = [
  'I detected a tokenization explanation, so I am placing a token grid to anchor the vocabulary discussion.',
  'This turn sounds like an embedding explanation, so I am rendering a spatial artifact for vector intuition.',
  'This turn maps well to self-attention, so I am placing an attention matrix artifact on the board.',
  'This sounds like transformer architecture, so I am adding a stack overview artifact for the next segment.',
  'This sounds like training dynamics, so I am drawing a loss curve artifact to support the explanation.',
]

export function useTeachWithMeRuntime() {
  const [messages, setMessages] = useState<readonly ThreadMessageLike[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [backendStatus, setBackendStatus] = useState('Waiting for first session')
  const [error, setError] = useState<string | null>(null)
  const [canvasBatches, setCanvasBatches] = useState<readonly CanvasBatch[]>([])
  const [demoArtifacts, setDemoArtifacts] = useState<BackendArtifactRecord[]>(mockArtifacts)

  const seenEventIds = useRef<Set<string>>(new Set())
  const seenBatchIds = useRef<Set<string>>(new Set())
  const isSendingRef = useRef(false)
  const demoTurnRef = useRef(0)

  useEffect(() => {
    if (!DEMO_MODE) return
    let cancelled = false

    const loadArtifacts = async () => {
      try {
        const artifacts = await getArtifacts()
        if (!cancelled) setDemoArtifacts(artifacts.length > 0 ? artifacts : mockArtifacts)
      } catch (err) {
        if (!cancelled) {
          setDemoArtifacts(mockArtifacts)
          setBackendStatus('Using fallback demo artifacts')
        }
      }
    }

    loadArtifacts()
    return () => {
      cancelled = true
    }
  }, [])

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId
    const created = await createSession()
    setSessionId(created.session_id)
    setBackendStatus(`Session created: ${created.session_id}`)
    return created.session_id
  }, [sessionId])

  const applyRuntimeEvent = useCallback((event: FrontendRuntimeEvent) => {
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

  const submitTranscriptChunk = useCallback(
    async (rawText: string) => {
      const text = rawText.trim()
      if (!text) return
      if (isSendingRef.current) return

      isSendingRef.current = true
      setError(null)
      setMessages((current) => [...current, createUserMessage(text)])
      setIsRunning(true)
      setBackendStatus(DEMO_MODE ? 'Running frontend demo turn' : 'Sending transcript chunk to backend')

      try {
        if (DEMO_MODE) {
          const turnIndex = demoTurnRef.current++
          const availableArtifacts = demoArtifacts.length > 0 ? demoArtifacts : mockArtifacts
          const artifact = availableArtifacts[turnIndex % availableArtifacts.length]
          const summary = DEMO_SUMMARIES[turnIndex % DEMO_SUMMARIES.length]
          const messageId = `demo-asst-${turnIndex}`

          setMessages((current) => [
            ...current,
            {
              id: messageId,
              role: 'assistant',
              createdAt: new Date(),
              content: [{ type: 'text', text: summary }],
              status: { type: 'complete', reason: 'stop' },
              metadata: {
                unstable_state: null,
                unstable_annotations: [],
                unstable_data: [],
                steps: [],
                custom: {},
              },
            },
          ])

          if (artifact) {
            const demoBatch = createDemoBatch(artifact, turnIndex)
            console.debug('TeachWithMeAI runtime: created demo batch', demoBatch)
            setMessages((current) => [
              ...current,
              {
                id: `demo-tool-${turnIndex}`,
                role: 'assistant',
                createdAt: new Date(),
                content: [
                  {
                    type: 'tool-call',
                    toolCallId: `demo-tool-${turnIndex}`,
                    toolName: 'instantiate_artifact',
                    args: { artifactId: artifact.artifact_id, family: artifact.family },
                    result: { title: artifact.title, shapes: artifact.shape_template.length },
                  },
                ],
                status: { type: 'complete', reason: 'stop' },
                metadata: {
                  unstable_state: null,
                  unstable_annotations: [],
                  unstable_data: [],
                  steps: [],
                  custom: {},
                },
              },
            ])

            setCanvasBatches((current) => [...current, demoBatch])
          }

          setBackendStatus(artifact ? `Demo rendered: ${artifact.title}` : 'Demo turn completed')
          setIsRunning(false)
          return
        }

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
        setError(messageText)
        setBackendStatus('Request failed')
        setIsRunning(false)
      } finally {
        isSendingRef.current = false
      }
    },
    [demoArtifacts, ensureSession],
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

    const poll = async () => {
      try {
        const [events, batches] = await Promise.all([getEvents(sessionId), getBatches(sessionId)])

        if (stopped) return

        for (const event of events) {
          if (seenEventIds.current.has(event.event_id)) continue
          seenEventIds.current.add(event.event_id)
          const adapted = adaptBackendEvent(event)
          adapted.forEach(applyRuntimeEvent)
        }

        for (const batch of batches) {
          if (seenBatchIds.current.has(batch.batch_id)) continue
          seenBatchIds.current.add(batch.batch_id)
          setCanvasBatches((current) => [...current, adaptBatch(batch)])
        }
      } catch (err) {
        if (stopped) return
        const messageText = err instanceof Error ? err.message : 'Polling failed'
        setError(messageText)
        setBackendStatus('Backend polling failed')
      }
    }

    poll()
    const handle = window.setInterval(poll, 1500)
    return () => {
      stopped = true
      window.clearInterval(handle)
    }
  }, [applyRuntimeEvent, sessionId])

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

function createDemoBatch(artifact: BackendArtifactRecord, turnIndex: number): CanvasBatch {
  const offsetX = 40 + (turnIndex % 3) * 30
  const offsetY = 40 + (turnIndex % 2) * 24
  const batchId = `demo-batch-${turnIndex}`

  return {
    batchId,
    artifactId: artifact.artifact_id,
    ops: [
      {
        opType: 'set_camera',
        camera: { x: 0, y: 0, z: 1 },
      },
      ...buildGuaranteedDemoShapes(artifact, turnIndex, offsetX, offsetY).map((shape) => ({
        opType: 'create_shape',
        shape,
      })),
    ],
  }
}

function buildGuaranteedDemoShapes(
  artifact: BackendArtifactRecord,
  turnIndex: number,
  offsetX: number,
  offsetY: number,
) {
  const title = artifact.title || artifact.artifact_id
  const family = artifact.family
  const ids = {
    frame: `shape:${artifact.artifact_id}:${turnIndex}:frame`,
    title: `shape:${artifact.artifact_id}:${turnIndex}:title`,
    subtitle: `shape:${artifact.artifact_id}:${turnIndex}:subtitle`,
    cardA: `shape:${artifact.artifact_id}:${turnIndex}:a`,
    cardB: `shape:${artifact.artifact_id}:${turnIndex}:b`,
    cardC: `shape:${artifact.artifact_id}:${turnIndex}:c`,
  }

  return [
    {
      id: ids.frame,
      typeName: 'shape',
      type: 'frame',
      x: 120 + offsetX,
      y: 80 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}0`,
      props: {
        name: title,
        w: 640,
        h: 360,
      },
      meta: {},
    },
    {
      id: ids.title,
      typeName: 'shape',
      type: 'text',
      x: 150 + offsetX,
      y: 120 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}1`,
      props: {
        richText: toRichText(title),
        color: 'black',
        size: 'l',
        scale: 1,
        autoSize: true,
        textAlign: 'start',
      },
      meta: {},
    },
    {
      id: ids.subtitle,
      typeName: 'shape',
      type: 'text',
      x: 150 + offsetX,
      y: 165 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}2`,
      props: {
        richText: toRichText(`Artifact family: ${family}`),
        color: 'grey',
        size: 's',
        scale: 1,
        autoSize: true,
        textAlign: 'start',
      },
      meta: {},
    },
    {
      id: ids.cardA,
      typeName: 'shape',
      type: 'geo',
      x: 150 + offsetX,
      y: 230 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}3`,
      props: {
        geo: 'rectangle',
        w: 140,
        h: 70,
        color: 'blue',
        fill: 'solid',
        dash: 'draw',
        size: 'm',
        text: 'Concept',
        align: 'middle',
        verticalAlign: 'middle',
        font: 'draw',
        growY: 0,
        url: '',
      },
      meta: {},
    },
    {
      id: ids.cardB,
      typeName: 'shape',
      type: 'geo',
      x: 320 + offsetX,
      y: 230 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}4`,
      props: {
        geo: 'rectangle',
        w: 140,
        h: 70,
        color: 'green',
        fill: 'solid',
        dash: 'draw',
        size: 'm',
        text: 'Visual',
        align: 'middle',
        verticalAlign: 'middle',
        font: 'draw',
        growY: 0,
        url: '',
      },
      meta: {},
    },
    {
      id: ids.cardC,
      typeName: 'shape',
      type: 'geo',
      x: 490 + offsetX,
      y: 230 + offsetY,
      rotation: 0,
      isLocked: false,
      opacity: 1,
      parentId: 'page:page',
      index: `a${turnIndex}5`,
      props: {
        geo: 'rectangle',
        w: 140,
        h: 70,
        color: 'violet',
        fill: 'solid',
        dash: 'draw',
        size: 'm',
        text: 'Notes',
        align: 'middle',
        verticalAlign: 'middle',
        font: 'draw',
        growY: 0,
        url: '',
      },
      meta: {},
    },
  ]
}

function toRichText(text: string) {
  return {
    type: 'doc',
    content: [
      {
        type: 'paragraph',
        content: [{ type: 'text', text }],
      },
    ],
  }
}
