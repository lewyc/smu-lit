import { AlertTriangle, CheckCircle2, ExternalLink, Play, Scale, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ErrorPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { HumanReviewItem, VeritasDemoSuite, VeritasOperatingConfig } from '../types'

function targetLabel(value: number | null) {
  return value == null ? 'Unmeasured' : 'Configured ' + value + ' ms · not an achieved result'
}

export function DemosPage() {
  const [config, setConfig] = useState<VeritasOperatingConfig | null>(null)
  const [suite, setSuite] = useState<VeritasDemoSuite | null>(null)
  const [reviews, setReviews] = useState<HumanReviewItem[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([auditRepository.getVeritasConfig(), auditRepository.listHumanReviews()])
      .then(([nextConfig, nextReviews]) => {
        setConfig(nextConfig)
        setReviews(nextReviews)
      })
      .catch((value) => setError(value instanceof Error ? value.message : 'VERITAS configuration is unavailable'))
  }, [])

  async function run() {
    setRunning(true)
    setError('')
    try {
      const result = await auditRepository.runVeritasDemos()
      setSuite(result)
      setReviews(await auditRepository.listHumanReviews())
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Demonstration failed')
    } finally {
      setRunning(false)
    }
  }

  async function decide(review: HumanReviewItem, form: HTMLFormElement) {
    const data = new FormData(form)
    setError('')
    try {
      const updated = await auditRepository.submitHumanDecision(review.public_id, {
        reviewer_name: String(data.get('reviewer_name') ?? ''),
        reviewer_role: String(data.get('reviewer_role')) as 'qualified_lawyer' | 'legal_researcher',
        decision: String(data.get('decision')) as 'confirm' | 'reject' | 'needs_more_evidence',
        rationale: String(data.get('rationale') ?? ''),
      })
      setReviews((items) => items.map((item) => item.public_id === updated.public_id ? updated : item))
      form.reset()
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Review decision could not be recorded')
    }
  }

  return (
    <section className="page">
      <PageHeader
        eyebrow="Pitch-ready proof"
        title="Five credibility demonstrations"
        description="Run source-locked failure cases through the same one-direction Tier 0–3 escalation pipeline."
        action={(
          <button className="button primary" onClick={run} disabled={running}>
            {running ? <span className="spinner small" /> : <Play size={16} />}
            {running ? 'Running source checks…' : 'Run demos 1–5'}
          </button>
        )}
      />

      <div className="integrity-banner panel">
        <ShieldAlert size={22} />
        <div>
          <strong>No fabricated legal material</strong>
          <p>{config?.integrity_policy.instruction ?? 'Loading the repository integrity policy…'}</p>
        </div>
      </div>
      {error && <ErrorPanel message={error} />}

      {config && (
        <div className="tier-overview">
          {config.tiers.map((tier) => (
            <article className="panel tier-summary" key={tier.tier}>
              <span>Tier {tier.tier}</span>
              <h2>{tier.name}</h2>
              <p>{tier.coverage.replaceAll('_', ' ')} · {tier.execution.replaceAll('_', ' ')}</p>
              <strong>{targetLabel(config.measurement_policy.latency_targets_ms['tier_' + tier.tier as keyof typeof config.measurement_policy.latency_targets_ms])}</strong>
            </article>
          ))}
        </div>
      )}

      {suite ? (
        <>
          <div className="demo-run-summary panel">
            <CheckCircle2 size={22} />
            <div>
              <p className="eyebrow">Current-machine result</p>
              <h2>{suite.passed_count} / {suite.demo_count} expected detections reproduced</h2>
              <p>{suite.tier_2_sampling_status}</p>
            </div>
            <small>{suite.config_version}</small>
          </div>
          <div className="demo-stack">
            {suite.results.map((demo, index) => (
              <article className="panel demo-card" key={demo.demo_id}>
                <header>
                  <div><span>Demo {index + 1}</span><h2>{demo.title}</h2></div>
                  <span className={demo.passed ? 'demo-pass' : 'demo-fail'}>
                    {demo.passed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                    {demo.passed ? 'Expected detection' : 'Mismatch'}
                  </span>
                </header>
                <blockquote>{demo.input}</blockquote>
                <div className="demo-outcome">
                  <div><span>Detected</span><strong>{demo.detected_code.replaceAll('_', ' ')}</strong></div>
                  <div><span>Verdict</span><strong>{demo.verdict.replaceAll('_', ' ')}</strong></div>
                  <div><span>Citation gate</span><strong>{demo.citation_gate}</strong></div>
                  <div><span>Currency gate</span><strong>{demo.currency_gate}</strong></div>
                </div>
                <p className="demo-explanation">{demo.explanation}</p>
                <div className="tier-waterfall">
                  {demo.tier_trace.map((tier) => (
                    <div className={'tier-step ' + tier.status} key={tier.tier}>
                      <span>Tier {tier.tier}</span>
                      <strong>{tier.name}</strong>
                      <small>{tier.status.replaceAll('_', ' ')} · {tier.duration_ms == null ? 'No runtime measurement' : tier.duration_ms + ' ms observed'}</small>
                      <p>{tier.reason}</p>
                    </div>
                  ))}
                </div>
                <details className="demo-evidence">
                  <summary>Inspect locked official evidence ({demo.evidence.length})</summary>
                  {demo.evidence.map((evidence) => (
                    <div key={evidence.source_sha256}>
                      <p><strong>{evidence.case_name}</strong> · {evidence.citation} {evidence.paragraph_label}</p>
                      <q>{evidence.text}</q>
                      <a href={evidence.official_url} target="_blank" rel="noreferrer">Official judgment <ExternalLink size={12} /></a>
                      <code>SHA-256 {evidence.source_sha256}</code>
                    </div>
                  ))}
                </details>
              </article>
            ))}
          </div>
        </>
      ) : (
        <div className="panel empty-state benchmark-empty">Run the demos to produce fresh, local evidence. No result is bundled or pre-asserted here.</div>
      )}

      <div className="review-queue panel">
        <div className="panel-heading-inline">
          <div><p className="eyebrow">Tier 3</p><h2>Qualified human review queue</h2></div>
          <span>{reviews.length} queued or reviewed</span>
        </div>
        {!reviews.length && <p className="empty-copy">Run the suite to enqueue the critical and currency-sensitive demonstrations.</p>}
        {reviews.map((review) => (
          <article key={review.public_id}>
            <div>
              <Scale size={18} />
              <div><strong>{review.demo_id.replace('_', ' ')}</strong><p>{review.issue}</p><small>{review.resolution_note}</small></div>
              <span className="status-pill">{review.status.replaceAll('_', ' ')}</span>
            </div>
            <p>{review.decisions.length} decision{review.decisions.length === 1 ? '' : 's'} recorded · gold candidate: {review.gold_candidate ? 'yes' : 'no'}</p>
            {review.status !== 'resolved' && (
              <form onSubmit={(event) => { event.preventDefault(); void decide(review, event.currentTarget) }}>
                <input name="reviewer_name" placeholder="Reviewer name" required minLength={2} />
                <select name="reviewer_role" defaultValue="qualified_lawyer">
                  <option value="qualified_lawyer">Qualified lawyer</option>
                  <option value="legal_researcher">Legal researcher</option>
                </select>
                <select name="decision" defaultValue="confirm">
                  <option value="confirm">Confirm</option>
                  <option value="reject">Reject</option>
                  <option value="needs_more_evidence">Needs more evidence</option>
                </select>
                <textarea name="rationale" placeholder="Independent evidence-based rationale" required minLength={10} />
                <button className="button secondary" type="submit">Record decision</button>
              </form>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
