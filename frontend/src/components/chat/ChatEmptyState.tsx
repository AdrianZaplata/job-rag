/**
 * Phase 6 Plan 04 — ChatEmptyState presentation component (UI-SPEC §6e verbatim).
 *
 * Renders before any user submits, when items.length === 0 AND !isStreaming.
 * Per D-25, chip click pre-fills the composer textarea + focuses it — does NOT
 * auto-submit (lets user edit before sending; avoids accidental sends).
 *
 * The 4 sample queries are demo-tuned per UI-SPEC §6e to produce visibly
 * different agent tool-call patterns (skills lookup / aggregation / match /
 * salary filter), showcasing the streaming + tool chip UX on first run.
 */

import { MessageSquare } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

export type ChatEmptyStateProps = {
  onSampleClick: (query: string) => void
}

const SAMPLE_QUERIES = [
  "What's the top must-have skill in Berlin?",
  'Compare AWS vs Azure demand across senior roles.',
  'How does my CV match staff-level positions?',
  'Which postings pay above €100k?',
] as const

export function ChatEmptyState({ onSampleClick }: ChatEmptyStateProps) {
  return (
    <Card className="max-w-md mx-auto mt-24 p-8 text-center">
      <CardContent className="space-y-4">
        <MessageSquare
          className="h-12 w-12 text-muted-foreground mx-auto mb-4"
          aria-hidden="true"
        />
        <h2 className="text-2xl font-semibold">
          Ask the agent about the job-market corpus
        </h2>
        <p className="text-sm text-muted-foreground">
          108 curated AI-Engineer postings from Berlin, Germany, EU, and remote.
          Try one of these:
        </p>
        <div className="flex flex-wrap gap-2 justify-center pt-4">
          {SAMPLE_QUERIES.map((query) => (
            <Badge
              key={query}
              variant="outline"
              className="cursor-pointer hover:bg-muted transition-colors text-xs whitespace-normal text-left h-auto py-1 px-2"
              role="button"
              tabIndex={0}
              onClick={() => onSampleClick(query)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSampleClick(query)
                }
              }}
            >
              {query}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
