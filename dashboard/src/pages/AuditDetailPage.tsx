import { ArrowLeft, ExternalLink, FileText, Flag, RefreshCw, Scale, ShieldCheck, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ErrorPanel, LoadingPanel, PageHeader, VerdictBadge } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { AuditDetail } from '../types'

function excerpt(value: string, maximum = 260) {
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > maximum ? compact.slice(0, maximum).trimEnd() + '…' : compact
}

export function AuditDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [audit, setAudit] = useState<AuditDetail | null>(null)
  const [error, setError] = useState('')
  const [reAuditing, setReAuditing] = useState(false)
  const [reAuditError, setReAuditError] = useState('')
  const [feedbackClaim, setFeedbackClaim] = useState<number | null>(null)
  const [feedbackCategory, setFeedbackCategory] = useState<'wrong_verdict' | 'wrong_proposition' | 'wrong_pinpoint' | 'incorrect_case_map_role' | 'missing_authority' | 'missing_context' | 'outdated_authority' | 'other'>('wrong_verdict')
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackMessage, setFeedbackMessage] = useState('')

  useEffect(() => {
    auditRepository.getAudit(id).then(setAudit).catch((value: Error) => setError(value.message))
  }, [id])

  if (error) return <section className="page"><ErrorPanel message={error} /></section>
  if (!audit) return <section className="page"><LoadingPanel label="Loading evidence report" /></section>

  const metricData = [{ name: 'Citation integrity', value: audit.metrics.citation_integrity }]

  async function submitFeedback(claimOrder: number) {
    if (!feedbackText.trim()) return setFeedbackMessage('Explain what appears inaccurate.')
    try {
      await auditRepository.submitFeedback({ audit_public_id: audit!.public_id, claim_order: claimOrder, category: feedbackCategory, explanation: feedbackText })
      setAudit({ ...audit!, claims: audit!.claims.map((claim) => claim.order === claimOrder ? { ...claim, pending_feedback: true } : claim) })
      setFeedbackMessage('Flag submitted for controlled practitioner review. The verdict and score have not changed.')
      setFeedbackText('')
    } catch (value) { setFeedbackMessage(value instanceof Error ? value.message : 'Feedback could not be submitted.') }
  }

  async function reAuditUnderLatestCorpus() {
    setReAuditing(true)
    setReAuditError('')
    try {
      const refreshed = await auditRepository.reAudit(audit!.public_id)
      setAudit(refreshed)
      navigate('/audits/' + refreshed.public_id, { replace: true })
    } catch (value) {
      setReAuditError(value instanceof Error ? value.message : 'The audit could not be re-run.')
    } finally {
      setReAuditing(false)
    }
  }

  const sourceTimestamp = audit.sources_current_as_of ?? audit.source_checked_at
  const sourceDate = sourceTimestamp ? new Date(sourceTimestamp).toLocaleString() : 'not available'
  const corpusIsStale = audit.corpus_version !== audit.active_corpus_version
  const currencyIsStale = audit.currency_registry_version !== audit.active_currency_registry_version
  const staleTitle = corpusIsStale ? 'A newer source snapshot is active' : 'The reviewed currency register has changed'
  const staleMessage = corpusIsStale
    ? 'This report used ' + audit.corpus_version + '. The active snapshot is ' + (audit.active_corpus_version ?? 'newer') + ' and sources are current as of ' + sourceDate + '.'
    : 'A lawyer-approved treatment, supersession, or amendment record changed after this report was created.'
  const submittedContext = [
    audit.original_question ? 'Question: ' + audit.original_question : '',
    audit.facts ? 'Facts: ' + audit.facts : '',
  ].filter(Boolean).join(' ') || audit.input_text
  const tier0Flags = (audit.flags ?? []).filter((flag) => flag.module !== 'balance_completeness')

  return (
    <section className="page">
      <Link to="/audits" className="back-link"><ArrowLeft size={15} />Back to worklist</Link>
      <PageHeader
        eyebrow="Completed Tier 0 audit"
        title="Citation-integrity report"
        description={`${audit.claims.length} claims · ${audit.processing_duration_ms} ms · ${audit.parser_used} parser · ${audit.audit_mode === 'full' ? 'full contextual audit' : 'citation-only audit'}`}
        action={
          <div className="audit-header-actions">
            <span className={audit.is_saved_demo ? 'source-stamp demo' : 'source-stamp'}>{audit.source_label}</span>
            {!audit.is_saved_demo && (
              <button className="button secondary compact" type="button" disabled={reAuditing} onClick={reAuditUnderLatestCorpus}>
                <RefreshCw className={reAuditing ? 'spin' : ''} size={14} />{reAuditing ? 'Re-auditing…' : 'Re-audit latest'}
              </button>
            )}
          </div>
        }
      />
      {audit.is_saved_demo && (
        <div className="offline-banner">
          <FileText size={18} />
          <div><strong>Saved demonstration result</strong><p>The API was unavailable. This is a bundled, pre-computed example—not a newly run audit.</p></div>
        </div>
      )}
      {audit.is_stale && (
        <div className="freshness-banner" role="status">
          <TriangleAlert size={18} />
          <div>
            <strong>{staleTitle}</strong>
            <p>{staleMessage} {currencyIsStale && corpusIsStale ? 'The reviewed currency register also changed. ' : ''}Re-audit to create a separate, traceable report under the latest review context.</p>
          </div>
        </div>
      )}
      {reAuditError && <ErrorPanel message={reAuditError} />}
      <section id="submitted-input" className="panel submitted-input-panel">
        <div className="submitted-input-heading">
          <div><p className="eyebrow">Original user input</p><h2>Material assessed in this audit</h2></div>
          <span>{audit.audit_mode === 'full' ? 'Full contextual audit' : 'Citation-only audit'}</span>
        </div>
        <div className="submission-block">
          <strong>AI answer submitted for evaluation</strong>
          <pre aria-label="AI answer submitted for evaluation">{audit.input_text}</pre>
        </div>
        {(audit.original_question || audit.facts) && (
          <div className="submitted-context-grid">
            {audit.original_question && <div className="submission-block"><strong>Original legal question</strong><p>{audit.original_question}</p></div>}
            {audit.facts && <div className="submission-block"><strong>Facts supplied for context</strong><p>{audit.facts}</p></div>}
          </div>
        )}
      </section>
      <div className="detail-top-grid">
        <div className="panel metric-chart">
          <div><p className="eyebrow">Tier 0 metric</p><h2>Citation integrity</h2></div>
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
          <p className="metric-note">This is a deterministic evidence-integrity indicator, not a probability that the legal answer is correct.</p>
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
            <div><dt>Parser version</dt><dd>{audit.parser_version}</dd></div>
            <div><dt>Result cache</dt><dd>{audit.cache_status === 'hit' ? 'Source-versioned cache hit' : audit.cache_status === 'bypassed' ? 'Bypassed for a fresh run' : 'Freshly evaluated'}</dd></div>
            <div><dt>Sources current as of</dt><dd>{sourceDate}</dd></div>
            <div><dt>Currency register</dt><dd>{audit.currency_registry_version ?? 'legacy audit · not captured'}</dd></div>
          </dl>
          {audit.parser_fallback_reason && <div className="fallback-note">{audit.parser_fallback_reason}</div>}
        </div>
      </div>

      {tier0Flags.length > 0 && (
        <section id="review-prompts" className="panel framework-flags">
          <p className="eyebrow">Tier 0 review flags</p>
          <h2>Lawyer review prompts</h2>
          <p className="prompt-intro">Each prompt links to the claim or submitted context that triggered it.</p>
          {tier0Flags.map((flag, index) => {
            const referencedClaim = flag.claim_order == null
              ? undefined
              : audit.claims.find((claim) => claim.order === flag.claim_order)
            return (
              <div className="framework-flag" key={flag.code + '-' + index}>
                <span className={'status-pill ' + flag.severity}>{flag.severity}</span>
                <div>
                  <p><strong>{flag.code.replaceAll('_', ' ')}</strong> · {flag.message}</p>
                  {referencedClaim ? (
                    <a className="prompt-reference" href={'#claim-' + referencedClaim.order}>
                      <span>Refers to claim {referencedClaim.order.toString().padStart(2, '0')}</span>
                      <q>{excerpt(referencedClaim.text)}</q>
                    </a>
                  ) : (
                    <a className="prompt-reference" href="#submitted-input">
                      <span>Derived from the submitted question, facts, or answer</span>
                      <q>{excerpt(submittedContext)}</q>
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </section>
      )}

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
                <span><strong>Language modality</strong>{claim.modality ?? 'not assessed'}</span>
                <span><strong>Citation identity</strong>{claim.citation_identity_status?.replaceAll('_', ' ') ?? 'not assessed'}</span>
                <span><strong>Pinpoint</strong>{claim.pinpoint_status?.replaceAll('_', ' ') ?? 'not assessed'}</span>
                <span><strong>Direct quote</strong>{claim.quote_status?.replaceAll('_', ' ') ?? 'not present'}</span>
                <span><strong>Source role</strong>{claim.source_role_status?.replaceAll('_', ' ') ?? 'unreviewed'}</span>
                <span><strong>Currency</strong>{claim.currency_status?.replaceAll('_', ' ') ?? 'not verified'}</span>
                <span><strong>Decision rule</strong>{claim.decision_rule_id ?? 'legacy result'}</span>
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
                  <div className="source-badge-row evidence-badges">
                    {evidence.officially_sourced && <span className="source-badge official">Official SG Courts source</span>}
                    {evidence.ai_supported && <span className="source-badge ai">AI-supported proposition</span>}
                    {evidence.passage.source_role_reviewed && <span className="source-badge muted">Reviewed role: {evidence.passage.source_role?.replaceAll('_', ' ')}</span>}
                    {evidence.passage.annotation_disagrees && <span className="source-badge warning">Taxonomy disagreement · lawyer review</span>}
                    {!evidence.officially_sourced && !evidence.ai_supported && <span className="source-badge muted">Saved demonstration evidence</span>}
                  </div>
                  <blockquote>{evidence.passage.text}</blockquote>
                  {evidence.passage.limitations.length > 0 && (
                    <div className="limitations"><strong>Recorded limitations</strong><ul>{evidence.passage.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  )}
                  <a href={evidence.official_url} target="_blank" rel="noreferrer">Open official judgment <ExternalLink size={13} /></a>
                </details>
              ))}
              <div className="feedback-action">
                <button className="button secondary" type="button" onClick={() => { setFeedbackClaim(feedbackClaim === claim.order ? null : claim.order); setFeedbackMessage('') }}><Flag size={15} />Flag this evaluation</button>
                {claim.pending_feedback && <span className="status-pill warning">under review · verdict unchanged</span>}
              </div>
              {feedbackClaim === claim.order && (
                <div className="feedback-form">
                  <select value={feedbackCategory} onChange={(event) => setFeedbackCategory(event.target.value as typeof feedbackCategory)}>
                    <option value="wrong_verdict">Wrong verdict</option><option value="wrong_proposition">Wrong proposition</option><option value="wrong_pinpoint">Wrong pinpoint</option><option value="incorrect_case_map_role">Incorrect Case Map role</option><option value="missing_authority">Missing authority</option><option value="missing_context">Missing context</option><option value="outdated_authority">Outdated authority</option><option value="other">Other</option>
                  </select>
                  <textarea value={feedbackText} onChange={(event) => setFeedbackText(event.target.value)} placeholder="Explain the inaccuracy and, if possible, identify the correct authority or paragraph." />
                  <button className="button primary" type="button" onClick={() => submitFeedback(claim.order)}>Submit for review</button>
                  {feedbackMessage && <small>{feedbackMessage}</small>}
                </div>
              )}
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
