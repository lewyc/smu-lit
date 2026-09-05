import { ArrowRight, Ban, CheckCircle2, Database, Scale, ServerCog, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { CorpusMetadata } from '../types'

const current = [
  'Synchronous local FastAPI engine',
  'Immutable official-judgment snapshot with cached fallback',
  'Exact neutral-citation resolution',
  'Exact-pincite and citation-identity checks',
  'Gemini Case Map drafts with exact paragraph anchors',
  'Lawyer editing, approval and immutable review history',
  'Full-mode context, modality, omission and balance checks',
  'Controlled practitioner feedback without self-training',
  'Supabase Auth, RLS, and durable audit records',
  'Source-versioned cache, stale-report warning, and linked re-audit',
  'Reviewer-only treatment, supersession, and amendment register',
]

const future = [
  'Supabase Queues and stateless workers',
  'PGMQ-backed stateless official-judgment refresh workers',
  'Hybrid lexical and pgvector retrieval',
  'Organisation administration and audit exports',
  'Drift monitoring and larger legal benchmark sets',
  'LicensedSourceConnector for SAL/SLR/LawNet where tenant licensing permits',
]

export function AssurancePage() {
  const [corpus, setCorpus] = useState<CorpusMetadata | null>(null)

  useEffect(() => {
    auditRepository.getCorpus().then(setCorpus).catch(() => undefined)
  }, [])

  return (
    <section className="page">
      <PageHeader
        eyebrow="Trust architecture"
        title="Assurance, boundaries, and scale"
        description="The system makes its evidence boundary visible and preserves a credible path beyond the hackathon."
      />
      <div className="assurance-hero">
        <div>
          <span><ShieldCheck size={24} /></span>
          <p className="eyebrow">Intended use</p>
          <h2>Help lawyers triage AI-generated legal answers—not replace legal judgment.</h2>
          <p>ProofMark turns opaque prose into inspectable claims, links each claim to stored evidence, and escalates uncertainty to a named human review step.</p>
        </div>
        <div className="principle-stack">
          <div><CheckCircle2 size={18} /><span><strong>Deterministic verdicts</strong>Models cannot mark their own work correct.</span></div>
          <div><Database size={18} /><span><strong>Versioned evidence</strong>Every audit records corpus and engine versions.</span></div>
          <div><Scale size={18} /><span><strong>Human accountability</strong>Non-verified claims create a lawyer handoff.</span></div>
        </div>
      </div>
      <div className="panel boundary-panel">
        <p className="eyebrow">Hard boundary</p>
        <div className="boundary-grid">
          <div><strong>Jurisdiction</strong><span>Singapore</span></div>
          <div><strong>Practice area</strong><span>Employment restraints of trade</span></div>
          <div><strong>Corpus</strong><span>{corpus ? corpus.authority_count + ' official judgments · ' + corpus.passage_count + ' passages' : 'Awaiting first official snapshot'}</span></div>
          <div><strong>Sources current as of</strong><span>{corpus?.snapshot_created_at ? new Date(corpus.snapshot_created_at).toLocaleString() : 'Awaiting first successful refresh'}</span></div>
          <div><strong>Outcome</strong><span>Evaluation and lawyer handoff</span></div>
        </div>
        <p>Absence from this corpus is never treated as proof that an authority does not exist. “Likely fabricated” requires a separately recorded negative official-registry check.</p>
      </div>
      <div className="corpus-notice">
        <strong>Licensed materials: future integration only.</strong> ProofMark does not scrape SAL, SLR, or LawNet. A future <code>LicensedSourceConnector</code> would ingest private tenant material only after the organisation confirms its licence and terms permit it.
      </div>
      <div className="panel boundary-panel">
        <p className="eyebrow">Who audits the auditor?</p>
        <h2>Three independent trust hierarchies</h2>
        <div className="boundary-grid">
          <div><strong>Pipeline</strong><span>Official refresh → Case Map draft → lawyer approval → deterministic audit</span></div>
          <div><strong>Decision authority</strong><span>Source checks → gold labels → approved maps → AI labels → lexical rank</span></div>
          <div><strong>Source hierarchy</strong><span>Official law → licensed metadata → recognised commentary → user supplied</span></div>
          <div><strong>Court hierarchy</strong><span>Forum-aware court tier, reviewed binding status, foreign law as persuasive only</span></div>
        </div>
        <p>Approval means fit for evaluation assistance, not guaranteed legal truth. Runtime Case Maps remain capped at context review; only the separated benchmark can display verified.</p>
      </div>
      <div className="architecture-grid">
        <div className="panel architecture-column">
          <p className="eyebrow">Built in this MVP</p>
          <h2>Presentation-ready vertical slice</h2>
          <ul>{current.map((item) => <li key={item}><CheckCircle2 size={16} />{item}</li>)}</ul>
        </div>
        <div className="architecture-arrow"><ArrowRight /></div>
        <div className="panel architecture-column future">
          <p className="eyebrow">Scale path</p>
          <h2>Production architecture</h2>
          <ul>{future.map((item) => <li key={item}><ServerCog size={16} />{item}</li>)}</ul>
        </div>
      </div>
      <div className="panel prohibited-panel">
        <div><Ban size={20} /><span><p className="eyebrow">Prohibited uses</p><h2>What ProofMark must not do</h2></span></div>
        <ul>
          <li>Provide legal advice or autonomously decide whether a restraint is enforceable.</li>
          <li>Call an unknown citation fabricated merely because it is outside the pilot corpus.</li>
          <li>Allow browser clients or a generative model to edit derived verdicts or evidence.</li>
          <li>Present benchmark fixture correctness as general legal accuracy.</li>
        </ul>
      </div>
    </section>
  )
}
