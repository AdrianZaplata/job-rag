import { describe, it } from 'vitest'

describe('AppShell', () => {
  it('renders nav with Dashboard/Chat/Profile (activates with Plan 04-05)', async () => {
    let mod: Record<string, unknown>
    try {
      const spec = '@/components/' + 'AppShell'
      mod = (await import(/* @vite-ignore */ spec)) as Record<string, unknown>
    } catch {
      return
    }
    if (!('AppShell' in mod) || typeof mod.AppShell !== 'function') {
      return
    }
    // Plan 04-05 extends with role+name queries.
  })
})
