import type { ReactNode } from 'react'

export function AppShell({
  sidebar,
  canvas,
}: {
  sidebar: ReactNode
  canvas: ReactNode
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(82,123,255,0.14),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(36,196,181,0.10),_transparent_28%),linear-gradient(180deg,_#09090b,_#111114_55%,_#0b0b0d)] text-neutral-100">
      <div className="mx-auto flex h-screen max-w-[1800px] gap-2 p-2">
        <aside className="flex w-[350px] min-w-[320px] flex-col overflow-hidden rounded-[14px] border border-white/8 bg-neutral-950/90 shadow-[0_20px_80px_rgba(0,0,0,0.38)] backdrop-blur-xl">
          {sidebar}
        </aside>
        <main className="min-w-0 flex-1 overflow-hidden rounded-[16px] border border-white/8 bg-neutral-950/75 shadow-[0_20px_80px_rgba(0,0,0,0.38)] backdrop-blur-xl">
          {canvas}
        </main>
      </div>
    </div>
  )
}
