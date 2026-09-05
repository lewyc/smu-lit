import { ArrowRight, Database, Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorPanel, LoadingPanel, PageHeader, VerdictBadge } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { AuditSummary, AuditVerdict } from '../types'

export function AuditsPage() {
  const [audits, setAudits] = useState<AuditSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [verdict, setVerdict] = useState<AuditVerdict | ''>('')

  useEffect(() => {
    auditRepository.listAudits()
      .then(setAudits)
      .catch((value: Error) => setError(value.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(
    () => audits.filter((audit) => {
      const matchesText = audit.input_preview.toLowerCase().includes(search.toLowerCase())
      const matchesVerdict = !verdict || (audit.summary_counts[verdict] ?? 0) > 0
      return matchesText && matchesVerdict
    }),
    [audits, search, verdict],
  )

  const totals = audits.reduce(
    (result, audit) => {
      result.claims += Object.values(audit.summary_counts).reduce((sum, count) => sum + count, 0)
      result.review += audit.summary_counts.context_review + audit.summary_counts.unsupported
        + audit.summary_counts.likely_fabricated + audit.summary_counts.unverified
      return result
    },
    { claims: 0, review: 0 },
  )

  return (
    <section className="page">
      <PageHeader
        eyebrow="Audit operations"
        title="Assurance worklist"
        description="Track claim-level evidence, citation integrity, and the lawyer review queue."
        action={<Link className="button primary" to="/audits/new"><Plus size={16} />New audit</Link>}
      />
      <div className="metric-grid">
        <div className="metric-card"><span>Completed audits</span><strong>{audits.length}</strong><small>Current session or organisation</small></div>
        <div className="metric-card"><span>Claims assessed</span><strong>{totals.claims}</strong><small>Atomic legal propositions</small></div>
        <div className="metric-card metric-warn"><span>Lawyer review</span><strong>{totals.review}</strong><small>Non-verified in-scope claims</small></div>
      </div>
      <div className="panel table-panel">
        <div className="panel-toolbar">
          <div>
            <p className="eyebrow">Recent runs</p>
            <h2>Audit history</h2>
          </div>
          <div className="filters">
            <label className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search answer text" /></label>
            <select value={verdict} onChange={(event) => setVerdict(event.target.value as AuditVerdict | '')} aria-label="Filter by verdict">
              <option value="">All verdicts</option>
              <option value="verified">Verified</option>
              <option value="context_review">Context review</option>
              <option value="unsupported">Unsupported</option>
              <option value="likely_fabricated">Likely fabricated</option>
              <option value="unverified">Unverified</option>
            </select>
          </div>
        </div>
        {loading && <LoadingPanel label="Loading audits" />}
        {error && <ErrorPanel message={error} />}
        {!loading && !error && (
          <div className="audit-list">
            {filtered.map((audit) => {
              const primaryVerdict: AuditVerdict = audit.summary_counts.likely_fabricated
                ? 'likely_fabricated'
                : audit.summary_counts.unsupported
                  ? 'unsupported'
                  : audit.summary_counts.context_review
                    ? 'context_review'
                    : 'verified'
              return (
                <Link to={`/audits/${audit.public_id}`} className="audit-row" key={audit.public_id}>
                  <div className="source-icon"><Database size={17} /></div>
                  <div className="audit-row-main">
                    <div className="row-title">
                      <strong>{audit.input_preview}{audit.input_preview.length >= 120 ? '…' : ''}</strong>
                      {audit.is_saved_demo && <span className="saved-label">Saved demonstration result</span>}
                    </div>
                    <span>{new Date(audit.created_at).toLocaleString()} · {audit.parser_used} parser</span>
                  </div>
                  <VerdictBadge verdict={primaryVerdict} />
                  <div className="score"><strong>{audit.metrics.grounded_coverage}%</strong><span>grounded</span></div>
                  <ArrowRight size={17} />
                </Link>
              )
            })}
            {!filtered.length && <div className="empty-state">No audit matches these filters.</div>}
          </div>
        )}
      </div>
    </section>
  )
}
