import { useEffect, useState, type CSSProperties } from 'react'
import {
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
} from '@assistant-ui/react'
import { ArrowDown, ArrowUp, BookOpenText, Boxes, MessageSquare, Mic, Square, Waves } from 'lucide-react'
import { mockArtifacts } from '../../demo/mock-artifacts'
import { lectureNotes } from '../../demo/lecture-notes'
import { getArtifacts } from '../../runtime/api-client'
import type { BackendArtifactRecord } from '../../runtime/types'
import { MarkdownText } from './markdown-text'
import { Reasoning } from './Reasoning'
import { ToolCallCard } from './ToolCallCard'

const SUGGESTIONS = [
  {
    title: 'Explain tokenization',
    description: 'Break a sentence into tokens and show a token grid.',
    prompt: 'Let us explain tokenization with a token grid example.',
  },
  {
    title: 'Move to attention',
    description: 'Show self-attention with a matrix-style artifact.',
    prompt: 'Now let us move into self-attention and visualize the attention matrix.',
  },
]

const AUTO_SEND_CHAR_THRESHOLD = 140

export function ThreadPanel({
  sessionId,
  isRunning,
  backendStatus,
  error,
  submitTranscriptChunk,
}: {
  sessionId: string | null
  isRunning: boolean
  backendStatus: string
  error: string | null
  submitTranscriptChunk: (text: string) => Promise<void>
}) {
  const [tab, setTab] = useState<'chat' | 'notes' | 'artifacts'>('chat')
  const [artifacts, setArtifacts] = useState<BackendArtifactRecord[]>([])
  const [artifactError, setArtifactError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadArtifacts = async () => {
      try {
        const data = await getArtifacts()
        if (!cancelled) {
          setArtifacts(data.length > 0 ? data : mockArtifacts)
          setArtifactError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setArtifacts(mockArtifacts)
          setArtifactError(null)
        }
      }
    }

    loadArtifacts()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root flex h-full flex-col bg-neutral-950"
      style={
        {
          '--thread-max-width': '44rem',
          '--composer-radius': '12px',
          '--composer-padding': '6px',
        } as CSSProperties
      }
    >
      <ThreadPrimitive.Viewport className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-hidden overflow-y-auto scroll-smooth px-2.5 pt-2.5">
        <StatusPanel sessionId={sessionId} isRunning={isRunning} backendStatus={backendStatus} error={error} />
        <SidebarTabs tab={tab} onChange={setTab} />

        {tab === 'chat' ? (
          <>
            <DictationAutoSend submitTranscriptChunk={submitTranscriptChunk} />
            <AuiIf condition={(state) => state.thread.isEmpty}>
              <ThreadWelcome />
            </AuiIf>

            <ThreadPrimitive.Messages>{() => <ThreadMessage />}</ThreadPrimitive.Messages>

            <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-2 overflow-visible rounded-t-(--composer-radius) bg-gradient-to-t from-neutral-950 via-neutral-950 to-neutral-950/88 pb-2.5 pt-1.5">
              <ThreadPrimitive.ScrollToBottom asChild>
                <button
                  type="button"
                  className="aui-thread-scroll-to-bottom absolute -top-9 self-center rounded-full border border-neutral-800 bg-neutral-900 p-1.5 text-neutral-400 transition-colors hover:text-neutral-100 disabled:invisible"
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
              </ThreadPrimitive.ScrollToBottom>
              <AuiIf condition={(state) => state.thread.isEmpty}>
                <ThreadSuggestions />
              </AuiIf>
              <Composer submitTranscriptChunk={submitTranscriptChunk} />
            </ThreadPrimitive.ViewportFooter>
          </>
        ) : null}

        {tab === 'notes' ? <LectureNotesPanel /> : null}
        {tab === 'artifacts' ? <ArtifactsPanel artifacts={artifacts} error={artifactError} /> : null}
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  )
}

function DictationAutoSend({ submitTranscriptChunk }: { submitTranscriptChunk: (text: string) => Promise<void> }) {
  const aui = useAui()
  const text = useAuiState((state) => state.composer.text)
  const dictation = useAuiState((state) => state.composer.dictation)
  const isRunning = useAuiState((state) => state.thread.isRunning)
  const [lastSubmittedText, setLastSubmittedText] = useState('')

  useEffect(() => {
    const trimmed = text.trim()
    if (!dictation || isRunning) return
    if (trimmed.length < AUTO_SEND_CHAR_THRESHOLD) return
    if (trimmed === lastSubmittedText) return

    setLastSubmittedText(trimmed)
    void submitTranscriptChunk(trimmed).then(() => {
      aui.composer().setText('')
    })
  }, [aui, dictation, isRunning, lastSubmittedText, submitTranscriptChunk, text])

  useEffect(() => {
    if (text.trim().length === 0) {
      setLastSubmittedText('')
    }
  }, [text])

  return null
}

function SidebarTabs({
  tab,
  onChange,
}: {
  tab: 'chat' | 'notes' | 'artifacts'
  onChange: (tab: 'chat' | 'notes' | 'artifacts') => void
}) {
  const items = [
    { id: 'chat' as const, label: 'Chat', icon: MessageSquare },
    { id: 'notes' as const, label: 'Lecture Notes', icon: BookOpenText },
    { id: 'artifacts' as const, label: 'Artifacts', icon: Boxes },
  ]

  return (
    <div className="mx-auto mb-2 flex w-full max-w-(--thread-max-width) gap-1 rounded-[10px] border border-white/8 bg-white/[0.02] p-1">
      {items.map((item) => {
        const Icon = item.icon
        const active = tab === item.id
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={
              active
                ? 'flex flex-1 items-center justify-center gap-1.5 rounded-[8px] bg-cyan-400/15 px-2.5 py-1.5 text-[12px] font-medium text-cyan-200'
                : 'flex flex-1 items-center justify-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12px] text-neutral-400 transition-colors hover:bg-white/[0.04] hover:text-neutral-200'
            }
          >
            <Icon className="h-3.5 w-3.5" />
            {item.label}
          </button>
        )
      })}
    </div>
  )
}

function StatusPanel({
  sessionId,
  isRunning,
  backendStatus,
  error,
}: {
  sessionId: string | null
  isRunning: boolean
  backendStatus: string
  error: string | null
}) {
  return (
    <div className="mx-auto mb-2.5 w-full max-w-(--thread-max-width) rounded-[12px] border border-white/8 bg-white/[0.025] p-2.5">
      <div className="flex items-start justify-between gap-2.5">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-cyan-300/80">TeachWithMeAI</div>
          <h1 className="mt-0.5 text-[17px] font-semibold text-neutral-50">Lecture Copilot</h1>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-neutral-300">
          {isRunning ? 'Streaming' : 'Idle'}
        </div>
      </div>
      <div className="mt-2.5 grid gap-1.5">
        <StatusRow label="Session" value={sessionId ?? 'Not created yet'} />
        <StatusRow label="Backend" value={backendStatus} />
        {error ? <StatusRow label="Error" value={error} danger /> : null}
      </div>
    </div>
  )
}

function StatusRow({
  label,
  value,
  danger = false,
}: {
  label: string
  value: string
  danger?: boolean
}) {
  return (
    <div className="flex items-center justify-between rounded-[10px] border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-[12px]">
      <span className="text-neutral-500">{label}</span>
      <span className={danger ? 'max-w-[70%] text-right text-red-300' : 'max-w-[70%] text-right text-neutral-200'}>
        {value}
      </span>
    </div>
  )
}

function ThreadWelcome() {
  return (
    <div className="aui-thread-welcome-root mx-auto my-auto flex w-full max-w-(--thread-max-width) grow flex-col">
      <div className="aui-thread-welcome-center flex w-full grow flex-col items-center justify-center">
        <div className="aui-thread-welcome-message flex size-full flex-col justify-center px-2 text-center">
          <div className="mx-auto mb-2.5 flex h-10 w-10 items-center justify-center rounded-[12px] bg-cyan-400/10 text-cyan-300">
            <Waves className="h-4.5 w-4.5" />
          </div>
          <h2 className="font-semibold text-[1.55rem] leading-tight text-neutral-100">Start a teaching session</h2>
          <p className="mt-1.5 text-neutral-400 text-[12px] leading-5">
            Send a lecture chunk and TeachWithMeAI will create the session, infer the topic, and render visual artifacts
            on the board.
          </p>
        </div>
      </div>
    </div>
  )
}

function LectureNotesPanel() {
  return (
    <div className="mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-2 pb-2">
      <PanelIntro
        title="Lecture Notes"
        description="This is the teaching plan and concept summary the agent can rely on during the demo."
      />
      {lectureNotes.map((section) => (
        <section key={section.id} className="rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2.5">
          <h3 className="text-[12px] font-semibold text-neutral-100">{section.title}</h3>
          <ul className="mt-2 space-y-1 text-[12px] leading-5 text-neutral-300">
            {section.bullets.map((bullet) => (
              <li key={bullet} className="flex gap-2">
                <span className="mt-[7px] h-1 w-1 rounded-full bg-cyan-300/80" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function ArtifactsPanel({
  artifacts,
  error,
}: {
  artifacts: BackendArtifactRecord[]
  error: string | null
}) {
  return (
    <div className="mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-2 pb-2">
      <PanelIntro
        title="Primitive Artifacts"
        description="These are the predefined visual primitives the agent can instantiate during the lecture."
      />
      {error ? <div className="rounded-[12px] border border-red-500/20 bg-red-500/8 px-3 py-2 text-[12px] text-red-200">{error}</div> : null}
      {artifacts.map((artifact) => (
        <section key={artifact.artifact_id} className="rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2.5">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="text-[12px] font-semibold text-neutral-100">{artifact.title || artifact.artifact_id}</h3>
              <p className="mt-1 text-[11px] text-neutral-400">{artifact.description || artifact.family}</p>
            </div>
            <div className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[10px] uppercase tracking-wide text-neutral-300">
              {artifact.family}
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {artifact.tags.map((tag) => (
              <span key={tag} className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[10px] text-neutral-300">
                {tag}
              </span>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-neutral-500">
            {artifact.shape_template.length} shapes · {Object.keys(artifact.parameters ?? {}).length} parameters
          </div>
        </section>
      ))}
      {!error && artifacts.length === 0 ? (
        <div className="rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2 text-[12px] text-neutral-400">
          No artifacts loaded yet.
        </div>
      ) : null}
    </div>
  )
}

function PanelIntro({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2.5">
      <div className="text-[12px] font-semibold text-neutral-100">{title}</div>
      <div className="mt-1 text-[11px] leading-5 text-neutral-400">{description}</div>
    </div>
  )
}

function ThreadSuggestions() {
  return (
    <div className="aui-thread-welcome-suggestions grid w-full @md:grid-cols-2 gap-1.5">
      {SUGGESTIONS.map((suggestion) => (
        <ThreadPrimitive.Suggestion key={suggestion.title} prompt={suggestion.prompt} send asChild>
          <button
            type="button"
            className="aui-thread-welcome-suggestion h-auto w-full rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2.5 text-left text-[12px] transition-colors hover:bg-white/[0.05]"
          >
            <div className="font-medium text-[12px] text-neutral-100">{suggestion.title}</div>
            <div className="mt-1 text-neutral-400 text-[11px] leading-4.5">{suggestion.description}</div>
          </button>
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  )
}

function Composer({ submitTranscriptChunk }: { submitTranscriptChunk: (text: string) => Promise<void> }) {
  return (
    <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
      <ComposerPrimitive.AttachmentDropzone asChild>
        <div className="flex w-full flex-col gap-1.5 rounded-(--composer-radius) border border-white/10 bg-neutral-900 p-(--composer-padding) shadow-[0_9px_9px_0px_rgba(0,0,0,0.01),0_2px_5px_0px_rgba(0,0,0,0.06)] transition-shadow focus-within:border-cyan-400/40 focus-within:ring-1 focus-within:ring-cyan-400/10 data-[dragging=true]:border-cyan-300 data-[dragging=true]:bg-white/[0.04]">
          <div className="px-1 pt-0.5 text-[11px] uppercase tracking-[0.18em] text-neutral-500">Transcript / command input</div>
          <ComposerPrimitive.Input
            placeholder="Speak or type a lecture chunk, for example: 'now let us move into self-attention'"
            className="aui-composer-input max-h-24 min-h-14 w-full resize-none bg-transparent px-2 py-1 text-[13px] leading-5.5 text-neutral-100 outline-none placeholder:text-neutral-500"
            rows={1}
            submitMode="none"
            autoFocus
            aria-label="Message input"
          />
          <AuiIf condition={(state) => state.composer.dictation != null}>
            <div className="rounded-[10px] border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1.5 text-[12px] text-cyan-100">
              <ComposerPrimitive.DictationTranscript />
            </div>
          </AuiIf>
          <ComposerAction submitTranscriptChunk={submitTranscriptChunk} />
        </div>
      </ComposerPrimitive.AttachmentDropzone>
    </ComposerPrimitive.Root>
  )
}

function ComposerAction({ submitTranscriptChunk }: { submitTranscriptChunk: (text: string) => Promise<void> }) {
  const aui = useAui()
  const canSend = useAuiState((state) => !state.thread.isRunning && !state.composer.isEmpty)
  const dictation = useAuiState((state) => state.composer.dictation)

  const handleSend = async () => {
    const text = aui.composer().getState().text.trim()
    if (!text) return
    await submitTranscriptChunk(text)
    aui.composer().setText('')
    if (dictation) {
      window.setTimeout(() => {
        try {
          aui.composer().startDictation()
        } catch {
          // Keep the send path reliable even if the adapter refuses an immediate restart.
        }
      }, 150)
    }
  }

  return (
    <div className="aui-composer-action-wrapper relative flex items-center justify-between pt-0.5">
      <div className="flex items-center gap-2">
        <AuiIf condition={(state) => state.composer.dictation == null}>
          <ComposerPrimitive.Dictate asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[12px] text-neutral-300 transition-colors hover:bg-white/[0.08] hover:text-neutral-50"
            >
              <Mic className="h-3.5 w-3.5" />
              Dictate
            </button>
          </ComposerPrimitive.Dictate>
        </AuiIf>
        <AuiIf condition={(state) => state.composer.dictation != null}>
          <ComposerPrimitive.StopDictation asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[12px] text-red-200 transition-colors hover:bg-red-500/15"
            >
              <Square className="h-3.5 w-3.5" />
              Stop dictation
            </button>
          </ComposerPrimitive.StopDictation>
        </AuiIf>
      </div>

      <ThreadPrimitive.If running={false}>
        <button
          type="button"
          disabled={!canSend}
          onClick={() => void handleSend()}
          className="aui-composer-send inline-flex size-8 items-center justify-center rounded-full bg-cyan-400 text-neutral-950 transition-opacity hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Send message"
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
      </ThreadPrimitive.If>

      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel asChild>
          <button
            type="button"
            className="aui-composer-cancel inline-flex size-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-neutral-300 transition-colors hover:bg-white/[0.08]"
            aria-label="Stop generating"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </div>
  )
}

function ThreadMessage() {
  const role = useAuiState((state) => state.message.role)
  if (role === 'user') return <UserMessage />
  return <AssistantMessage />
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-user-message-root mx-auto grid w-full max-w-(--thread-max-width) auto-rows-auto grid-cols-[minmax(40px,1fr)_auto] gap-y-1 px-1.5 py-1.5 [&:where(>*)]:col-start-2">
      <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
        <div className="aui-user-message-content break-words rounded-[10px] bg-neutral-800 px-3 py-1.5 text-[12px] leading-5 text-neutral-100">
          <MessagePrimitive.Parts />
        </div>
      </div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  const createdAt = useAuiState((state) => state.message.createdAt)

  return (
    <MessagePrimitive.Root className="aui-assistant-message-root relative mx-auto w-full max-w-(--thread-max-width) py-1.5">
      <div className="rounded-[12px] border border-white/8 bg-white/[0.025] px-3 py-2.5">
        <div className="mb-1.5 flex items-center justify-between">
          <div className="text-[13px] font-medium text-neutral-100">TeachWithMeAI</div>
          <div className="text-[11px] text-neutral-500">{createdAt ? createdAt.toLocaleTimeString() : ''}</div>
        </div>
        <div className="text-[12px] leading-5 text-neutral-200">
          <MessagePrimitive.Parts>
            {({ part }) => {
              if (part.type === 'text') return <MarkdownText />
              if (part.type === 'reasoning') return <Reasoning text={part.text} />
              if (part.type === 'tool-call') return <ToolCallCard part={part} />
              return null
            }}
          </MessagePrimitive.Parts>
        </div>
      </div>
    </MessagePrimitive.Root>
  )
}
