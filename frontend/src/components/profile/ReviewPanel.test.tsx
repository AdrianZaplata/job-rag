// Phase 7 Plan 05 — ReviewPanel tests per VALIDATION 07-05-08.
//
// Covers:
//   - CardDescription summary "X skills found · Y new · Z removed · W unchanged"
//   - Sticky CardFooter (className contains "sticky bottom-0")
//   - Live Save label updates as user toggles chips
//   - Save click → onSave called with payload containing only checked items + extraction_id
//   - Discard click → onCancel called

import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { ReviewPanel } from './ReviewPanel'
import type { DiffItemState } from './types'

function seed(): DiffItemState[] {
  return [
    {
      name: 'Rust',
      source: 'added',
      editable: true,
      checked: true,
      editedName: 'Rust',
    },
    {
      name: 'azure',
      source: 'added',
      editable: true,
      checked: true,
      editedName: 'azure',
    },
    {
      name: 'jquery',
      source: 'removed',
      editable: false,
      checked: false,
      editedName: 'jquery',
    },
    {
      name: 'Python',
      source: 'unchanged',
      editable: false,
      checked: true,
      editedName: 'Python',
    },
    {
      name: 'docker',
      source: 'unchanged',
      editable: false,
      checked: true,
      editedName: 'docker',
    },
  ]
}

describe('ReviewPanel', () => {
  it('renders the diff summary in CardDescription with correct counts', () => {
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    expect(
      screen.getByText(/5 skills found · 2 new · 1 removed · 2 unchanged/),
    ).toBeInTheDocument()
  })

  it('CardFooter has sticky positioning class', () => {
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    const footer = screen.getByTestId('review-footer')
    expect(footer.className).toContain('sticky')
    expect(footer.className).toContain('bottom-0')
  })

  it('Save button label updates live when an "added" chip is unticked', () => {
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    // Seed default checked total = 2 (added) + 0 (removed) + 2 (unchanged) = 4
    expect(screen.getByTestId('save-button')).toHaveTextContent(
      'Save profile (4 skills)',
    )
    // Untick "Rust" (added → checked currently)
    fireEvent.click(screen.getByLabelText(/Confirm skill Rust/i))
    expect(screen.getByTestId('save-button')).toHaveTextContent(
      'Save profile (3 skills)',
    )
  })

  it('Save click sends UserProfileUpdate with only checked items + extraction_id', () => {
    const onSave = vi.fn()
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="00000000-0000-0000-0000-000000000abc"
        onSave={onSave}
        onCancel={vi.fn()}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId('save-button'))
    expect(onSave).toHaveBeenCalledTimes(1)
    const payload = onSave.mock.calls[0][0]
    expect(payload).toEqual({
      skills: [
        { name: 'Rust' },
        { name: 'azure' },
        { name: 'Python' },
        { name: 'docker' },
      ],
      target_roles: null,
      preferred_locations: null,
      min_salary_eur: null,
      remote_preference: null,
      extraction_id: '00000000-0000-0000-0000-000000000abc',
    })
  })

  it('Discard click fires onCancel', () => {
    const onCancel = vi.fn()
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={onCancel}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Discard/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('Save button is disabled when all chips unticked', () => {
    const diff = seed().map((d) => ({ ...d, checked: false }))
    render(
      <ReviewPanel
        diff={diff}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        isSaving={false}
        setDiff={vi.fn()}
      />,
    )
    expect(screen.getByTestId('save-button')).toBeDisabled()
  })

  it('Save button shows Saving… and is disabled while isSaving=true', () => {
    render(
      <ReviewPanel
        diff={seed()}
        extractionId="abc"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        isSaving
        setDiff={vi.fn()}
      />,
    )
    const btn = screen.getByTestId('save-button')
    expect(btn).toBeDisabled()
    expect(btn).toHaveTextContent('Saving…')
  })
})
