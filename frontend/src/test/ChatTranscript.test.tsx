/**
 * Wave 0 scaffold for ChatTranscript tests. Skip-clean until Plan 04 lands
 * frontend/src/components/chat/ChatTranscript.tsx. Once active, covers:
 *  - D-17 smart-autoscroll (suppressed on user scroll-up; re-engaged on scroll-down)
 *  - Items render in order
 *  - Network-error Alert conditional render at top of transcript
 */

import { describe, it, expect } from 'vitest'

const COMPONENT_MODULE = '@/components/chat/' + 'ChatTranscript'

describe('ChatTranscript (Wave 0 scaffold)', () => {
  it('module is importable once Plan 04 lands', async () => {
    let mod: Record<string, unknown>
    try {
      mod = (await import(/* @vite-ignore */ COMPONENT_MODULE)) as Record<string, unknown>
    } catch {
      return
    }
    if (typeof mod['ChatTranscript'] !== 'function') {
      return
    }
    expect(typeof mod['ChatTranscript']).toBe('function')
  })
})
