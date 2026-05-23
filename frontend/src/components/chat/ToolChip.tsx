/**
 * Phase 6 Plan 04 — ToolChip presentation component (UI-SPEC §6c verbatim).
 *
 * Renders a tool-call TranscriptItem in 3 visual states:
 *  - running (output === null): pulsing dot, expand disabled (D-13)
 *  - done collapsed: header shows tool name + JSON args preview + ChevronRight
 *  - done expanded: pretty-printed args + 200-char output preview + optional
 *                   "Show full output" Button that opens a Dialog with full
 *                   output in a scrollable <pre> (D-12)
 *
 * Composition primitives:
 *  - shadcn Collapsible (Wave 0 install) for expand/collapse
 *  - shadcn Dialog (Phase 4) for full-output modal (mirrors TopSkillsDialog shape)
 *  - shadcn Button link variant for "Show full output" CTA
 *  - lucide ArrowRight (call semantic, D-10) + ChevronRight (expand indicator)
 */

import { useState } from 'react'
import { ArrowRight, ChevronRight } from 'lucide-react'

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { TranscriptItem } from '@/components/chat/types'

type ToolCallItem = Extract<TranscriptItem, { kind: 'tool-call' }>

export type ToolChipProps = {
  item: ToolCallItem
  onToggleExpand: (id: string) => void
}

export function ToolChip({ item, onToggleExpand }: ToolChipProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const running = item.output === null
  const truncated = !running && (item.output as string).length > 200
  const preview = running
    ? ''
    : truncated
      ? (item.output as string).slice(0, 200) + '…'
      : (item.output as string)
  const argsPreview = item.args === null ? '' : JSON.stringify(item.args)
  const argsPretty = item.args === null ? '' : JSON.stringify(item.args, null, 2)

  return (
    <li>
      <Collapsible
        open={item.expanded}
        onOpenChange={() => onToggleExpand(item.id)}
        className="rounded-md border bg-card"
      >
        <CollapsibleTrigger
          disabled={running}
          className="flex w-full items-center gap-2 p-2 text-left hover:bg-muted/50 transition-colors disabled:cursor-not-allowed disabled:opacity-90"
          aria-expanded={item.expanded}
          aria-controls={`tool-${item.id}-body`}
        >
          <ArrowRight
            className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <span className="text-sm font-mono shrink-0">{item.name}</span>
          {argsPreview && (
            <span className="text-xs font-mono text-muted-foreground truncate min-w-0 flex-1">
              {argsPreview}
            </span>
          )}
          {running && (
            <span
              className="text-muted-foreground animate-pulse shrink-0"
              aria-hidden="true"
            >
              ·
            </span>
          )}
          {!running && (
            <ChevronRight
              className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform data-[state=open]:rotate-90"
              aria-hidden="true"
            />
          )}
        </CollapsibleTrigger>
        <CollapsibleContent
          id={`tool-${item.id}-body`}
          className="space-y-2 px-2 pb-2"
        >
          {argsPretty && (
            <div>
              <div className="text-xs text-muted-foreground">args</div>
              <pre className="mt-1 max-w-full overflow-x-auto rounded-sm bg-muted p-2 text-xs font-mono whitespace-pre-wrap">
                {argsPretty}
              </pre>
            </div>
          )}
          {!running && (
            <div>
              <div className="text-xs text-muted-foreground">output</div>
              <pre className="mt-1 max-w-full overflow-x-auto rounded-sm bg-muted p-2 text-xs font-mono whitespace-pre-wrap">
                {preview}
              </pre>
              {truncated && (
                <div className="flex justify-end pt-1">
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => setDialogOpen(true)}
                  >
                    Show full output
                  </Button>
                </div>
              )}
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>

      {/* Full-output Dialog — mirrors TopSkillsDialog (Phase 5) shape */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Tool output</DialogTitle>
            <DialogDescription>
              Full output of <span className="font-mono">{item.name}</span>
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-y-auto">
            <pre className="rounded-sm bg-muted p-2 text-xs font-mono whitespace-pre-wrap">
              {item.output ?? ''}
            </pre>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  )
}
