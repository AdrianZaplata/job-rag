import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { BootErrorFallback } from '@/components/BootErrorFallback'

describe('BootErrorFallback', () => {
  let originalReload: () => void

  beforeEach(() => {
    originalReload = window.location.reload
    // jsdom's window.location.reload is non-configurable by default — replace via Object.defineProperty
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, reload: vi.fn() },
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, reload: originalReload },
    })
  })

  it('renders the headline and the error message in a <pre> block', () => {
    const error = new Error('boot failed: AADSTS500011')
    render(<BootErrorFallback error={error} />)

    expect(
      screen.getByRole('heading', { name: /we hit a problem starting the app/i }),
    ).toBeInTheDocument()
    // Stack (or message fallback) is rendered in a <pre>
    const pre = document.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre!.textContent).toContain('boot failed: AADSTS500011')
  })

  it('falls back to String(error) when error is not an Error instance', () => {
    render(<BootErrorFallback error="raw string failure" />)
    const pre = document.querySelector('pre')
    expect(pre!.textContent).toContain('raw string failure')
  })

  it('truncates long error stacks to 1000 characters', () => {
    const longStack = 'x'.repeat(5000)
    const error = new Error('long')
    error.stack = longStack
    render(<BootErrorFallback error={error} />)
    const pre = document.querySelector('pre')
    expect(pre!.textContent!.length).toBeLessThanOrEqual(1000)
  })

  it('has a Reload page button that calls window.location.reload', async () => {
    const user = userEvent.setup()
    render(<BootErrorFallback error={new Error('any')} />)
    const button = screen.getByRole('button', { name: /reload page/i })
    await user.click(button)
    expect(window.location.reload).toHaveBeenCalledTimes(1)
  })

  it('uses role="alert" on the outer container for a11y', () => {
    render(<BootErrorFallback error={new Error('any')} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
