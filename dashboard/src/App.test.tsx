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

  it('shows source integrity and unmeasured operating points on the demo route', async () => {
    vi.spyOn(auditRepository, 'getVeritasConfig').mockResolvedValue({
      config_version: 'test-config',
      scope: 'Singapore employment restraint-of-trade assurance pilot',
      measurement_policy: {
        rule: 'Configured targets are not achieved figures.',
        performance_runs: 3,
        latency_targets_ms: { tier_0: null, tier_1: null, tier_2: null, tier_3: null },
        tier_2_sample_rate: null,
      },
      calibration: {
        confidence_band_boundaries: null,
        measured_accuracy_by_confidence_band: null,
        held_out_set_version: null,
        component_metrics: {},
        dashboard_figures_policy: 'Measured values only.',
        final_submission_figures_policy: 'Label every figure.',
      },
      assurance_policy: {
        policy_version: 'test-policy',
        claim_graph_version: 'test-graph',
        score_cap_when_gate_triggers: 49,
        weights_validation_status: 'indicative_unvalidated_refittable',
        weights: { citation: 30, proposition: 35, currency: 20, balance: 15 },
      },
      integrity_policy: {
        instruction: 'Never fabricate case names, citations, or judgment text.',
        missing_corpus_behaviour: 'fail_loudly',
      },
      tiers: [0, 1, 2, 3].map((tier) => ({
        tier: tier as 0 | 1 | 2 | 3,
        name: 'Tier ' + tier,
        coverage: 'all_queries',
        execution: 'inline',
        model_inference: false,
        checks: [],
      })),
    })
    vi.spyOn(auditRepository, 'listHumanReviews').mockResolvedValue([])
    render(
      <MemoryRouter initialEntries={['/demos']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Five credibility demonstrations/i)).toBeInTheDocument()
    expect(await screen.findByText(/Never fabricate case names/i)).toBeInTheDocument()
    expect(screen.getAllByText('Unmeasured')).toHaveLength(4)
    expect(screen.getByRole('button', { name: /Run demos 1–5/i })).toBeInTheDocument()
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

  it('renders the four-question assurance spine and gate-first scorecard', async () => {
    vi.spyOn(auditRepository, 'getAudit').mockResolvedValue(savedDemoResult)
    render(
      <MemoryRouter initialEntries={['/audits/fixture-audit']}>
        <Routes>
          <Route path="/audits/:id" element={<AuditDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('region', { name: /Four-question assurance spine/i })).toBeInTheDocument()
    expect(screen.getByText(/Does the authority exist and is it correctly identified/i)).toBeInTheDocument()
    expect(screen.getByText(/Gates before weights/i)).toBeInTheDocument()
    expect(screen.getByText(/What each claim says supports it/i)).toBeInTheDocument()
  })
})
