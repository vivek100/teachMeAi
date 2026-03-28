import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { ThreadPanel } from './components/assistant/ThreadPanel'
import { CanvasPane } from './components/canvas/CanvasPane'
import { AppShell } from './components/layout/AppShell'
import { useTeachWithMeRuntime } from './runtime/useTeachWithMeRuntime'

export default function App() {
  const runtimeState = useTeachWithMeRuntime()

  return (
    <AssistantRuntimeProvider runtime={runtimeState.runtime}>
      <AppShell
        sidebar={
          <ThreadPanel
            sessionId={runtimeState.sessionId}
            isRunning={runtimeState.isRunning}
            backendStatus={runtimeState.backendStatus}
            error={runtimeState.error}
            submitTranscriptChunk={runtimeState.submitTranscriptChunk}
          />
        }
        canvas={
          <CanvasPane
            batches={runtimeState.canvasBatches}
            onBatchApplied={runtimeState.markBatchApplied}
          />
        }
      />
    </AssistantRuntimeProvider>
  )
}
