import { FlaskConical, Play, ShieldCheck } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import { dataMode } from '../lib/supabase'
import type { ParserMode } from '../types'

export function NewAuditPage() {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const [parserMode, setParserMode] = useState<ParserMode>('auto')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function loadDemo() {
    setAnswer(await auditRepository.loadDemoAnswer())
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!answer.trim()) return setError('Paste an answer or load the demonstration answer first.')
    setRunning(true)
    setError('')
    try {
      const audit = await auditRepository.submitAudit({
        answer,
        audit_mode: 'citation_only',
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
        description="Tier 0 checks deterministic citation integrity without rewriting or deciding the legal analysis."
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
            placeholder="Paste the AI-generated legal answer, including citations..."
            aria-label="AI-generated legal answer"
          />
          <div className="editor-footer"><span>{answer.length.toLocaleString()} / 20,000 characters</span><span>Raw submissions are not written to application logs.</span></div>
          {error && <ErrorPanel message={error} />}
        </div>
        <aside className="panel run-settings">
          <p className="eyebrow">Run configuration</p>
          <h2>Tier 0 citation integrity</h2>
          <p className="setting-note">Checks citation identity, pinpoints, direct quotes, approved treatment records and deterministic language signals. It does not assess factual fit, legal significance or omissions.</p>
          <label>
            Corpus
            <select disabled value="pilot"><option value="pilot">SG employment restraints - pilot 1</option></select>
          </label>
          <label>
            Claim parser
            <select value={parserMode} onChange={(event) => setParserMode(event.target.value as ParserMode)}>
              <option value="auto">Auto - Gemini with local fallback</option>
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
            {running ? 'Running audit...' : 'Run Tier 0 audit'}
          </button>
          <small>{dataMode === 'supabase' ? 'Result will be saved to your organisation.' : 'Result is retained for this local API session.'}</small>
        </aside>
      </form>
    </section>
  )
}
