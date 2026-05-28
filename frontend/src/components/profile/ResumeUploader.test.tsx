// Phase 7 Plan 05 — ResumeUploader tests per VALIDATION 07-05-06.
//
// Covers:
//   - file input accept attribute includes .pdf,.docx
//   - client-side pre-check rejects oversize PDFs (> 2 MB)
//   - client-side pre-check rejects unsupported extensions (.txt)
//   - valid file enables Upload button → calls onUpload(file)
//   - stepped status copy transitions 0-2s → 2-10s → 10s+ during isPending

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, act } from '@testing-library/react'

import { ResumeUploader } from './ResumeUploader'

describe('ResumeUploader', () => {
  it('file input accept attribute includes .pdf and .docx', () => {
    render(
      <ResumeUploader
        onUpload={vi.fn()}
        isPending={false}
        isError={false}
        error={null}
      />,
    )
    const input = screen.getByLabelText(
      'Choose resume file',
    ) as HTMLInputElement
    expect(input.accept).toContain('.pdf')
    expect(input.accept).toContain('.docx')
  })

  it('rejects a .txt file via client-side pre-check (does NOT call onUpload)', () => {
    const onUpload = vi.fn()
    render(
      <ResumeUploader
        onUpload={onUpload}
        isPending={false}
        isError={false}
        error={null}
      />,
    )
    const input = screen.getByLabelText(
      'Choose resume file',
    ) as HTMLInputElement
    const txt = new File(['hello'], 'note.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [txt] } })

    // Inline destructive alert appears
    expect(screen.getByText('Unsupported format')).toBeInTheDocument()
    expect(screen.getByText('Upload a PDF or DOCX.')).toBeInTheDocument()
    // No file pill, no Upload button click
    expect(screen.queryByTestId('selected-file')).not.toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('rejects an oversize (>2 MB) PDF via client-side pre-check', () => {
    const onUpload = vi.fn()
    render(
      <ResumeUploader
        onUpload={onUpload}
        isPending={false}
        isError={false}
        error={null}
      />,
    )
    const input = screen.getByLabelText(
      'Choose resume file',
    ) as HTMLInputElement
    // 3 MB PDF
    const bigBytes = new Uint8Array(3_000_000)
    const bigPdf = new File([bigBytes], 'huge.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(input, { target: { files: [bigPdf] } })

    expect(screen.getByText('File too large')).toBeInTheDocument()
    expect(screen.getByText('Resume must be ≤2 MB.')).toBeInTheDocument()
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('accepts a valid <2 MB PDF and calls onUpload when Upload clicked', () => {
    const onUpload = vi.fn()
    render(
      <ResumeUploader
        onUpload={onUpload}
        isPending={false}
        isError={false}
        error={null}
      />,
    )
    const input = screen.getByLabelText(
      'Choose resume file',
    ) as HTMLInputElement
    const pdf = new File([new Uint8Array(102_400)], 'resume_2026.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(input, { target: { files: [pdf] } })

    // Selected file pill shows.
    expect(screen.getByTestId('selected-file')).toBeInTheDocument()
    expect(screen.getByText(/resume_2026\.pdf/)).toBeInTheDocument()

    // Click the explicit "Upload" button to submit.
    fireEvent.click(screen.getByRole('button', { name: 'Upload resume' }))
    expect(onUpload).toHaveBeenCalledTimes(1)
    expect(onUpload).toHaveBeenCalledWith(pdf)
  })

  describe('stepped status copy during upload (D-31)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('cycles Reading… → Asking… → Still working… as time elapses', () => {
      render(
        <ResumeUploader
          onUpload={vi.fn()}
          isPending
          isError={false}
          error={null}
        />,
      )
      // 0-2s
      expect(
        screen.getByTestId('upload-status').textContent,
      ).toMatch(/Reading your resume/)

      // Advance to 2s+
      act(() => {
        vi.advanceTimersByTime(2_001)
      })
      expect(
        screen.getByTestId('upload-status').textContent,
      ).toMatch(/Asking the agent to extract skills/)

      // Advance to 10s+
      act(() => {
        vi.advanceTimersByTime(10_000)
      })
      expect(
        screen.getByTestId('upload-status').textContent,
      ).toMatch(/Still working/)
    })
  })

  it('shows server error via D-35 COPY mapping when isError=true', () => {
    render(
      <ResumeUploader
        onUpload={vi.fn()}
        isPending={false}
        isError
        error={new Error('pdf_encrypted')}
      />,
    )
    expect(screen.getByText('Encrypted PDF')).toBeInTheDocument()
    expect(
      screen.getByText('Remove the password and try again.'),
    ).toBeInTheDocument()
  })

  it('drop event with a valid PDF stages the file for upload', () => {
    const onUpload = vi.fn()
    render(
      <ResumeUploader
        onUpload={onUpload}
        isPending={false}
        isError={false}
        error={null}
      />,
    )
    const zone = screen.getByTestId('resume-dropzone')
    const pdf = new File([new Uint8Array(1024)], 'dropped.pdf', {
      type: 'application/pdf',
    })
    fireEvent.drop(zone, {
      dataTransfer: { files: [pdf] },
    })
    expect(screen.getByText(/dropped\.pdf/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Upload resume' }))
    expect(onUpload).toHaveBeenCalledWith(pdf)
  })
})
