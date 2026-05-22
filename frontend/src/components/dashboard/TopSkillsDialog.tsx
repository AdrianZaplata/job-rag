import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

import type { TopSkillItem } from '@/api/jobs'

export function TopSkillsDialog({
  open,
  onOpenChange,
  skills,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  skills: TopSkillItem[]
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>All top skills</DialogTitle>
          <DialogDescription>
            Full ranked list of hard skills across the filtered postings.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[70vh] overflow-y-auto" role="region" aria-label="Skill list">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-2 py-2 font-medium">#</th>
                <th className="px-2 py-2 font-medium">Skill</th>
                <th className="px-2 py-2 font-medium text-right">Must</th>
                <th className="px-2 py-2 font-medium text-right">Nice</th>
                <th className="px-2 py-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {skills.map((s, i) => (
                <tr key={s.skill} className="border-b last:border-b-0">
                  <td className="px-2 py-1.5 tabular-nums text-muted-foreground">{i + 1}</td>
                  <td className="px-2 py-1.5 font-mono text-xs">{s.skill}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{s.must_count}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{s.nice_count}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums font-medium">{s.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
