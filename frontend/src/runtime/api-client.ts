import type { BackendArtifactRecord, BackendBatchRecord, BackendEventRecord } from './types'
import { runtimeDebug } from './debug'

const API_BASE = import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'

export function getSessionWebSocketUrl(sessionId: string) {
  const url = new URL(`${API_BASE}/ws/sessions/${sessionId}`)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export async function createSession() {
  runtimeDebug.info('api', 'creating session')
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lecture_id: 'intro_to_llms' }),
  })

  if (!response.ok) {
    runtimeDebug.error('api', 'create session failed', { status: response.status })
    throw new Error(`Failed to create session (${response.status})`)
  }

  const data = (await response.json()) as { session_id: string; lecture_id: string }
  runtimeDebug.info('api', 'session created', data)
  return data
}

export async function sendChunk(sessionId: string, text: string) {
  runtimeDebug.info('api', 'sending chunk', { sessionId, textLength: text.length })
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/chunks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, source: 'user_command' }),
  })

  if (!response.ok) {
    runtimeDebug.error('api', 'send chunk failed', { sessionId, status: response.status })
    throw new Error(`Failed to send chunk (${response.status})`)
  }

  const data = (await response.json()) as {
    chunk_id: string
    window_triggered: boolean
    batch: { batch_id: string; op_count: number; artifact_id: string | null } | null
  }
  runtimeDebug.info('api', 'chunk sent', {
    sessionId,
    chunkId: data.chunk_id,
    windowTriggered: data.window_triggered,
    batchId: data.batch?.batch_id ?? null,
  })
  return data
}

export async function getEvents(sessionId: string) {
  runtimeDebug.debug('api', 'fetching events', { sessionId })
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/events`)

  if (!response.ok) {
    throw new Error(`Failed to fetch events (${response.status})`)
  }

  const data = (await response.json()) as { events: BackendEventRecord[] }
  runtimeDebug.debug('api', 'events fetched', { sessionId, count: data.events.length })
  return data.events
}

export async function getBatches(sessionId: string) {
  runtimeDebug.debug('api', 'fetching batches', { sessionId })
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/batches`)

  if (!response.ok) {
    throw new Error(`Failed to fetch batches (${response.status})`)
  }

  const data = (await response.json()) as { batches: BackendBatchRecord[] }
  runtimeDebug.debug('api', 'batches fetched', { sessionId, count: data.batches.length })
  return data.batches
}

export async function getArtifacts() {
  runtimeDebug.debug('api', 'fetching artifacts')
  const response = await fetch(`${API_BASE}/artifacts`)

  if (!response.ok) {
    throw new Error(`Failed to fetch artifacts (${response.status})`)
  }

  const data = (await response.json()) as { artifacts: BackendArtifactRecord[] }
  runtimeDebug.debug('api', 'artifacts fetched', { count: data.artifacts.length })
  return data.artifacts
}
