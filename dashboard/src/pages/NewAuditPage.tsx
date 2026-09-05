import { FlaskConical, Play, ShieldCheck } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import { dataMode } from '../lib/supabase'
import type { AuditMode, ParserMode } from '../types'

export function NewAuditPage() {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const [parserMode, setParserMode] = useState<ParserMode>('auto')
  const [auditMode, setAuditMode] = useState<AuditMode>('citation_only')
  const [originalQuestion, setOriginalQuestion] = useState('')
  const [facts, setFacts] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function loadDemo() {
    setAnswer(await auditRepository.loadDemoAnswer())
    setOriginalQuestion('Is this employee restraint likely enforceable in Singapore, and what should counsel verify?')
    setFacts('The employee held a commercial role, had customer contact and confidential-information access. The clause lasts one year and has worldwide scope. Interim injunctive relief is contemplated.')
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!answer.trim()) return setError('Paste an answer or load the demonstration answer first.')
    if (auditMode === 'full' && !originalQuestion.trim()) return setError('Full mode requires the original legal question.')
    setRunning(true)
    setError('')
    try {
      const audit = await auditRepository.submitAudit({
        answer,
        audit_mode: auditMode,
        original_question: auditMode === 'full' ? originalQuestion : undefined,
        facts: auditMode === 'full' && facts.trim() ? facts : undefined,
        parser_mode: parserMode,
        persist: dataMode === 'supabase',
      })
      navigate(`/audits/${audit.public_id}`)
    } catch (value) {
      setError(value instanceof Error ? value.message : 'The audit could not be completed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="page">
      <PageHeader
        eyebrow="New assurance run"
        title="Audit an AI-generated answer"
        description="Paste the answer exactly as produced. ProofMark will atomise its claims without rewriting the legal analysis."
      />
      <form className="new-audit-grid" onSubmit={submit}>
        <div className="panel editor-panel">
          <div className="panel-heading-inline">
            <div><p className="eyebrow">Source answer</p><h2>Legal response</h2></div>
            <button className="button secondary" type="button" onClick={loadDemo}><FlaskConical size={16} />Load demonstration answer</button>
          </div>
          <textarea
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            maxLength={20_000}
            placeholder="Paste the AI-generated legal answer, including citations…"
            aria-label="AI-generated legal answer"
          />
          {auditMode === 'full' && (
            <div className="context-fields">
              <label>
                Original legal question
                <textarea
                  className="context-textarea"
                  value={originalQuestion}
                  onChange={(event) => setOriginalQuestion(event.target.value)}
                  maxLength={5_000}
                  placeholder="What question was the AI asked?"
                />
              </label>
              <label>
                Optional factual context
                <textarea
                  className="context-textarea"
                  value={facts}
                  onChange={(event) => setFacts(event.target.value)}
                  maxLength={10_000}
                  placeholder="Duration, territory, employee role, protected interests, procedural stage…"
                />
              </label>
            </div>
          )}
          <div className="editor-footer"><span>{answer.length.toLocaleString()} / 20,000 characters</span><span>Raw submissions are not written to application logs.</span></div>
          {error && <ErrorPanel message={error} />}
        </div>
        <aside className="panel run-settings">
          <p className="eyebrow">Run configuration</p>
          <h2>Bounded by design</h2>
          <label>
            Audit depth
            <select value={auditMode} onChange={(event) => setAuditMode(event.target.value as AuditMode)}>
              <option value="citation_only">Citation only · answer input</option>
              <option value="full">Full · context, omissions and balance</option>
            </select>
          </label>
          <label>
            Corpus
            <select disabled value="pilot"><option value="pilot">SG employment restraints · pilot 1</option></select>
          </label>
          <label>
            Claim parser
            <select value={parserMode} onChange={(event) => setParserMode(event.target.value as ParserMode)}>
              <option value="auto">Auto · Gemini with local fallback</option>
              <option value="local">Local deterministic</option>
              <option value="gemini">Gemini, fall back on failure</option>
            </select>
          </label>
          <div className="assurance-callout">
            <ShieldCheck size={18} />
            <p><strong>Verdicts remain deterministic.</strong> Gemini may structure claims; it cannot create evidence or choose a verdict.</p>
          </div>
          <button className="button primary run-button" disabled={running || !answer.trim()} type="submit">
            {running ? <span className="spinner small" /> : <Play size={16} />}
            {running ? 'Running audit…' : 'Run audit'}
          </button>
          <small>{dataMode === 'supabase' ? 'Result will be saved to your organisation.' : 'Result is retained for this local API session.'}</small>
        </aside>
      </form>
    </section>
  )
}
