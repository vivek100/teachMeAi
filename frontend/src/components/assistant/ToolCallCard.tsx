type ToolCallPart = {
  toolName: string
  toolCallId?: string
  args?: unknown
  result?: unknown
  isError?: boolean
}

export function ToolCallCard({ part }: { part: ToolCallPart }) {
  return (
    <div className="mb-4 overflow-hidden rounded-2xl border border-neutral-800/90 bg-neutral-900/75">
      <div className="flex items-center justify-between border-b border-neutral-800/80 px-3 py-2">
        <div className="text-sm font-medium text-neutral-100">{part.toolName}</div>
        {part.toolCallId ? (
          <div className="rounded-full border border-neutral-700/80 bg-neutral-950/80 px-2 py-0.5 text-[10px] uppercase tracking-wide text-neutral-400">
            {part.toolCallId}
          </div>
        ) : null}
      </div>
      <div className="space-y-3 px-3 py-3 text-sm">
        {part.args ? (
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">Args</div>
            <pre className="overflow-x-auto rounded-xl bg-neutral-950/80 p-3 text-xs text-neutral-300">
              {JSON.stringify(part.args, null, 2)}
            </pre>
          </div>
        ) : null}
        {part.result ? (
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">Result</div>
            <pre className="overflow-x-auto rounded-xl bg-neutral-950/80 p-3 text-xs text-neutral-300">
              {JSON.stringify(part.result, null, 2)}
            </pre>
          </div>
        ) : null}
        {part.isError ? <div className="text-xs text-red-300">This tool call completed with an error.</div> : null}
      </div>
    </div>
  )
}
