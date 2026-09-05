import { ExternalLink, RefreshCw, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ErrorPanel, LoadingPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { Authority, CaseMapDetail, CorpusMetadata, RefreshRun } from '../types'

function sourceBadge(authority: Authority, label: string) {
  const official = authority.source_provenance === 'officially_sourced'
  return <span className={'source-badge ' + (official ? 'official' : 'gold')}>{label}</span>
}

export function AuthoritiesPage() {
  const [authorities, setAuthorities] = useState<Authority[]>([])
  const [corpus, setCorpus] = useState<CorpusMetadata | null>(null)
  const [refresh, setRefresh] = useState<RefreshRun | null>(null)
  const [caseMaps, setCaseMaps] = useState<CaseMapDetail[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<number | null>(null)

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

  const filtered = useMemo(() => authorities.filter((authority) => {
    const haystack = authority.case_name + ' ' + authority.citation + ' ' + authority.passages.flatMap((passage) => passage.supported_propositions).join(' ')
    return haystack.toLowerCase().includes(search.toLowerCase())
  }), [authorities, search])
  const refreshing = refresh?.status === 'queued' || refresh?.status === 'running'

  return (
    <section className="page">
      <PageHeader
        eyebrow="Automated corpus"
        title="Official judgment inventory"
        description="Refreshes are capped at 25 SG Courts judgments; everyday audits use only the last successful immutable snapshot."
        action={<button className="button primary" onClick={beginRefresh} disabled={refreshing}><RefreshCw size={16} className={refreshing ? 'spin' : ''} />{refreshing ? 'Refreshing…' : 'AI refresh from SG Courts'}</button>}
      />
      {refresh?.status === 'fallback' && (
        <div className="offline-banner">
          <RefreshCw size={18} />
          <div><strong>Cached snapshot retained</strong><p>{refresh.fallback_reason ?? 'The live source was unavailable; no corpus content changed.'}</p></div>
        </div>
      )}
      {refreshing && (
        <div className="refresh-banner">
          <Sparkles size={18} />
          <div><strong>Refreshing outside the audit path</strong><p>Discovering, validating, and annotating official judgments. Your current snapshot remains available.</p></div>
        </div>
      )}
      {corpus && (
        <div className="corpus-notice">
          <strong>{corpus.is_cached ? 'Cached immutable snapshot.' : 'Active immutable snapshot.'}</strong>
          {' '}{corpus.authority_count} judgments · {corpus.passage_count} passages · {corpus.snapshot_created_at ? new Date(corpus.snapshot_created_at).toLocaleString() : 'awaiting first successful refresh'}.
          {' '}Machine-discovered evidence is always escalated for lawyer context review.
        </div>
      )}
      <div className="panel">
        <div className="panel-toolbar">
          <div><p className="eyebrow">Active version {corpus?.version ?? 'Loading'}</p><h2>{authorities.length} official decisions</h2></div>
          <label className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search citation or proposition" /></label>
        </div>
        {loading && <LoadingPanel label="Loading immutable snapshot" />}
        {error && <ErrorPanel message={error} />}
        <div className="authority-list">
          {filtered.map((authority) => (
            <article className="authority-card" key={authority.id}>
              <div className="authority-title">
                <div>
                  <span>{authority.citation}</span><h3>{authority.case_name}</h3>
                  <p>{authority.court} · {new Date(authority.decision_date).getFullYear()} {authority.retrieved_at ? '· retrieved ' + new Date(authority.retrieved_at).toLocaleDateString() : ''}</p>
                  <div className="source-badge-row">
                    {sourceBadge(authority, authority.source_provenance === 'officially_sourced' ? 'Official SG Courts source' : 'Benchmark gold fixture')}
                    {authority.assessment_status === 'ai_supported' && <span className="source-badge ai">AI annotation retained</span>}
                    <span className="source-badge muted">{authority.court_code ?? 'court unknown'} · tier {authority.court_tier ?? 'unrated'}</span>
                    <span className="source-badge warning">precedent: {authority.hierarchy_reviewed ? authority.precedential_status : 'awaiting legal review'}</span>
                    <span className="source-badge ai">Case Map: {caseMaps.find((item) => item.citation_key === authority.citation_key && item.status !== 'superseded')?.status ?? 'not generated'}</span>
                  </div>
                </div>
                <a href={authority.official_url} target="_blank" rel="noreferrer">Official source <ExternalLink size={13} /></a>
              </div>
              <div className="passage-grid">
                {authority.passages.map((passage) => (
                  <div className="passage-card" key={passage.id}>
                    <strong>{passage.paragraph_label}</strong>
                    <p>{passage.text}</p>
                    <div className="source-badge-row">
                      {passage.source_provenance === 'officially_sourced' && <span className="source-badge official">Official SG Courts source</span>}
                      {passage.assessment_status === 'ai_supported' && <span className="source-badge ai">AI-supported proposition</span>}
                      {passage.assessment_status === 'unannotated' && <span className="source-badge muted">No retained AI proposition</span>}
                    </div>
                    <div className="tag-row">{passage.supported_propositions.map((item) => <span key={item}>{item.replaceAll('_', ' ')}</span>)}</div>
                    {passage.limitations.length > 0 && <small>Limit: {passage.limitations.join(' ')}</small>}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
