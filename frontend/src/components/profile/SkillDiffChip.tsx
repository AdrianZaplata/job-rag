// Phase 7 Plan 05 — single chip row per CONTEXT.md D-24 (status pill colors) +
// D-26 (inline-edit restricted to added).  PATTERNS §20 / UI-SPEC §6e analog.
//
// One row = checkbox + status pill ([+ ADDED] / [− REMOVED] / [= UNCHANGED])
// + skill name (or shadcn Input when editing) + Pencil affordance (added only).
//
// Inline-edit interactions (D-26):
//   - Click Pencil → swap to Input with autofocus + text selected
//   - Enter → onRename(originalName, trimmed value); revert to static display
//   - Escape → cancel; revert to static display

import { useEffect, useRef, useState } from 'react'
import { Check, Pencil, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import type { DiffItemState } from './types'

export type SkillDiffChipProps = {
  item: DiffItemState
  onToggle: (name: string) => void
  onRename: (name: string, newName: string) => void
  disabled?: boolean
}

// D-24 verbatim status pill classes
const PILL_CLASS: Record<DiffItemState['source'], string> = {
  added: 'bg-green-500/10 text-green-700 dark:text-green-400',
  removed: 'bg-red-500/10 text-red-700 dark:text-red-400',
  unchanged: 'bg-muted text-muted-foreground',
}

// D-24 verbatim status pill labels (U+2212 minus sign for "− REMOVED")
const PILL_LABEL: Record<DiffItemState['source'], string> = {
  added: '+ ADDED',
  removed: '− REMOVED',
  unchanged: '= UNCHANGED',
}

const CHECKBOX_LABEL: Record<DiffItemState['source'], string> = {
  added: 'Confirm skill',
  removed: 'Keep skill',
  unchanged: 'Keep skill',
}

export function SkillDiffChip({
  item,
  onToggle,
  onRename,
  disabled = false,
}: SkillDiffChipProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(item.editedName)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync draft when item.editedName changes from outside (e.g., parent reset).
  useEffect(() => {
    if (!editing) setDraft(item.editedName)
  }, [item.editedName, editing])

  // Auto-focus + select text when entering edit mode (D-26).
  useEffect(() => {
    if (editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [editing])

  const canEdit = item.source === 'added'

  const startEdit = () => {
    if (!canEdit || disabled) return
    setDraft(item.editedName)
    setEditing(true)
  }

  const commitEdit = () => {
    const trimmed = draft.trim()
    if (trimmed === '') {
      // Empty input → cancel the edit (do NOT blank the name). WR-04.
      cancelEdit()
      return
    }
    if (trimmed !== item.editedName) {
      onRename(item.name, trimmed)
    }
    // WR-04: always sync draft to the committed value (even on no-op)
    // so the next pencil-open shows the committed text in the input.
    setEditing(false)
    setDraft(trimmed)
  }

  const cancelEdit = () => {
    setDraft(item.editedName)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commitEdit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      cancelEdit()
    }
  }

  const isEdited = item.editedName !== item.name

  return (
    <li
      data-testid={`chip-${item.name}`}
      data-source={item.source}
      className={[
        'flex items-center gap-2 rounded-sm px-2 py-1.5',
        'hover:bg-muted/50 transition-colors',
        disabled ? 'opacity-50 pointer-events-none' : '',
      ].join(' ')}
    >
      <input
        type="checkbox"
        checked={item.checked}
        onChange={() => onToggle(item.name)}
        aria-label={`${CHECKBOX_LABEL[item.source]} ${item.name}`}
        className="shrink-0 h-4 w-4 cursor-pointer accent-primary"
        disabled={disabled}
      />
      <Badge
        className={`shrink-0 ${PILL_CLASS[item.source]}`}
        data-testid={`pill-${item.source}`}
      >
        {PILL_LABEL[item.source]}
      </Badge>
      {editing && canEdit ? (
        <Input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={cancelEdit}
          aria-label="Edit skill name"
          className="flex-1 h-8 text-sm font-mono"
          data-testid={`edit-input-${item.name}`}
        />
      ) : (
        <span className="flex-1 truncate text-sm font-mono">
          {item.editedName}
          {isEdited && (
            <span className="ml-2 text-xs text-muted-foreground">(edited)</span>
          )}
        </span>
      )}
      {canEdit && !editing && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={startEdit}
          aria-label={`Edit skill name ${item.name}`}
          className="h-7 w-7 p-0"
          disabled={disabled}
          data-testid={`pencil-${item.name}`}
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      )}
      {canEdit && editing && (
        <>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            // onMouseDown so we beat the Input's onBlur cancel
            onMouseDown={(e) => {
              e.preventDefault()
              commitEdit()
            }}
            aria-label="Save edited name"
            className="h-7 w-7 p-0"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onMouseDown={(e) => {
              e.preventDefault()
              cancelEdit()
            }}
            aria-label="Cancel edit"
            className="h-7 w-7 p-0"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </>
      )}
    </li>
  )
}
