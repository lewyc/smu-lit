import { ArrowRight, Ban, CheckCircle2, Database, Scale, ServerCog, ShieldCheck } from 'lucide-react'
import { PageHeader } from '../components/Common'

const current = [
  'Synchronous local FastAPI engine',
  'Versioned four-decision pilot corpus',
  'Exact neutral-citation resolution',
  'TF-IDF passage navigation',
  'Optional Gemini claim structuring',
  'Supabase Auth, RLS, and durable audit records',
]

const future = [
  'Supabase Queues and stateless workers',
  'Curator-approved judgment ingestion',
  'Hybrid lexical and pgvector retrieval',
  'Organisation administration and audit exports',
  'Drift monitoring and larger legal benchmark sets',
]

export function AssurancePage() {
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
          <div><strong>Corpus</strong><span>Four selected decisions</span></div>
          <div><strong>Outcome</strong><span>Evaluation and lawyer handoff</span></div>
        </div>
        <p>Absence from this corpus is never treated as proof that an authority does not exist. “Likely fabricated” requires a separately recorded negative official-registry check.</p>
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
