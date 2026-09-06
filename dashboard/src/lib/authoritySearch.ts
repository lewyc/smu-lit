import type { Authority, Passage } from '../types'

export const LEGAL_ISSUE_LABELS: Record<string, string> = {
  prima_facie_unenforceable: 'Prima facie unenforceability',
  legitimate_proprietary_interest: 'Legitimate business interest',
  reasonableness_between_parties: 'Reasonableness between the parties',
  reasonableness_public_interest: 'Public-interest reasonableness',
  confidential_information: 'Confidential information',
  customer_connections: 'Customer relationships',
  stable_trained_workforce: 'Stable trained workforce',
  geographic_scope: 'Geographic scope',
  duration_scope: 'Duration',
  activity_scope: 'Restricted activities',
  interim_injunction_standard: 'Interim injunction',
  severance_blue_pencil: 'Severance (blue pencil)',
  cascading_restraint: 'Cascading restraint',
  non_solicitation_non_dealing: 'Non-solicitation / non-dealing',
  policy_freedom_to_trade: 'Freedom to trade',
  outside_corpus_scope: 'Outside corpus scope',
}

export type AuthoritySort = 'relevance' | 'newest' | 'highest_court'

export interface AuthoritySearchMatch {
  authority: Authority
  score: number
  matchingPassages: Passage[]
}

export interface PassageSearchMatch {
  authority: Authority
  passage: Passage
  score: number
  snippet: string
}

export function normaliseSearch(value: string): string {
  return value.normalize('NFKD').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ')
}

function includesQuery(value: string, query: string): boolean {
  return Boolean(query) && normaliseSearch(value).includes(query)
}

function issueText(authority: Authority): string[] {
  return (authority.search_metadata?.issue_tags ?? []).map((tag) => LEGAL_ISSUE_LABELS[tag] ?? tag.replaceAll('_', ' '))
}

function passageMatches(passage: Passage, query: string): boolean {
  if (!query) return false
  return includesQuery(passage.text, query)
    || includesQuery(passage.paragraph_label, query)
    || passage.supported_propositions.some((item) => includesQuery(LEGAL_ISSUE_LABELS[item] ?? item, query))
}

export function searchAuthorities(authorities: Authority[], queryValue: string): AuthoritySearchMatch[] {
  const query = normaliseSearch(queryValue)
  return authorities.map((authority) => {
    const metadata = authority.search_metadata
    const matchingPassages = query ? authority.passages.filter((passage) => passageMatches(passage, query)) : []
    let score = 0
    if (query) {
      if (normaliseSearch(authority.citation) === query) score = 1_000
      else if (includesQuery(authority.citation, query)) score = 900
      else if (includesQuery(authority.case_name, query)) score = 800
      else if ([...(metadata?.search_aliases ?? []), ...issueText(authority)].some((value) => includesQuery(value, query))) score = 600
      else if (metadata && includesQuery(metadata.plain_language_summary, query)) score = 400
      else if (includesQuery(authority.court, query) || includesQuery(authority.court_code ?? '', query)) score = 300
      else if (matchingPassages.length) score = 200
    }
    return { authority, score, matchingPassages }
  }).filter((match) => !query || match.score > 0)
}

export function sortAuthorityMatches(matches: AuthoritySearchMatch[], sort: AuthoritySort, hasQuery: boolean): AuthoritySearchMatch[] {
  const effectiveSort = hasQuery && sort === 'relevance' ? 'relevance' : sort === 'relevance' ? 'highest_court' : sort
  return [...matches].sort((left, right) => {
    if (effectiveSort === 'relevance' && right.score !== left.score) return right.score - left.score
    if (effectiveSort === 'newest') {
      const dateDifference = Date.parse(right.authority.decision_date) - Date.parse(left.authority.decision_date)
      if (dateDifference) return dateDifference
    }
    const tierDifference = (right.authority.court_tier ?? 0) - (left.authority.court_tier ?? 0)
    if (tierDifference) return tierDifference
    return Date.parse(right.authority.decision_date) - Date.parse(left.authority.decision_date)
  })
}

export function passageSnippet(text: string, queryValue: string, length = 240): string {
  const query = normaliseSearch(queryValue)
  if (!query || text.length <= length) return text
  const matchIndex = normaliseSearch(text).indexOf(query)
  if (matchIndex < 0) return text.slice(0, length).trimEnd() + '…'
  const start = Math.max(0, matchIndex - Math.floor(length / 3))
  const end = Math.min(text.length, start + length)
  return (start > 0 ? '…' : '') + text.slice(start, end).trim() + (end < text.length ? '…' : '')
}

export function rankPassages(matches: AuthoritySearchMatch[], queryValue: string, issueTag: string, focusedCitationKey: string): PassageSearchMatch[] {
  const query = normaliseSearch(queryValue)
  const issueQuery = issueTag ? normaliseSearch(LEGAL_ISSUE_LABELS[issueTag] ?? issueTag) : ''
  const passageQuery = query || issueQuery
  const rows: PassageSearchMatch[] = []
  for (const match of matches) {
    if (focusedCitationKey && match.authority.citation_key !== focusedCitationKey) continue
    for (const passage of match.authority.passages) {
      const textMatch = passageQuery ? passageMatches(passage, passageQuery) : Boolean(focusedCitationKey)
      const propositionMatch = issueTag ? passage.supported_propositions.includes(issueTag) : false
      if (!textMatch && !propositionMatch) continue
      rows.push({
        authority: match.authority,
        passage,
        score: match.score + (propositionMatch ? 80 : 0) + (query && includesQuery(passage.text, query) ? 40 : 0),
        snippet: passageSnippet(passage.text, passageQuery),
      })
    }
  }
  return rows.sort((left, right) => right.score - left.score || left.passage.paragraph_label.localeCompare(right.passage.paragraph_label, undefined, { numeric: true }))
}
