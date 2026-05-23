/**
 * Phase 6 Plan 04 — activated tests for ToolChip presentation component.
 * Coverage: CHAT-03 (collapsed render), CHAT-04 (output truncation + Show full Dialog).
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { ToolChip } from '@/components/chat/ToolChip'
import type { TranscriptItem } from '@/components/chat/types'

type ToolCallItem = Extract<TranscriptItem, { kind: 'tool-call' }>

function makeItem(overrides: Partial<ToolCallItem> = {}): ToolCallItem {
  return {
    kind: 'tool-call',
    id: 'tool-1',
    name: 'search_jobs',
    args: { query: 'Azure senior Berlin' },
    output: null,
    expanded: false,
    ...overrides,
  }
}

describe('ToolChip — CHAT-03 collapsed render', () => {
  it('renders tool name + JSON args preview when collapsed', () => {
    render(<ToolChip item={makeItem()} onToggleExpand={vi.fn()} />)
    expect(screen.getByText('search_jobs')).toBeInTheDocument()
    expect(
      screen.getByText('{"query":"Azure senior Berlin"}', { exact: false }),
    ).toBeInTheDocument()
  })

  it('marks aria-expanded=false on the trigger when collapsed', () => {
    render(<ToolChip item={makeItem()} onToggleExpand={vi.fn()} />)
    const trigger = screen.getByRole('button', { name: /search_jobs/i })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('renders pulsing dot (running state) when output === null', () => {
    const { container } = render(
      <ToolChip item={makeItem({ output: null })} onToggleExpand={vi.fn()} />,
    )
    // The running pulse is a span with animate-pulse + content '·'
    expect(container.querySelector('.animate-pulse')).not.toBeNull()
  })

  it('disables CollapsibleTrigger while running (cannot expand without output)', () => {
    render(<ToolChip item={makeItem({ output: null })} onToggleExpand={vi.fn()} />)
    const trigger = screen.getByRole('button', { name: /search_jobs/i })
    expect(trigger).toBeDisabled()
  })
})

describe('ToolChip — CHAT-04 output truncation + Show full Dialog', () => {
  it('truncates output > 200 chars with "…" and shows "Show full output" button when expanded', () => {
    const longOutput = 'x'.repeat(300)
    render(
      <ToolChip
        item={makeItem({ output: longOutput, expanded: true })}
        onToggleExpand={vi.fn()}
      />,
    )
    // Truncated preview: 200 x's + ellipsis
    const truncated = 'x'.repeat(200) + '…'
    expect(screen.getByText(truncated, { exact: false })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Show full output' }),
    ).toBeInTheDocument()
  })

  it('does NOT show "Show full output" when output <= 200 chars', () => {
    render(
      <ToolChip
        item={makeItem({ output: 'short result', expanded: true })}
        onToggleExpand={vi.fn()}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Show full output' }),
    ).not.toBeInTheDocument()
  })

  it('opens Dialog on "Show full output" click with full output text', async () => {
    const longOutput = 'x'.repeat(300) + ' END'
    render(
      <ToolChip
        item={makeItem({ output: longOutput, expanded: true })}
        onToggleExpand={vi.fn()}
      />,
    )
    const showFullBtn = screen.getByRole('button', { name: 'Show full output' })
    fireEvent.click(showFullBtn)
    // Dialog title is "Tool output"
    expect(await screen.findByText('Tool output')).toBeInTheDocument()
    // Full output (including " END" suffix beyond 200 chars) renders inside dialog
    expect(
      screen.getByText((content) => content.includes('END')),
    ).toBeInTheDocument()
  })
})

describe('ToolChip — expand/collapse interaction', () => {
  it('calls onToggleExpand(item.id) when header is clicked', () => {
    const onToggle = vi.fn()
    render(
      <ToolChip
        item={makeItem({ output: 'done', expanded: false })}
        onToggleExpand={onToggle}
      />,
    )
    const trigger = screen.getByRole('button', { name: /search_jobs/i })
    fireEvent.click(trigger)
    expect(onToggle).toHaveBeenCalledWith('tool-1')
  })
})
