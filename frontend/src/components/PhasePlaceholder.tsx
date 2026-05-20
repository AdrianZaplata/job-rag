import { BarChart3, MessageSquare, User } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'

/**
 * UI-SPEC §10 instantiations — typed "coming soon" stub for Phase 5/6/7 surfaces.
 * The `phase` prop is part of the contract for future per-phase customization but
 * is unused in render today.
 */
type PhasePlaceholderProps = {
  phase: 5 | 6 | 7
  feature: 'Dashboard' | 'Chat' | 'Profile'
}

const COPY: Record<
  PhasePlaceholderProps['feature'],
  { heading: string; body: string; icon: LucideIcon }
> = {
  Dashboard: {
    heading: 'Dashboard coming soon',
    body: 'The dashboard widgets land in Phase 5. Check the roadmap for progress.',
    icon: BarChart3,
  },
  Chat: {
    heading: 'Chat coming soon',
    body: 'The streaming chat surface lands in Phase 6. Check the roadmap for progress.',
    icon: MessageSquare,
  },
  Profile: {
    heading: 'Profile coming soon',
    body: 'Resume upload and profile editing land in Phase 7. Check the roadmap for progress.',
    icon: User,
  },
}

export function PhasePlaceholder({ feature }: PhasePlaceholderProps) {
  // `phase` is part of the typed contract for future per-phase customization;
  // unused in render today (UI-SPEC §10 copy is feature-keyed, not phase-keyed).
  const copy = COPY[feature]
  return <EmptyState icon={copy.icon} heading={copy.heading} body={copy.body} />
}
