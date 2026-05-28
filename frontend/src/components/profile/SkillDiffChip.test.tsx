// Phase 7 Plan 05 — SkillDiffChip tests per VALIDATION 07-05-07.
//
// Covers:
//   - status pill colour + label per source (D-24 verbatim)
//   - Pencil affordance present ONLY on source==='added' (D-26)
//   - inline edit: Enter saves, Esc cancels (D-26)
//   - checkbox click toggles via onToggle callback

import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { SkillDiffChip } from './SkillDiffChip'
import type { DiffItemState } from './types'

function diffItem(over: Partial<DiffItemState>): DiffItemState {
  const merged = {
    name: 'Python',
    source: 'unchanged' as DiffItemState['source'],
    editable: false,
    checked: true,
    ...over,
  }
  // Default editedName tracks the resolved name unless caller overrode it.
  return {
    ...merged,
    editedName: over.editedName ?? merged.name,
  }
}

describe('SkillDiffChip', () => {
  it('renders green + ADDED pill + Pencil affordance for source=added', () => {
    render(
      <SkillDiffChip
        item={diffItem({ name: 'Rust', source: 'added', editable: true })}
        onToggle={vi.fn()}
        onRename={vi.fn()}
      />,
    )
    const pill = screen.getByTestId('pill-added')
    expect(pill).toHaveTextContent('+ ADDED')
    expect(pill.className).toContain('bg-green-500/10')
    expect(pill.className).toContain('text-green-700')
    expect(screen.getByTestId('pencil-Rust')).toBeInTheDocument()
  })

  it('renders red − REMOVED pill, NO Pencil affordance for source=removed', () => {
    render(
      <SkillDiffChip
        item={diffItem({ name: 'jquery', source: 'removed' })}
        onToggle={vi.fn()}
        onRename={vi.fn()}
      />,
    )
    const pill = screen.getByTestId('pill-removed')
    expect(pill).toHaveTextContent('− REMOVED')
    expect(pill.className).toContain('bg-red-500/10')
    expect(pill.className).toContain('text-red-700')
    expect(screen.queryByTestId('pencil-jquery')).not.toBeInTheDocument()
  })

  it('renders muted = UNCHANGED pill, NO Pencil affordance for source=unchanged', () => {
    render(
      <SkillDiffChip
        item={diffItem({ name: 'docker', source: 'unchanged' })}
        onToggle={vi.fn()}
        onRename={vi.fn()}
      />,
    )
    const pill = screen.getByTestId('pill-unchanged')
    expect(pill).toHaveTextContent('= UNCHANGED')
    expect(pill.className).toContain('bg-muted')
    expect(screen.queryByTestId('pencil-docker')).not.toBeInTheDocument()
  })

  it('clicking the checkbox calls onToggle with the skill name', () => {
    const onToggle = vi.fn()
    render(
      <SkillDiffChip
        item={diffItem({ name: 'Rust', source: 'added', editable: true })}
        onToggle={onToggle}
        onRename={vi.fn()}
      />,
    )
    const cb = screen.getByLabelText(/Confirm skill Rust/i)
    fireEvent.click(cb)
    expect(onToggle).toHaveBeenCalledWith('Rust')
  })

  it('clicking Pencil enters edit mode with focused Input pre-filled with editedName', () => {
    render(
      <SkillDiffChip
        item={diffItem({ name: 'Rust', source: 'added', editable: true })}
        onToggle={vi.fn()}
        onRename={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId('pencil-Rust'))
    const input = screen.getByTestId('edit-input-Rust') as HTMLInputElement
    expect(input).toBeInTheDocument()
    expect(input.value).toBe('Rust')
    expect(document.activeElement).toBe(input)
  })

  it('Enter on Input commits a renamed value via onRename(originalName, newName)', () => {
    const onRename = vi.fn()
    render(
      <SkillDiffChip
        item={diffItem({ name: 'Rust', source: 'added', editable: true })}
        onToggle={vi.fn()}
        onRename={onRename}
      />,
    )
    fireEvent.click(screen.getByTestId('pencil-Rust'))
    const input = screen.getByTestId('edit-input-Rust') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'rustlang' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onRename).toHaveBeenCalledWith('Rust', 'rustlang')
    // After commit, input unmounts back to span
    expect(
      screen.queryByTestId('edit-input-Rust'),
    ).not.toBeInTheDocument()
  })

  it('Escape on Input cancels edit; onRename NOT called; static span returns', () => {
    const onRename = vi.fn()
    render(
      <SkillDiffChip
        item={diffItem({ name: 'Rust', source: 'added', editable: true })}
        onToggle={vi.fn()}
        onRename={onRename}
      />,
    )
    fireEvent.click(screen.getByTestId('pencil-Rust'))
    const input = screen.getByTestId('edit-input-Rust') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'rustlang' } })
    fireEvent.keyDown(input, { key: 'Escape' })

    expect(onRename).not.toHaveBeenCalled()
    expect(
      screen.queryByTestId('edit-input-Rust'),
    ).not.toBeInTheDocument()
  })
})
