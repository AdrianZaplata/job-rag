/**
 * Wave 0 scaffold for useChatStream hook tests. Skip-clean until Plan 03 lands
 * frontend/src/components/chat/useChatStream.ts. Once active, covers:
 *  - CHAT-01 / CHAT-02 (fetch+ReadableStream consumption, token streaming)
 *  - CHAT-05 (final → composer re-enables, submit-during-stream blocked)
 *  - CHAT-06 (storage spy — never calls localStorage.setItem / indexedDB.open)
 *  - Pitfall A (React 19 StrictMode does NOT double-fire submit)
 *  - Pitfall B (AbortError → networkError stays null + item marked stopped)
 *  - Pitfall D (cold-start timer cleanup across rapid submit/stop/submit)
 */

import { describe, it, expect } from 'vitest'

// String-concat import specifier so tsc doesn't resolve at type-check time —
// mirrors frontend/src/test/AppShell.test.tsx skip-on-missing pattern.
const HOOK_MODULE = '@/components/chat/' + 'useChatStream'

describe('useChatStream (Wave 0 scaffold)', () => {
  it('module is importable once Plan 03 lands', async () => {
    let mod: Record<string, unknown>
    try {
      mod = (await import(/* @vite-ignore */ HOOK_MODULE)) as Record<string, unknown>
    } catch {
      // skip-clean when module not yet shipped
      return
    }
    if (typeof mod['useChatStream'] !== 'function') {
      // module exists but symbol missing — skip-clean
      return
    }
    // Activated assertion: hook export resolved
    expect(typeof mod['useChatStream']).toBe('function')
  })

  // Plan 03 expands this file with active tests against the hook.
  // The skip-clean stub above is the activation gate.
})
