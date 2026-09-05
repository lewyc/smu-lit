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
        <div><strong>Fixture correctness is not general legal accuracy.</strong><p>The seven hand-labelled fixtures test only rules the team can explain: supported, overgeneralised, mismatched, uncited, negative-registry, and out-of-scope claims.</p></div>
      </div>
      {error && <ErrorPanel message={error} />}
      {result ? (
        <>
          <div className="metric-grid benchmark-metrics">
            <div className="metric-card"><span>Fixture correctness</span><strong>{result.fixture_accuracy}%</strong><small>{result.correct_count} / {result.fixture_count} expected labels</small></div>
            <div className="metric-card"><span>P50 latency</span><strong>{result.p50_latency_ms} ms</strong><small>Median after corpus warm-up</small></div>
            <div className="metric-card"><span>P95 latency</span><strong>{result.p95_latency_ms} ms</strong><small>Target &lt; 1,500 ms</small></div>
            <div className="metric-card"><span>Performance runs</span><strong>{result.performance_runs}</strong><small>{result.error_count} errors</small></div>
          </div>
          <div className="panel benchmark-proof">
            <Gauge size={22} />
            <div><p className="eyebrow">Measured, not claimed</p><h2>Version-pinned evidence</h2><p>Engine {result.engine_version} · corpus {result.corpus_version}</p></div>
          </div>
        </>
      ) : <div className="panel empty-state benchmark-empty">Run the fixed pack to generate current-machine evidence for the pitch.</div>}
    </section>
  )
}
