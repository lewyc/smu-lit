import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import App from './App'
import { DEMO_ANSWER, savedDemoResult } from './lib/demo'
import { auditRepository } from './lib/repository'
import { AuditDetailPage } from './pages/AuditDetailPage'

vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
})

afterEach(() => vi.restoreAllMocks())

describe('ProofMark dashboard', () => {
  it('keeps the pilot limitations visible on the assurance route', async () => {
    render(
      <MemoryRouter initialEntries={['/assurance']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Help lawyers triage/i)).toBeInTheDocument()
    expect(screen.getByText(/Pilot evaluation tool/i)).toBeInTheDocument()
    expect(screen.getByText(/Production architecture/i)).toBeInTheDocument()
  })

  it('loads the new audit form in demo mode without Supabase credentials', async () => {
    render(
      <MemoryRouter initialEntries={['/audits/new']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('textbox', { name: /AI-generated legal answer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Load demonstration answer/i })).toBeInTheDocument()
  })

  it('keeps the new-audit form citation-only during the Tier 0 release', async () => {
    render(
      <MemoryRouter initialEntries={['/audits/new']}>
        <App />
      </MemoryRouter>,
    )
    expect(screen.queryByPlaceholderText(/What question was the AI asked/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Audit depth/i)).not.toBeInTheDocument()
    expect(screen.getByText(/does not assess factual fit, legal significance or omissions/i)).toBeInTheDocument()
  })

  it('exposes the Case Map human-review workbench', async () => {
    vi.spyOn(auditRepository, 'listCaseMapSources').mockResolvedValue([])
    vi.spyOn(auditRepository, 'listCaseMaps').mockResolvedValue([])
    vi.spyOn(auditRepository, 'listFeedback').mockResolvedValue([])
    render(
      <MemoryRouter initialEntries={['/case-maps']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Case Map workbench/i)).toBeInTheDocument()
    expect(screen.getByText(/Generate anchored draft/i)).toBeInTheDocument()
    expect(screen.getByText(/Practitioner feedback/i)).toBeInTheDocument()
    expect(await screen.findByText(/0 maps/i)).toBeInTheDocument()
  })

  it('shows Tier 0 prompts and hides deferred completeness prompts', async () => {
    vi.spyOn(auditRepository, 'getAudit').mockResolvedValue({
      ...savedDemoResult,
      audit_mode: 'citation_only',
      flags: [
        {
          code: 'wrong_pinpoint',
          module: 'citation_integrity',
          severity: 'serious',
          message: 'The supplied pinpoint is missing or does not support the mapped proposition.',
          claim_order: 1,
          lawyer_review_required: true,
        },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/audits/fixture-audit']}>
        <Routes>
          <Route path="/audits/:id" element={<AuditDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Material assessed in this audit/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/AI answer submitted for evaluation/i)).toHaveTextContent(DEMO_ANSWER.split('\n')[0])
    expect(screen.getByRole('link', { name: /Refers to claim 01/i })).toHaveAttribute('href', '#claim-1')
    expect(screen.queryByText(/issue checklist expects consideration/i)).not.toBeInTheDocument()
  })
})
