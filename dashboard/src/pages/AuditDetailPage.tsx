import { ArrowLeft, ExternalLink, FileText, Scale, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ErrorPanel, LoadingPanel, PageHeader, VerdictBadge } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { AuditDetail } from '../types'

export function AuditDetailPage() {
  const { id = '' } = useParams()
  const [audit, setAudit] = useState<AuditDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    auditRepository.getAudit(id).then(setAudit).catch((value: Error) => setError(value.message))
  }, [id])

  if (error) return <section className="page"><ErrorPanel message={error} /></section>
  if (!audit) return <section className="page"><LoadingPanel label="Loading evidence report" /></section>

  const metricData = [
    { name: 'Citation integrity', value: audit.metrics.citation_integrity },
    { name: 'Grounded coverage', value: audit.metrics.grounded_coverage },
    { name: 'Contextual support', value: audit.metrics.contextual_support },
  ]

  return (
    <section className="page">
      <Link to="/audits" className="back-link"><ArrowLeft size={15} />Back to worklist</Link>
      <PageHeader
        eyebrow="Completed audit"
        title="Evidence-linked assurance report"
        description={`${audit.claims.length} claims · ${audit.processing_duration_ms} ms · ${audit.parser_used} parser`}
        action={<span className={audit.is_saved_demo ? 'source-stamp demo' : 'source-stamp'}>{audit.source_label}</span>}
      />
      {audit.is_saved_demo && (
        <div className="offline-banner">
          <FileText size={18} />
          <div><strong>Saved demonstration result</strong><p>The API was unavailable. This is a bundled, pre-computed example—not a newly run audit.</p></div>
        </div>
      )}
      <div className="detail-top-grid">
        <div className="panel metric-chart">
          <div><p className="eyebrow">Transparent metrics</p><h2>Audit posture</h2></div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={185}>
              <BarChart data={metricData} layout="vertical" margin={{ left: 8, right: 22 }}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis dataKey="name" type="category" width={128} axisLine={false} tickLine={false} tick={{ fill: '#42526b', fontSize: 12 }} />
                <Tooltip formatter={(value) => [`${value}%`, 'Score']} cursor={{ fill: '#f3f6f8' }} />
                <Bar dataKey="value" fill="#008d86" radius={[0, 4, 4, 0]} barSize={17}>
                  <LabelList dataKey="value" position="right" formatter={(value: number) => `${value}%`} fill="#0b1f49" fontSize={12} fontWeight={700} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="metric-note">These are coverage indicators, not a probability that the legal answer is correct.</p>
        </div>
        <div className="panel provenance-panel">
          <p className="eyebrow">Provenance</p>
          <h2>Reproducible run</h2>
          <dl>
            <div><dt>Engine</dt><dd>{audit.engine_version}</dd></div>
            <div><dt>Corpus</dt><dd>{audit.corpus_version}</dd></div>
            <div><dt>Taxonomy</dt><dd>{audit.taxonomy_version}</dd></div>
            <div><dt>Parser requested</dt><dd>{audit.parser_requested}</dd></div>
            <div><dt>Parser used</dt><dd>{audit.parser_used}</dd></div>
          </dl>
          {audit.parser_fallback_reason && <div className="fallback-note">{audit.parser_fallback_reason}</div>}
        </div>
      </div>

      <div className="report-grid">
        <aside className="claim-rail panel">
          <p className="eyebrow">Claim rail</p>
          {audit.claims.map((claim) => (
            <a href={`#claim-${claim.order}`} key={claim.order}>
              <span>{claim.order.toString().padStart(2, '0')}</span>
              <VerdictBadge verdict={claim.verdict} />
            </a>
          ))}
        </aside>
        <div className="claims-column">
          {audit.claims.map((claim) => (
            <article id={`claim-${claim.order}`} className={`panel claim-card claim-${claim.verdict}`} key={claim.order}>
              <div className="claim-heading">
                <div><p className="eyebrow">Claim {claim.order.toString().padStart(2, '0')}</p><h2>{claim.text}</h2></div>
                <VerdictBadge verdict={claim.verdict} />
              </div>
              <div className="claim-meta">
                <span><strong>Proposition</strong>{claim.proposition.replaceAll('_', ' ')}</span>
                <span><strong>Citation</strong>{claim.citation ?? 'No citation supplied'} {claim.pinpoint ?? ''}</span>
                <span><strong>Parser confidence</strong>{Math.round(claim.parser_confidence * 100)}%</span>
              </div>
              <div className="rationale">
                <Scale size={17} />
                <div><strong>Why this verdict</strong><p>{claim.rationale}</p></div>
              </div>
              {claim.missing_evidence && (
                <div className="missing-evidence"><strong>What is missing</strong><p>{claim.missing_evidence}</p></div>
              )}
              {claim.evidence.map((evidence) => (
                <details className="evidence-box" key={evidence.passage.id} open={claim.verdict === 'verified'}>
                  <summary>
                    <span><strong>{evidence.authority_citation} · {evidence.passage.paragraph_label}</strong><small>{evidence.relation} · lexical rank {Math.round(evidence.score * 100)}%</small></span>
                    <span>View exact stored passage</span>
                  </summary>
                  <blockquote>{evidence.passage.text}</blockquote>
                  {evidence.passage.limitations.length > 0 && (
                    <div className="limitations"><strong>Recorded limitations</strong><ul>{evidence.passage.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  )}
                  <a href={evidence.official_url} target="_blank" rel="noreferrer">Open official judgment <ExternalLink size={13} /></a>
                </details>
              ))}
            </article>
          ))}
        </div>
      </div>

      {audit.handoff && (
        <section className="panel handoff-panel">
          <div className="handoff-heading"><span><ShieldCheck size={20} /></span><div><p className="eyebrow">Lawyer handoff</p><h2>{audit.handoff.issue}</h2></div></div>
          <div className="handoff-grid">
            <div><strong>Established in the pilot corpus</strong><ul>{audit.handoff.established_points.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><strong>Relevant authorities</strong><ul>{audit.handoff.relevant_authorities.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><strong>Unresolved questions</strong><ul>{audit.handoff.unresolved_questions.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </div>
        </section>
      )}
    </section>
  )
}
