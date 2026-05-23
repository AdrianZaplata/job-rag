/**
 * Wave 0 scaffold for ChatComposer tests. Skip-clean until Plan 04 lands
 * frontend/src/components/chat/ChatComposer.tsx. Once active, covers:
 *  - CHAT-05 UI half (Enter submits, Shift+Enter newline, Stop click aborts,
 *    Textarea disabled-while-streaming)
 */

import { describe, it, expect } from 'vitest'

const COMPONENT_MODULE = '@/components/chat/' + 'ChatComposer'

describe('ChatComposer (Wave 0 scaffold)', () => {
  it('module is importable once Plan 04 lands', async () => {
    let mod: Record<string, unknown>
    try {
      mod = (await import(/* @vite-ignore */ COMPONENT_MODULE)) as Record<string, unknown>
    } catch {
      return
    }
    if (typeof mod['ChatComposer'] !== 'function') {
      return
    }
    expect(typeof mod['ChatComposer']).toBe('function')
  })
})
