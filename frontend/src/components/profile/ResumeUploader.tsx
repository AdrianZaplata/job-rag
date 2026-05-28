// Phase 7 Plan 05 — resume upload affordance per CONTEXT.md D-30 / D-31 / D-35.
// PATTERNS §18 / UI-SPEC §6c analog.
//
// Native <input type="file"> + drag-drop listeners on wrapper div (D-30 verbatim:
// NO react-dropzone). Client-side pre-checks file.size <= 2 MB and extension
// ∈ {.pdf, .docx} BEFORE POST (T-07-02 / T-07-05 mitigation; backend is the
// authoritative backstop).
//
// During upload: stepped status copy per D-31 (0-2s / 2-10s / 10s+) computed
// via setTimeout (analog: useChatStream cold-start timer).
//
// On error: COPY object maps the backend's {reason} HTTPException detail to
// {title, body} per D-35.

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, FileText, Upload, X } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

const MAX_BYTES = 2_000_000
const ALLOWED_EXTS = ['.pdf', '.docx'] as const
const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
] as const

// WR-02: Tailwind only emits classes it sees as full literal tokens at
// scan time (`w-${w}` is invisible to the scanner). Use a static lookup
// so all eight skeleton-bar widths survive the v4 build. Picked from
// classes Tailwind always emits (w-16 / w-20 / w-24 / w-28 are core).
const SKELETON_WIDTHS = [
  'w-20',
  'w-24',
  'w-16',
  'w-28',
  'w-20',
  'w-24',
  'w-16',
  'w-24',
] as const

// D-35 verbatim error copy mapping.
const COPY: Record<string, { title: string; body: string }> = {
  file_too_large: {
    title: 'File too large',
    body: 'Resume must be ≤2 MB.',
  },
  unsupported_file_type: {
    title: 'Unsupported format',
    body: 'Upload a PDF or DOCX.',
  },
  pdf_encrypted: {
    title: 'Encrypted PDF',
    body: 'Remove the password and try again.',
  },
  text_extraction_failed: {
    title: 'Could not read the file',
    body: 'The file appears to be a scanned image. v1 does not support OCR.',
  },
  extraction_failed: {
    title: 'Extraction failed',
    body: 'The agent could not parse the resume. Try again or simplify the formatting.',
  },
  empty_skills: {
    title: 'No skills found',
    body: 'The extracted skill list is empty. Is this a resume?',
  },
  llm_unavailable: {
    title: 'Service unavailable',
    body: 'The LLM is down. Please try again in a few minutes.',
  },
}

export type ResumeUploaderProps = {
  onUpload: (file: File) => void
  isPending: boolean
  isError: boolean
  error?: Error | null
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function validateFile(file: File): { reason: string } | null {
  if (file.size > MAX_BYTES) return { reason: 'file_too_large' }
  const name = file.name.toLowerCase()
  const extOk = ALLOWED_EXTS.some((ext) => name.endsWith(ext))
  const typeOk = (ALLOWED_TYPES as readonly string[]).includes(file.type)
  // Allow if EITHER extension OR MIME matches (some browsers don't set type for DOCX).
  if (!extOk && !typeOk) return { reason: 'unsupported_file_type' }
  return null
}

function describeError(err: Error | null | undefined): {
  title: string
  body: string
} {
  if (!err) return { title: 'Upload failed', body: 'Unknown error.' }
  const reason = err.message
  const mapped = COPY[reason]
  if (mapped) return mapped
  return { title: 'Upload failed', body: err.message }
}

export function ResumeUploader({
  onUpload,
  isPending,
  isError,
  error,
}: ResumeUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [clientError, setClientError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [statusCopy, setStatusCopy] = useState<string>(
    'Reading your resume…',
  )

  // D-31 stepped status copy: 0-2s / 2-10s / 10s+ timers, cleared when isPending falls.
  useEffect(() => {
    if (!isPending) {
      setStatusCopy('Reading your resume…')
      return
    }
    setStatusCopy('Reading your resume…')
    const t1 = setTimeout(
      () => setStatusCopy('Asking the agent to extract skills…'),
      2_000,
    )
    const t2 = setTimeout(
      () =>
        setStatusCopy(
          'Still working — extraction can take a minute on first load…',
        ),
      10_000,
    )
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [isPending])

  const handleCandidate = useCallback((candidate: File) => {
    const v = validateFile(candidate)
    if (v) {
      setClientError(v.reason)
      setFile(null)
      return
    }
    setClientError(null)
    setFile(candidate)
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleCandidate(f)
    // reset so re-picking same file fires onChange again
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleCandidate(f)
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => setDragOver(false)

  const handleRemove = () => {
    setFile(null)
    setClientError(null)
  }

  const handleUploadClick = () => {
    if (file && !isPending) onUpload(file)
  }

  // Compose the displayed error: client-side validation takes precedence over
  // server-side error (the user must clear their client mistake first).
  const errorDetail = clientError
    ? COPY[clientError] ?? {
        title: 'Upload failed',
        body: clientError,
      }
    : isError
      ? describeError(error)
      : null

  return (
    <Card data-testid="resume-uploader">
      <CardHeader>
        <CardTitle className="text-sm font-medium">Upload resume</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          data-testid="resume-dropzone"
          data-dragover={dragOver ? 'true' : 'false'}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => !isPending && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Resume upload drop zone — drop a file or activate to open the file picker"
          aria-disabled={isPending}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              if (!isPending) fileInputRef.current?.click()
            }
          }}
          className={[
            'flex w-full flex-col items-center justify-center gap-2',
            'rounded-md border-2 border-dashed p-8 md:p-12 text-center',
            'transition-colors cursor-pointer',
            'border-border bg-card',
            'hover:border-ring hover:bg-muted',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            'data-[dragover=true]:border-ring data-[dragover=true]:bg-muted',
            isPending ? 'opacity-50 pointer-events-none' : '',
          ].join(' ')}
        >
          <Upload
            className="h-12 w-12 text-muted-foreground"
            aria-hidden="true"
          />
          <p className="text-sm">Drop your PDF or DOCX here</p>
          <p className="text-xs text-muted-foreground">
            or click to choose a file
          </p>
          <p className="text-xs text-muted-foreground">
            PDF or DOCX · max 2 MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            onChange={handleInputChange}
            aria-label="Choose resume file"
          />
        </div>

        {file && !isPending && (
          <div
            className="flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-2"
            data-testid="selected-file"
          >
            <FileText
              className="h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <span className="text-sm font-medium truncate flex-1">
              {file.name} · {formatBytes(file.size)}
            </span>
            <div className="flex shrink-0 gap-2 ml-auto">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleRemove}
                aria-label="Remove selected file"
              >
                <X className="h-4 w-4" aria-hidden="true" />
                Remove
              </Button>
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={handleUploadClick}
                aria-label="Upload resume"
              >
                <Upload className="h-4 w-4 mr-1" aria-hidden="true" />
                Upload
              </Button>
            </div>
          </div>
        )}

        {isPending && (
          <div className="space-y-4">
            <p
              className="text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
              data-testid="upload-status"
            >
              {statusCopy}
            </p>
            <div className="flex flex-wrap gap-2" aria-hidden="true">
              {SKELETON_WIDTHS.map((cls, i) => (
                <Skeleton key={i} className={`h-6 ${cls}`} />
              ))}
            </div>
          </div>
        )}

        {errorDetail && !isPending && (
          <Alert variant="destructive" data-testid="upload-error">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>{errorDetail.title}</AlertTitle>
            <AlertDescription>{errorDetail.body}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
