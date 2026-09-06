import { ExternalLink, Filter, RefreshCw, Search, Sparkles, X } from 'lucide-react'
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorPanel, LoadingPanel, PageHeader } from '../components/Common'
import {
  LEGAL_ISSUE_LABELS,
  passageSnippet,
  rankPassages,
  searchAuthorities,
  sortAuthorityMatches,
  type AuthoritySort,
} from '../lib/authoritySearch'
import { auditRepository } from '../lib/repository'
import type { Authority, CaseMapDetail, CorpusMetadata, RefreshRun } from '../types'

type AuthorityView = 'judgments' | 'passages'
type CourtFilter = 'all' | 'SGCA' | 'SGHC'
type ReviewFilter = 'all' | 'pending' | 'approved'
type CaseMapFilter = 'all' | 'available' | 'missing'

function caseMapFor(authority: Authority, maps: CaseMapDetail[]) {
  return maps.find((item) => item.citation_key === authority.citation_key && item.status !== 'superseded')
}

function reviewLabel(authority: Authority) {
  if (!authority.search_metadata) return 'No curated classification'
  return authority.search_metadata.review_status === 'approved' ? 'Classification reviewed' : 'Draft classification · lawyer review needed'
}

export function AuthoritiesPage() {
  const [authorities, setAuthorities] = useState<Authority[]>([])
  const [corpus, setCorpus] = useState<CorpusMetadata | null>(null)
  const [refresh, setRefresh] = useState<RefreshRun | null>(null)
  const [caseMaps, setCaseMaps] = useState<CaseMapDetail[]>([])
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [view, setView] = useState<AuthorityView>('judgments')
  const [court, setCourt] = useState<CourtFilter>('all')
  const [year, setYear] = useState('all')
  const [issue, setIssue] = useState('all')
  const [review, setReview] = useState<ReviewFilter>('all')
  const [mapFilter, setMapFilter] = useState<CaseMapFilter>('all')
  const [sort, setSort] = useState<AuthoritySort>('highest_court')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [focusedCitationKey, setFocusedCitationKey] = useState('')
  const [passageLimit, setPassageLimit] = useState(50)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<number | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)

  async function load() {
    const [nextCorpus, nextAuthorities, latest, nextMaps] = await Promise.all([
      auditRepository.getCorpus(),
      auditRepository.listAuthorities(),
      auditRepository.getLatestCorpusRefresh(),
      auditRepository.listCaseMaps(),
    ])
    setCorpus(nextCorpus)
    setAuthorities(nextAuthorities)
    setRefresh(latest)
    setCaseMaps(nextMaps)
  }

  useEffect(() => {
    load().catch((value: Error) => setError(value.message)).finally(() => setLoading(false))
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [])

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const editing = target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA' || target?.tagName === 'SELECT'
      if (event.key === '/' && !editing) {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', focusSearch)
    return () => window.removeEventListener('keydown', focusSearch)
  }, [])

  function stopPolling() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function beginRefresh() {
    setError('')
    try {
      const started = await auditRepository.startCorpusRefresh()
      setRefresh(started)
      stopPolling()
      pollRef.current = window.setInterval(async () => {
        try {
          const latest = await auditRepository.getLatestCorpusRefresh()
          setRefresh(latest)
          if (latest && !['queued', 'running'].includes(latest.status)) {
            stopPolling()
            await load()
          }
        } catch (value) {
          stopPolling()
          setError(value instanceof Error ? value.message : 'Unable to read refresh progress')
        }
      }, 2000)
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Unable to start corpus refresh')
    }
  }

  const years = useMemo(() => [...new Set(authorities.map((authority) => new Date(authority.decision_date).getFullYear()))].sort((a, b) => b - a), [authorities])
  const issues = useMemo(() => [...new Set(authorities.flatMap((authority) => authority.search_metadata?.issue_tags ?? []))]
    .sort((left, right) => (LEGAL_ISSUE_LABELS[left] ?? left).localeCompare(LEGAL_ISSUE_LABELS[right] ?? right)), [authorities])

  const filteredMatches = useMemo(() => {
    const matches = searchAuthorities(authorities, deferredSearch).filter(({ authority }) => {
      const map = caseMapFor(authority, caseMaps)
      return (court === 'all' || authority.court_code === court)
        && (year === 'all' || String(new Date(authority.decision_date).getFullYear()) === year)
        && (issue === 'all' || authority.search_metadata?.issue_tags.includes(issue))
        && (review === 'all' || authority.search_metadata?.review_status === review)
        && (mapFilter === 'all' || (mapFilter === 'available' ? Boolean(map) : !map))
    })
    return sortAuthorityMatches(matches, sort, Boolean(deferredSearch.trim()))
  }, [authorities, caseMaps, court, deferredSearch, issue, mapFilter, review, sort, year])

  const passageMatches = useMemo(() => rankPassages(filteredMatches, deferredSearch, issue === 'all' ? '' : issue, focusedCitationKey), [deferredSearch, filteredMatches, focusedCitationKey, issue])

  const hasCriteria = Boolean(search.trim()) || court !== 'all' || year !== 'all' || issue !== 'all'
    || review !== 'all' || mapFilter !== 'all' || Boolean(focusedCitationKey)
  const refreshing = refresh?.status === 'queued' || refresh?.status === 'running'
  const activeFilters = [
    court !== 'all' ? { key: 'court', label: court === 'SGCA' ? 'Court of Appeal (SGCA)' : 'High Court (SGHC)' } : null,
    year !== 'all' ? { key: 'year', label: `Year: ${year}` } : null,
    issue !== 'all' ? { key: 'issue', label: LEGAL_ISSUE_LABELS[issue] ?? issue } : null,
    review !== 'all' ? { key: 'review', label: review === 'approved' ? 'Classification reviewed' : 'Draft classification' } : null,
    mapFilter !== 'all' ? { key: 'map', label: mapFilter === 'available' ? 'Case Map available' : 'No Case Map' } : null,
    focusedCitationKey ? { key: 'focused', label: authorities.find((item) => item.citation_key === focusedCitationKey)?.citation ?? focusedCitationKey } : null,
  ].filter((item): item is { key: string; label: string } => Boolean(item))

  function resetPassages() { setPassageLimit(50) }

  function clearFilter(key: string) {
    if (key === 'court') setCourt('all')
    if (key === 'year') setYear('all')
    if (key === 'issue') setIssue('all')
    if (key === 'review') setReview('all')
    if (key === 'map') setMapFilter('all')
    if (key === 'focused') setFocusedCitationKey('')
    resetPassages()
  }

  function clearAll() {
    setSearch('')
    setCourt('all')
    setYear('all')
    setIssue('all')
    setReview('all')
    setMapFilter('all')
    setSort('highest_court')
    setFocusedCitationKey('')
    resetPassages()
    searchRef.current?.focus()
  }

  function showPassages(authority: Authority) {
    setFocusedCitationKey(authority.citation_key)
    setView('passages')
    resetPassages()
  }

  return (
    <section className="page authorities-page">
      <PageHeader eyebrow="Automated corpus" title="Official judgment inventory" description="Find a decision first, then inspect only the official paragraphs that matter. Draft classifications are navigation aids, not legal conclusions." action={<button className="button primary" onClick={beginRefresh} disabled={refreshing}><RefreshCw size={16} className={refreshing ? 'spin' : ''} />{refreshing ? 'Refreshing…' : 'AI refresh from SG Courts'}</button>} />
      {refresh?.status === 'fallback' && <div className="offline-banner"><RefreshCw size={18} /><div><strong>Cached snapshot retained</strong><p>{refresh.fallback_reason ?? 'The live source was unavailable; no corpus content changed.'}</p></div></div>}
      {refreshing && <div className="refresh-banner"><Sparkles size={18} /><div><strong>Refreshing outside the audit path</strong><p>Discovering, validating, and annotating official judgments. Your current snapshot remains available.</p></div></div>}
      {corpus && <div className="corpus-notice"><strong>{corpus.is_cached ? 'Cached immutable snapshot.' : 'Active immutable snapshot.'}</strong>{' '}{corpus.authority_count} judgments · {corpus.passage_count} passages · {corpus.snapshot_created_at ? new Date(corpus.snapshot_created_at).toLocaleString() : 'awaiting first successful refresh'}.{' '}Machine-discovered evidence is always escalated for lawyer context review.</div>}

      <div className="panel authority-search-panel">
        <div className="authority-search-header">
          <div><p className="eyebrow">Active version {corpus?.version ?? 'Loading'}</p><h2>Search official decisions</h2></div>
          <label className="authority-sort-field">Sort<select aria-label="Sort authorities" value={sort} onChange={(event) => setSort(event.target.value as AuthoritySort)}><option value="relevance">Most relevant</option><option value="newest">Newest first</option><option value="highest_court">Highest court first</option></select></label>
        </div>
        <div className="authority-search-control"><Search size={18} aria-hidden="true" /><input ref={searchRef} type="search" aria-label="Search judgments" value={search} onChange={(event) => { const next = event.target.value; if (!search.trim() && next.trim() && sort === 'highest_court') setSort('relevance'); if (search.trim() && !next.trim() && sort === 'relevance') setSort('highest_court'); setSearch(next); setFocusedCitationKey(''); resetPassages() }} placeholder="Search case name, citation, court, legal issue or paragraph text" /><kbd aria-hidden="true">/</kbd></div>
        <p className="authority-search-examples">Try “non-compete”, “[2024] SGHC 94”, “Court of Appeal” or “confidential information”.</p>
        <div className="authority-view-tabs" role="tablist" aria-label="Authority result type"><button type="button" role="tab" aria-selected={view === 'judgments'} onClick={() => setView('judgments')}>Judgments <span>{filteredMatches.length}</span></button><button type="button" role="tab" aria-selected={view === 'passages'} onClick={() => setView('passages')}>Relevant passages <span>{hasCriteria ? passageMatches.length : corpus?.passage_count ?? 0}</span></button></div>
        <div className="authority-filter-area">
          <div className="authority-quick-filters" aria-label="Filter by court"><span>Court</span><button type="button" aria-pressed={court === 'all'} onClick={() => { setCourt('all'); resetPassages() }}>All courts · {authorities.length}</button><button type="button" aria-pressed={court === 'SGCA'} onClick={() => { setCourt('SGCA'); resetPassages() }}>Court of Appeal (SGCA) · {authorities.filter((item) => item.court_code === 'SGCA').length}</button><button type="button" aria-pressed={court === 'SGHC'} onClick={() => { setCourt('SGHC'); resetPassages() }}>High Court (SGHC) · {authorities.filter((item) => item.court_code === 'SGHC').length}</button><button className="authority-more-filters" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><Filter size={15} />More filters</button></div>
          {filtersOpen && <div className="authority-advanced-filters"><label>Decision year<select value={year} onChange={(event) => { setYear(event.target.value); resetPassages() }}><option value="all">Any year</option>{years.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label>Legal issue<select value={issue} onChange={(event) => { setIssue(event.target.value); resetPassages() }}><option value="all">Any issue</option>{issues.map((item) => <option key={item} value={item}>{LEGAL_ISSUE_LABELS[item] ?? item.replaceAll('_', ' ')}</option>)}</select></label><label>Classification review<select value={review} onChange={(event) => { setReview(event.target.value as ReviewFilter); resetPassages() }}><option value="all">Any state</option><option value="pending">Draft · lawyer review needed</option><option value="approved">Reviewed</option></select></label><label>Case Map<select value={mapFilter} onChange={(event) => { setMapFilter(event.target.value as CaseMapFilter); resetPassages() }}><option value="all">Any status</option><option value="available">Available</option><option value="missing">Not generated</option></select></label></div>}
          {activeFilters.length > 0 && <div className="authority-active-filters" aria-label="Active filters">{activeFilters.map((filter) => <button type="button" key={filter.key} onClick={() => clearFilter(filter.key)}>{filter.label}<X size={13} aria-hidden="true" /></button>)}<button className="authority-clear" type="button" onClick={clearAll}>Clear all</button></div>}
        </div>
        {loading && <LoadingPanel label="Loading immutable snapshot" />}
        {error && <ErrorPanel message={error} />}
        {!loading && !error && <div className="authority-result-summary" aria-live="polite"><strong>{view === 'judgments' ? `${filteredMatches.length} ${filteredMatches.length === 1 ? 'judgment' : 'judgments'}` : `${passageMatches.length} relevant ${passageMatches.length === 1 ? 'passage' : 'passages'}`}</strong>{search.trim() && <span>for “{search.trim()}”</span>}</div>}

        {!loading && !error && view === 'judgments' && <div className="authority-results" role="tabpanel" aria-label="Judgment results">
          {filteredMatches.length === 0 && <div className="empty-state">No judgments match. Try a broader term or clear a filter.</div>}
          {filteredMatches.map(({ authority, matchingPassages }) => {
            const map = caseMapFor(authority, caseMaps)
            const bestMatch = matchingPassages[0]
            return <article className="authority-result" key={authority.id}><div className="authority-result-main"><span className="authority-citation">{authority.citation}</span><h3>{authority.case_name}</h3><p className="authority-result-meta">{authority.court} · {new Date(authority.decision_date).getFullYear()} · {authority.passages.length} indexed passages</p><p className="authority-summary">{authority.search_metadata?.plain_language_summary ?? 'No curated plain-language summary is available. Search uses official judgment text only.'}</p><div className="authority-status-row"><span className={authority.source_provenance === 'officially_sourced' ? 'authority-status official' : 'authority-status neutral'}>{authority.source_provenance === 'officially_sourced' ? 'Official SG Courts source' : 'Source provenance unconfirmed'}</span><span className={authority.source_review_status === 'approved' ? 'authority-status reviewed' : 'authority-status warning'}>{authority.source_review_status === 'approved' ? 'Source reviewed' : 'Source review pending'}</span><span className={authority.search_metadata?.review_status === 'approved' ? 'authority-status reviewed' : authority.search_metadata ? 'authority-status warning' : 'authority-status neutral'}>{reviewLabel(authority)}</span><span className="authority-status neutral">{authority.hierarchy_reviewed ? `Precedent: ${authority.precedential_status}` : 'Precedent status not reviewed'}</span><span className="authority-status neutral">Case Map: {map?.status ?? 'not generated'}</span></div>{(authority.search_metadata?.issue_tags.length ?? 0) > 0 && <div className="authority-issue-row" aria-label="Draft legal issue classifications">{authority.search_metadata?.issue_tags.map((tag) => <span key={tag}>{LEGAL_ISSUE_LABELS[tag] ?? tag.replaceAll('_', ' ')}</span>)}</div>}{search.trim() && bestMatch && <p className="authority-match"><strong>Why this matched · {bestMatch.paragraph_label}</strong>{passageSnippet(bestMatch.text, search, 260)}</p>}</div><div className="authority-result-actions"><a className="button secondary compact" href={authority.official_url} target="_blank" rel="noreferrer">Open official judgment <ExternalLink size={13} /></a><button className="button primary compact" type="button" onClick={() => showPassages(authority)}>View relevant passages</button><Link className="authority-map-link" to={`/case-maps?citation=${encodeURIComponent(authority.citation)}`}>{map ? 'Open Case Map' : 'Create Case Map'}</Link></div></article>
          })}
        </div>}

        {!loading && !error && view === 'passages' && <div className="authority-results passage-results" role="tabpanel" aria-label="Relevant passage results">
          {!hasCriteria && <div className="authority-passage-prompt"><Search size={22} /><strong>Search or apply a filter to find relevant paragraphs.</strong><span>This view stays empty initially so the complete {corpus?.passage_count ?? 0}-passage corpus is never dumped onto the page.</span></div>}
          {hasCriteria && passageMatches.length === 0 && <div className="empty-state">No paragraph-level matches were found. Draft authority labels may not yet have reviewed paragraph annotations.</div>}
          {hasCriteria && passageMatches.slice(0, passageLimit).map(({ authority, passage, snippet }) => <article className="passage-result" key={`${authority.id}-${passage.id}`}><div className="passage-result-heading"><span>{authority.citation} · {passage.paragraph_label}</span><a href={authority.official_url} target="_blank" rel="noreferrer">Official source <ExternalLink size={12} /></a></div><h3>{authority.case_name}</h3><p>{snippet}</p><div className="authority-status-row"><span className="authority-status official">Official judgment text</span>{passage.source_role_reviewed ? <span className="authority-status reviewed">Reviewed role: {passage.source_role?.replaceAll('_', ' ')}</span> : <span className="authority-status warning">Judicial role not reviewed</span>}</div></article>)}
          {hasCriteria && passageMatches.length > passageLimit && <button className="button secondary authority-show-more" type="button" onClick={() => setPassageLimit((value) => value + 50)}>Show next 50 passages</button>}
        </div>}
      </div>
    </section>
  )
}
