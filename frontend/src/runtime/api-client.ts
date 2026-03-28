import type { BackendArtifactRecord, BackendBatchRecord, BackendEventRecord } from './types'

const API_BASE = import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'

export async function createSession() {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lecture_id: 'intro_to_llms' }),
  })

  if (!response.ok) {
    throw new Error(`Failed to create session (${response.status})`)
  }

  return (await response.json()) as { session_id: string; lecture_id: string }
}

export async function sendChunk(sessionId: string, text: string) {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/chunks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, source: 'user_command' }),
  })

  if (!response.ok) {
    throw new Error(`Failed to send chunk (${response.status})`)
  }

  return (await response.json()) as {
    chunk_id: string
    window_triggered: boolean
    batch: { batch_id: string; op_count: number; artifact_id: string | null } | null
  }
}

export async function getEvents(sessionId: string) {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/events`)

  if (!response.ok) {
    throw new Error(`Failed to fetch events (${response.status})`)
  }

  const data = (await response.json()) as { events: BackendEventRecord[] }
  return data.events
}

export async function getBatches(sessionId: string) {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/batches`)

  if (!response.ok) {
    throw new Error(`Failed to fetch batches (${response.status})`)
  }

  const data = (await response.json()) as { batches: BackendBatchRecord[] }
  return data.batches
}

export async function getArtifacts() {
  const response = await fetch(`${API_BASE}/artifacts`)

  if (!response.ok) {
    throw new Error(`Failed to fetch artifacts (${response.status})`)
  }

  const data = (await response.json()) as { artifacts: BackendArtifactRecord[] }
  return data.artifacts
}
