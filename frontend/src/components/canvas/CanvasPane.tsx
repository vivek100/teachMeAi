import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Link2, Share2 } from 'lucide-react'
import { Editor, Tldraw, toRichText } from 'tldraw'
import type { CanvasBatch } from '../../runtime/types'

export function CanvasPane({
  batches,
  onBatchApplied,
}: {
  batches: readonly CanvasBatch[]
  onBatchApplied: (batchId: string) => void
}) {
  const editorRef = useRef<Editor | null>(null)
  const appliedRef = useRef<Set<string>>(new Set())
  const [editorReady, setEditorReady] = useState(false)
  const [shareState, setShareState] = useState<'idle' | 'copied'>('idle')

  const shareUrl = useMemo(() => {
    if (typeof window === 'undefined') return 'https://teachwithme.ai/share/demo-session'
    return `${window.location.origin}/share/demo-session`
  }, [])

  useEffect(() => {
    const editor = editorRef.current
    if (!editor) {
      console.debug('TeachWithMeAI canvas: editor not ready yet', { batchCount: batches.length })
      return
    }

    console.debug('TeachWithMeAI canvas: processing batches', {
      batchCount: batches.length,
      appliedCount: appliedRef.current.size,
    })

    for (const batch of batches) {
      if (appliedRef.current.has(batch.batchId)) continue
      console.debug('TeachWithMeAI canvas: attempting batch', batch)
      const applied = applyBatch(editor, batch)
      if (!applied) {
        console.warn('TeachWithMeAI canvas: batch produced no applied ops', batch)
        continue
      }
      console.debug('TeachWithMeAI canvas: batch applied successfully', {
        batchId: batch.batchId,
        artifactId: batch.artifactId,
      })
      appliedRef.current.add(batch.batchId)
      onBatchApplied(batch.batchId)
    }
  }, [batches, editorReady, onBatchApplied])

  useEffect(() => {
    if (shareState !== 'copied') return
    const handle = window.setTimeout(() => setShareState('idle'), 2200)
    return () => window.clearTimeout(handle)
  }, [shareState])

  const handleMockShare = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
    } catch {
      // Demo-only affordance; if clipboard is blocked, we still show success state.
    }
    setShareState('copied')
  }

  return (
    <div className="relative h-full w-full bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.08),_transparent_28%),linear-gradient(180deg,_rgba(255,255,255,0.02),_rgba(255,255,255,0))]">
      <div className="absolute left-4 right-4 top-4 z-10 flex items-start justify-between gap-3">
        <div className="rounded-[14px] border border-white/10 bg-neutral-950/80 px-3 py-2.5 backdrop-blur">
          <div className="text-[11px] uppercase tracking-[0.18em] text-cyan-300/80">Canvas</div>
          <div className="mt-1 text-[13px] text-neutral-200">tldraw board for artifact placement and lecture visuals</div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleMockShare}
            className="inline-flex items-center gap-2 rounded-[12px] border border-white/10 bg-neutral-950/80 px-3 py-2 text-[12px] text-neutral-200 backdrop-blur transition-colors hover:bg-neutral-900"
          >
            {shareState === 'copied' ? <Check className="h-3.5 w-3.5" /> : <Share2 className="h-3.5 w-3.5" />}
            {shareState === 'copied' ? 'Shared link copied' : 'Mock share notes'}
          </button>
          <div className="rounded-[12px] border border-dashed border-cyan-400/25 bg-cyan-400/8 px-3 py-2 text-[11px] text-cyan-100">
            Teacher share demo
          </div>
        </div>
      </div>

      <div className="absolute right-4 top-20 z-10 max-w-[280px] rounded-[14px] border border-white/10 bg-neutral-950/72 px-3 py-2 text-[11px] leading-5 text-neutral-300 backdrop-blur">
        <div className="mb-1 flex items-center gap-2 text-neutral-100">
          <Link2 className="h-3.5 w-3.5 text-cyan-300" />
          Shareable notes snapshot
        </div>
        <div className="truncate text-neutral-400">{shareUrl}</div>
        <div className="mt-1 text-neutral-500">Demo flow: teacher shares the currently generated board notes with students.</div>
      </div>
      <Tldraw
        onMount={(editor) => {
          editorRef.current = editor
          setEditorReady(true)
          console.debug('TeachWithMeAI canvas: tldraw mounted', {
            currentPageId: editor.getCurrentPageId(),
          })
        }}
      />
    </div>
  )
}

function applyBatch(editor: Editor, batch: CanvasBatch) {
  let appliedOps = 0

  editor.run(() => {
    for (const [shapeIndex, op] of batch.ops.entries()) {
      console.debug('TeachWithMeAI canvas: applying op', {
        batchId: batch.batchId,
        shapeIndex,
        opType: op.opType,
        op,
      })
      switch (op.opType) {
        case 'create_shape':
          if (op.shape) {
            const normalizedShape = normalizeCreateShape(editor, op.shape, shapeIndex)
            if (!normalizedShape) {
              console.warn('TeachWithMeAI canvas: create_shape normalization returned null', op.shape)
              break
            }
            console.debug('TeachWithMeAI canvas: normalized create shape', normalizedShape)
            try {
              editor.createShapes([normalizedShape as never])
              appliedOps += 1
            } catch (error) {
              console.error('TeachWithMeAI: failed to create demo shape', normalizedShape, error)
            }
          }
          break
        case 'update_shape':
          if (op.shape) {
            try {
              editor.updateShapes([op.shape as never])
              appliedOps += 1
            } catch (error) {
              console.error('TeachWithMeAI: failed to update shape', op.shape, error)
            }
          }
          break
        case 'delete_shape':
          if (op.shapeId) {
            try {
              editor.deleteShapes([op.shapeId as never])
              appliedOps += 1
            } catch (error) {
              console.error('TeachWithMeAI: failed to delete shape', op.shapeId, error)
            }
          }
          break
        case 'set_camera':
          if (op.camera) {
            editor.setCamera(op.camera)
            appliedOps += 1
          }
          break
        default:
          break
      }
    }
  })

  return appliedOps > 0
}

function normalizeCreateShape(editor: Editor, shape: Record<string, unknown>, shapeIndex: number) {
  const type = typeof shape.type === 'string' ? shape.type : null
  if (!type) return null

  const pageId = editor.getCurrentPageId()
  const props = typeof shape.props === 'object' && shape.props ? { ...(shape.props as Record<string, unknown>) } : {}

  // tldraw v4+ uses `richText` instead of `text` in shape props.
  // Convert legacy `text` prop to `richText` for compatible shape types.
  if ('text' in props && typeof props.text === 'string') {
    const richTextTypes = new Set(['geo', 'text', 'note', 'arrow'])
    if (richTextTypes.has(type)) {
      props.richText = toRichText(props.text as string)
      delete props.text
    }
  }

  return {
    ...shape,
    id: typeof shape.id === 'string' ? shape.id : `shape:demo:${crypto.randomUUID()}`,
    type,
    x: Number(shape.x ?? 0),
    y: Number(shape.y ?? 0),
    rotation: Number(shape.rotation ?? 0),
    opacity: Number(shape.opacity ?? 1),
    parentId: pageId,
    index: typeof shape.index === 'string' ? shape.index : `a${shapeIndex}`,
    props,
  }
}
