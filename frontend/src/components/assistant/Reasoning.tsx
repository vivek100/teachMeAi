import { Brain, ChevronDown } from 'lucide-react'
import { useState } from 'react'

export function Reasoning({ text, defaultOpen = false }: { text: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="mb-4 overflow-hidden rounded-2xl border border-neutral-800/90 bg-neutral-900/70">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-neutral-400 transition-colors hover:bg-neutral-900 hover:text-neutral-200"
      >
        <Brain className="h-4 w-4" />
        <span className="flex-1">Reasoning</span>
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? (
        <div className="border-t border-neutral-800/80 px-3 py-3 text-sm text-neutral-300">
          <pre className="whitespace-pre-wrap font-mono">{text}</pre>
        </div>
      ) : null}
    </div>
  )
}
