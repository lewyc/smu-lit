import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { auditRepository } from '../lib/repository'
import type { Authority } from '../types'
import { AuthoritiesPage } from './AuthoritiesPage'

const authority: Authority = {
  id: 'money-smart', citation: '[2024] SGHC 94', citation_key: '2024SGHC94', case_name: 'MoneySmart Singapore Pte Ltd v Artem Musienko',
  court: 'High Court', court_code: 'SGHC', court_tier: 3, decision_date: '2024-04-02', official_url: 'https://www.elitigation.sg/gd/s/2024_SGHC_94',
  source_status: 'officially_sourced', source_provenance: 'officially_sourced', hierarchy_reviewed: false, precedential_status: 'unknown',
  search_metadata: { citation_key: '2024SGHC94', plain_language_summary: 'Addresses confidential information and broad non-compete clauses.', issue_tags: ['confidential_information'], search_aliases: ['trade secrets'], review_status: 'pending' },
  passages: [{ id: 'p1', paragraph_label: '[72]', text: 'The information had already been shared publicly by the claimant.', supported_propositions: [], limitations: [], source_provenance: 'officially_sourced' }],
}

afterEach(() => vi.restoreAllMocks())

function renderPage() {
  vi.spyOn(auditRepository, 'getCorpus').mockResolvedValue({
    version: 'test', name: 'Test corpus', jurisdiction: 'Singapore', scope_statement: 'Test scope',
    authority_count: 1, passage_count: 1, is_cached: true, active: true, limitations: [], coverage: [],
    snapshot_created_at: '2026-09-06T00:00:00Z', source_status: 'officially_sourced',
    content_hash: 'a'.repeat(64), profile_version: 'test',
  })
  vi.spyOn(auditRepository, 'listAuthorities').mockResolvedValue([authority])
  vi.spyOn(auditRepository, 'getLatestCorpusRefresh').mockResolvedValue(null)
  vi.spyOn(auditRepository, 'listCaseMaps').mockResolvedValue([])
  return render(<MemoryRouter><AuthoritiesPage /></MemoryRouter>)
}

describe('AuthoritiesPage', () => {
  it('starts with compact judgments and review-aware navigation metadata', async () => {
    renderPage()
    expect(await screen.findByText(authority.case_name)).toBeInTheDocument()
    expect(screen.getByText('Draft classification · lawyer review needed')).toBeInTheDocument()
    expect(screen.queryByText(authority.passages[0].text)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create Case Map' })).toHaveAttribute('href', '/case-maps?citation=%5B2024%5D%20SGHC%2094')
  })

  it('searches paragraph text and reveals only relevant passages', async () => {
    renderPage()
    const searchBox = await screen.findByRole('searchbox', { name: 'Search judgments' })
    fireEvent.change(searchBox, { target: { value: 'shared publicly' } })
    expect(await screen.findByText(/Why this matched/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /Relevant passages/ }))
    expect(screen.getByText(authority.passages[0].text)).toBeInTheDocument()
  })

  it('combines filters and clears them', async () => {
    renderPage()
    await screen.findByText(authority.case_name)
    fireEvent.click(screen.getByRole('button', { name: /More filters/ }))
    fireEvent.change(screen.getByLabelText('Legal issue'), { target: { value: 'confidential_information' } })
    expect(screen.getByRole('button', { name: /Confidential information/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(screen.queryByRole('button', { name: /Confidential information/ })).not.toBeInTheDocument()
  })
})
