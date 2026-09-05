import { CheckCircle2, Gauge, Play } from 'lucide-react'
import { useState } from 'react'
import { ErrorPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { BenchmarkResult } from '../types'

export function BenchmarkPage() {
  const [result, setResult] = useState<BenchmarkResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setRunning(true)
    setError('')
    try {
      setResult(await auditRepository.runBenchmark())
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Benchmark failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="page">
      <PageHeader
        eyebrow="Quality evidence"
        title="Fixed benchmark pack"
        description="Measure deterministic fixture correctness separately from runtime performance."
        action={<button className="button primary" onClick={run} disabled={running}>{running ? <span className="spinner small" /> : <Play size={16} />}{running ? 'Running 250 trials…' : 'Run benchmark'}</button>}
      />
      <div className="benchmark-explainer panel">
        <CheckCircle2 size={21} />
        <div><strong>Fixture correctness is not general legal accuracy.</strong><p>The adversarial fixture pack spans six isolated Singapore judgments and tests only rules the team can explain: supported, overgeneralised, mismatched, uncited, negative-registry, and out-of-scope claims.</p></div>
      </div>
      {error && <ErrorPanel message={error} />}
      {result ? (
        <>
          <div className="metric-grid benchmark-metrics">
            <div className="metric-card"><span>Fixture correctness</span><strong>{result.fixture_accuracy}%</strong><small>{result.correct_count} / {result.fixture_count} expected labels</small></div>
            <div className="metric-card"><span>P50 latency</span><strong>{result.p50_latency_ms} ms</strong><small>Median after corpus warm-up</small></div>
            <div className="metric-card"><span>P95 latency</span><strong>{result.p95_latency_ms} ms</strong><small>Target &lt; 1,500 ms</small></div>
            <div className="metric-card"><span>Performance runs</span><strong>{result.performance_runs}</strong><small>{result.error_count} errors</small></div>
            <div className="metric-card"><span>Official-source rate</span><strong>{result.source_provenance_rate}%</strong><small>Active snapshot authorities</small></div>
            <div className="metric-card"><span>Heading-match rate</span><strong>{result.citation_heading_match_rate}%</strong><small>Validated source headings</small></div>
            <div className="metric-card"><span>Annotation disagreement</span><strong>{result.annotation_disagreement_rate}%</strong><small>Forced to context review</small></div>
            <div className="metric-card"><span>Fabrication precision</span><strong>{result.fabrication_precision}%</strong><small>{result.fabrication_false_positive_count} false positives</small></div>
            <div className="metric-card"><span>Gold authority coverage</span><strong>{result.gold_authority_count}</strong><small>Isolated Singapore judgments</small></div>
          </div>
          <div className="panel coverage-panel">
            <p className="eyebrow">Module calibration</p><h2>Fixture accuracy by evaluated dimension</h2>
            <div className="coverage-table">{Object.entries(result.module_accuracy).map(([module, accuracy]) => <div key={module}><span>{module.replaceAll('_', ' ')}</span><strong>{accuracy == null ? 'Not yet gold-labelled' : `${accuracy}%`}</strong><small>Separate from general legal accuracy</small></div>)}</div>
          </div>
          <details className="panel source-paragraphs"><summary>View verdict confusion matrix</summary><pre>{JSON.stringify(result.confusion_matrix, null, 2)}</pre></details>
          <div className="panel benchmark-proof">
            <Gauge size={22} />
            <div><p className="eyebrow">Measured, not claimed</p><h2>Version-pinned evidence</h2><p>Engine {result.engine_version} · corpus {result.corpus_version}</p></div>
          </div>
          <div className="panel coverage-panel">
            <p className="eyebrow">Snapshot coverage</p><h2>Source coverage matrix</h2>
            {result.coverage.length ? (
              <div className="coverage-table">
                {result.coverage.map((cell) => <div key={[cell.court, cell.decision_year_band, cell.proposition, cell.outcome_direction].join('-')}><span>{cell.court} · {cell.decision_year_band}</span><strong>{cell.proposition.replaceAll('_', ' ')}</strong><small>{cell.outcome_direction.replaceAll('_', ' ')} · {cell.passage_count} passage{cell.passage_count === 1 ? '' : 's'}</small></div>)}
              </div>
            ) : <p className="metric-note">Run an official refresh to populate coverage; gold fixtures remain separate from the active snapshot.</p>}
          </div>
        </>
      ) : <div className="panel empty-state benchmark-empty">Run the fixed pack to generate current-machine evidence for the pitch.</div>}
    </section>
  )
}
