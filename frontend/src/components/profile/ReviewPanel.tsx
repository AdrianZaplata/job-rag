// Phase 7 Plan 05 — review panel per CONTEXT.md D-27 (single Card + sticky footer)
// + D-25 (live count save label).  PATTERNS §19 / UI-SPEC §6d analog.
//
// Composes <SkillDiffChip> for each row inside a single shadcn <Card> with a
// sticky <CardFooter>. Footer carries Discard + dynamic Save label per D-25:
//   Save (N new · M keep removed · K unchanged)
//
// Save handler composes the UserProfileUpdate per D-21:
//   - skills = checked items mapped to { name: editedName }
//   - other fields = null  (v1 review panel only edits skills per D-Discretion)
//   - extraction_id = the upload's UUID  (Langfuse correlation per D-32)

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

import { SkillDiffChip } from './SkillDiffChip'
import type { DiffItemState, UserProfileUpdate } from './types'

export type ReviewPanelProps = {
  diff: DiffItemState[]
  extractionId: string
  onSave: (payload: UserProfileUpdate) => void
  onCancel: () => void
  isSaving: boolean
  setDiff: (diff: DiffItemState[]) => void
}

export function ReviewPanel({
  diff,
  extractionId,
  onSave,
  onCancel,
  isSaving,
  setDiff,
}: ReviewPanelProps) {
  const [localDiff, setLocalDiff] = useState<DiffItemState[]>(diff)

  // Whenever upstream diff array changes (new upload), reset local.
  // Keep upstream synchronised via setDiff for parents that read it back.
  const update = (next: DiffItemState[]) => {
    setLocalDiff(next)
    setDiff(next)
  }

  const handleToggle = (name: string) => {
    update(
      localDiff.map((d) =>
        d.name === name ? { ...d, checked: !d.checked } : d,
      ),
    )
  }

  const handleRename = (name: string, newName: string) => {
    update(
      localDiff.map((d) =>
        d.name === name ? { ...d, editedName: newName } : d,
      ),
    )
  }

  // Live counts (D-25 / D-27 verbatim)
  const counts = {
    extracted: localDiff.length,
    added: localDiff.filter((d) => d.source === 'added').length,
    removed: localDiff.filter((d) => d.source === 'removed').length,
    unchanged: localDiff.filter((d) => d.source === 'unchanged').length,
    addedChecked: localDiff.filter((d) => d.source === 'added' && d.checked)
      .length,
    removedChecked: localDiff.filter(
      (d) => d.source === 'removed' && d.checked,
    ).length,
    unchangedChecked: localDiff.filter(
      (d) => d.source === 'unchanged' && d.checked,
    ).length,
  }

  const checkedTotal =
    counts.addedChecked + counts.removedChecked + counts.unchangedChecked

  const handleSave = () => {
    const skills = localDiff
      .filter((d) => d.checked)
      .map((d) => ({ name: d.editedName }))
    onSave({
      skills,
      target_roles: null,
      preferred_locations: null,
      min_salary_eur: null,
      remote_preference: null,
      extraction_id: extractionId,
    })
  }

  return (
    <Card data-testid="review-panel">
      <CardHeader>
        <CardTitle>Review extracted skills</CardTitle>
        <CardDescription>
          {counts.extracted} skills found · {counts.added} new ·{' '}
          {counts.removed} removed · {counts.unchanged} unchanged
        </CardDescription>
      </CardHeader>
      <CardContent className="max-h-[60vh] overflow-y-auto">
        <ul className="space-y-1 list-none">
          {localDiff.map((item) => (
            <SkillDiffChip
              key={item.name}
              item={item}
              onToggle={handleToggle}
              onRename={handleRename}
              disabled={isSaving}
            />
          ))}
        </ul>
      </CardContent>
      <CardFooter
        className="sticky bottom-0 bg-background border-t flex items-center justify-between gap-4"
        data-testid="review-footer"
      >
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isSaving}
          aria-label="Discard review and return to upload"
        >
          Discard
        </Button>
        <Button
          type="button"
          variant="default"
          onClick={handleSave}
          disabled={isSaving || checkedTotal === 0}
          aria-label="Save profile changes"
          data-testid="save-button"
        >
          {isSaving
            ? 'Saving…'
            : `Save profile (${checkedTotal} skill${checkedTotal === 1 ? '' : 's'})`}
        </Button>
      </CardFooter>
    </Card>
  )
}
