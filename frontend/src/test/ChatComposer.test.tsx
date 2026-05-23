/**
 * Phase 6 Plan 04 — activated tests for ChatComposer presentation component.
 * Coverage: CHAT-05 (UI half) — Enter submits, Shift+Enter newline, Stop click,
 *           disabled-while-streaming, Send/Stop conditional render.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { ChatComposer } from '@/components/chat/ChatComposer'

function setup(overrides: Partial<React.ComponentProps<typeof ChatComposer>> = {}) {
  const props = {
    value: '',
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onStop: vi.fn(),
    isStreaming: false,
    ...overrides,
  }
  const result = render(<ChatComposer {...props} />)
  return { ...props, ...result }
}

describe('ChatComposer — Send/Stop conditional render', () => {
  it('renders Send button when isStreaming === false', () => {
    setup({ value: 'hi', isStreaming: false })
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Stop streaming response' }),
    ).not.toBeInTheDocument()
  })

  it('renders Stop button when isStreaming === true', () => {
    setup({ isStreaming: true })
    expect(
      screen.getByRole('button', { name: 'Stop streaming response' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Send message' }),
    ).not.toBeInTheDocument()
  })
})

describe('ChatComposer — Enter / Shift+Enter keymap (D-15)', () => {
  it('Enter (no shift) submits when value non-empty and not streaming', () => {
    const onSubmit = vi.fn()
    setup({ value: 'test', onSubmit })
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('Shift+Enter does NOT submit (newline default behavior)', () => {
    const onSubmit = vi.fn()
    setup({ value: 'test', onSubmit })
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('Enter does NOT submit when value is empty', () => {
    const onSubmit = vi.fn()
    setup({ value: '', onSubmit })
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('Enter does NOT submit when isStreaming === true', () => {
    const onSubmit = vi.fn()
    setup({ value: 'test', isStreaming: true, onSubmit })
    // Textarea is disabled; jsdom still fires onKeyDown on disabled but handler guards.
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('ChatComposer — Stop click aborts', () => {
  it('clicking Stop calls onStop', () => {
    const onStop = vi.fn()
    setup({ isStreaming: true, onStop })
    const stopBtn = screen.getByRole('button', { name: 'Stop streaming response' })
    fireEvent.click(stopBtn)
    expect(onStop).toHaveBeenCalledTimes(1)
  })
})

describe('ChatComposer — disabled-while-streaming', () => {
  it('Textarea is disabled when isStreaming === true', () => {
    setup({ isStreaming: true })
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    expect(textarea).toBeDisabled()
  })

  it('Textarea is disabled when disabled prop === true (network-error state)', () => {
    setup({ disabled: true })
    const textarea = screen.getByRole('textbox', { name: 'Ask the agent' })
    expect(textarea).toBeDisabled()
  })
})

describe('ChatComposer — Send button disabled state', () => {
  it('Send disabled when value is empty', () => {
    setup({ value: '' })
    const send = screen.getByRole('button', { name: 'Send message' })
    expect(send).toBeDisabled()
  })

  it('Send enabled when value non-empty', () => {
    setup({ value: 'hi' })
    const send = screen.getByRole('button', { name: 'Send message' })
    expect(send).not.toBeDisabled()
  })
})
