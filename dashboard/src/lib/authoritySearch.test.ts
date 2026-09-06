import { describe, expect, it } from 'vitest'
import type { Authority } from '../types'
import { rankPassages, searchAuthorities, sortAuthorityMatches } from './authoritySearch'

const authorities: Authority[] = [
  {
    id: 'high-court', citation: '[2024] SGHC 94', citation_key: '2024SGHC94', case_name: 'MoneySmart Singapore Pte Ltd v Artem Musienko',
    court: 'High Court', court_code: 'SGHC', court_tier: 3, decision_date: '2024-04-02', official_url: 'https://www.elitigation.sg/gd/s/2024_SGHC_94',
    source_status: 'officially_sourced', source_provenance: 'officially_sourced',
    search_metadata: { citation_key: '2024SGHC94', plain_language_summary: 'Addresses confidential information and broad non-compete clauses.', issue_tags: ['confidential_information'], search_aliases: ['trade secrets'], review_status: 'pending' },
    passages: [{ id: 'p1', paragraph_label: '[72]', text: 'The information had already been shared publicly.', supported_propositions: [], limitations: [] }],
  },
  {
    id: 'appeal', citation: '[2007] SGCA 53', citation_key: '2007SGCA53', case_name: 'Man Financial v Wong Bark Chuan David',
    court: 'Court of Appeal', court_code: 'SGCA', court_tier: 5, decision_date: '2007-11-02', official_url: 'https://www.elitigation.sg/gd/s/2007_SGCA_53',
    source_status: 'officially_sourced', source_provenance: 'officially_sourced',
    search_metadata: { citation_key: '2007SGCA53', plain_language_summary: 'Addresses employee solicitation and legitimate interests.', issue_tags: ['non_solicitation_non_dealing'], search_aliases: ['staff poaching'], review_status: 'pending' },
    passages: [{ id: 'p2', paragraph_label: '[2]', text: 'This judgment clarifies the doctrine of restraint of trade.', supported_propositions: [], limitations: [] }],
  },
]

describe('authority search', () => {
  it('ranks exact citations above other matches and normalises punctuation', () => {
    const result = searchAuthorities(authorities, '2024 SGHC-94')
    expect(result.map((item) => item.authority.citation_key)).toEqual(['2024SGHC94'])
    expect(result[0].score).toBe(1_000)
  })

  it('finds lay aliases, lawyer terms and paragraph text', () => {
    expect(searchAuthorities(authorities, 'staff poaching')[0].authority.citation_key).toBe('2007SGCA53')
    expect(searchAuthorities(authorities, 'confidential information')[0].authority.citation_key).toBe('2024SGHC94')
    expect(searchAuthorities(authorities, 'shared publicly')[0].matchingPassages[0].paragraph_label).toBe('[72]')
  })

  it('uses court hierarchy then date when relevance is not meaningful', () => {
    const sorted = sortAuthorityMatches(searchAuthorities(authorities, ''), 'relevance', false)
    expect(sorted[0].authority.citation_key).toBe('2007SGCA53')
  })

  it('returns deterministic paragraph matches and snippets', () => {
    const matches = searchAuthorities(authorities, 'shared publicly')
    const passages = rankPassages(matches, 'shared publicly', '', '')
    expect(passages).toHaveLength(1)
    expect(passages[0].snippet).toContain('shared publicly')
  })
})
