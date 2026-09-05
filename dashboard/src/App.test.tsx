import { fireEvent, render, screen } from '@testing-library/react'
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

  it('reveals contextual inputs only when full mode is selected', async () => {
    render(
      <MemoryRouter initialEntries={['/audits/new']}>
        <App />
      </MemoryRouter>,
    )
    const auditDepth = await screen.findByLabelText(/Audit depth/i)
    expect(screen.queryByPlaceholderText(/What question was the AI asked/i)).not.toBeInTheDocument()
    fireEvent.change(auditDepth, { target: { value: 'full' } })
    expect(screen.getByPlaceholderText(/What question was the AI asked/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Duration, territory/i)).toBeInTheDocument()
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

  it('shows the assessed input and links prompts to their claim or context source', async () => {
    vi.spyOn(auditRepository, 'getAudit').mockResolvedValue({
      ...savedDemoResult,
      audit_mode: 'full',
      original_question: 'Can the employer enforce this worldwide restraint?',
      facts: 'The employee was a senior salesperson with customer access.',
      flags: [
        {
          code: 'wrong_pinpoint',
          module: 'citation_integrity',
          severity: 'serious',
          message: 'The supplied pinpoint is missing or does not support the mapped proposition.',
          claim_order: 1,
          lawyer_review_required: true,
        },
        {
          code: 'potential_omission',
          module: 'balance_completeness',
          severity: 'review',
          message: 'The issue checklist expects consideration of public interest.',
          claim_order: null,
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
    expect(screen.getByRole('link', { name: /Derived from the submitted question/i })).toHaveAttribute('href', '#submitted-input')
  })
})
