import type { AuditDetail, AuditedClaim, AuditVerdict } from '../types'

export const DEMO_ANSWER = `Singapore employment restraints are prima facie unenforceable unless the employer justifies them [2024] SGHC 29 at [18].
An employer must identify a legitimate proprietary interest before reasonableness is considered [2007] SGCA 53 at [70].
All worldwide one-year non-competes are automatically void under [2019] SGHC 96 at [82].
CLAAS proves that every Singapore-wide restraint is always unreasonable [2010] SGCA 3 at [59].
Any former employee who contacts a customer necessarily misuses confidential information.
Man Financial (S) Pte Ltd v Wong Bark Chuan David [2024] SGHC 29 at [59] requires a legitimate proprietary interest.
Separately, the PDPA always permits employers to publish former employees' personal data.`

const verdicts: AuditVerdict[] = [
  'unverified',
  'unverified',
  'context_review',
  'context_review',
  'unsupported',
  'unsupported',
  'out_of_scope',
]

const texts = DEMO_ANSWER.split('\n')

function claim(order: number): AuditedClaim {
  const verdict = verdicts[order - 1]
  const citations = [
    '[2024] SGHC 29',
    '[2007] SGCA 53',
    '[2019] SGHC 96',
    '[2010] SGCA 3',
    null,
    '[2024] SGHC 29',
    null,
  ]
  const propositions = [
    'prima_facie_unenforceable',
    'legitimate_proprietary_interest',
    'geographic_scope',
    'geographic_scope',
    'confidential_information',
    'legitimate_proprietary_interest',
    'outside_corpus_scope',
  ]
  const rationales: Record<AuditVerdict, string> = {
    verified: 'The citation resolves and a stored passage is explicitly annotated for this proposition.',
    context_review: 'The authority is relevant, but the absolute wording conflicts with fact-sensitive limitations.',
    unsupported: 'This legal conclusion has no nearby authority.',
    likely_fabricated: 'No authority was found in the recorded official-registry check for this adversarial fixture.',
    unverified: 'The citation cannot be resolved within the pilot corpus.',
    out_of_scope: 'The claim is outside the declared employment restraint-of-trade corpus.',
  }
  const citation = citations[order - 1]
  // A disconnected fallback must never invent or paraphrase judgment text.
  // Start the API to obtain source-hashed, paragraph-anchored evidence.
  const evidence: AuditedClaim['evidence'] = []
  return {
    order,
    text: texts[order - 1],
    citation,
    pinpoint: order <= 4 ? ['[18]', '[70]', '[82]', '[59]'][order - 1] : null,
    proposition: propositions[order - 1],
    parser_confidence: 0.88,
    parser_used: 'local',
    overgeneralisation_terms: order === 3 ? ['automatically', 'all non-competes'] : order === 4 ? ['always'] : [],
    verdict,
    rationale: rationales[verdict],
    missing_evidence: verdict === 'verified' ? null : 'Lawyer review and/or further authority is required.',
    lawyer_review_required: verdict !== 'verified',
    evidence,
    requires_authority: verdict === 'out_of_scope' ? 'uncertain' : 'true',
    failure_level: verdict === 'likely_fabricated' ? 1 : verdict === 'unsupported' ? 3 : verdict === 'context_review' ? 4 : null,
    quote_checks: [],
  }
}

const demoClaims = texts.map((_, index) => claim(index + 1))

export const savedDemoResult: AuditDetail = {
  public_id: '00000000-0000-4000-8000-000000000001',
  created_at: '2026-09-05T00:00:00+08:00',
  status: 'complete',
  parser_used: 'local',
  input_preview: DEMO_ANSWER.slice(0, 120),
  summary_counts: {
    verified: 0,
    context_review: 2,
    unsupported: 2,
    likely_fabricated: 0,
    unverified: 2,
    out_of_scope: 1,
  },
  metrics: {
    citation_integrity: 80,
    grounded_coverage: 66.7,
    contextual_support: 50,
    citation_integrity_module: { score: 80, weight: 30, assessed: true, reason_not_assessed: null },
    propositional_accuracy_module: { score: 66.7, weight: 35, assessed: true, reason_not_assessed: null },
    relevance_currency_module: { score: null, weight: 20, assessed: false, reason_not_assessed: 'No lawyer-approved currency record is available.' },
    balance_completeness_module: { score: 50, weight: 15, assessed: true, reason_not_assessed: null },
    overall_score: null,
  },
  is_saved_demo: true,
  input_text: DEMO_ANSWER,
  engine_version: 'proofmark-rules-0.1.0',
  corpus_version: 'sg-employment-restraints-2026.09-pilot.1',
  taxonomy_version: 'sg-rot-taxonomy-1.0',
  parser_requested: 'local',
  parser_fallback_reason: 'Saved result shown because the local API was unavailable.',
  processing_duration_ms: 8.4,
  claims: demoClaims,
  handoff: {
    issue: 'Review non-verified claims before the answer is relied on or sent.',
    established_points: ['No judgment passage is bundled into the disconnected fallback.'],
    relevant_authorities: ['[2007] SGCA 53', '[2010] SGCA 3', '[2019] SGHC 96', '[2024] SGHC 29'],
    unresolved_questions: ['Start the API and rerun against source-hashed corpus evidence.', 'Review the real case-name/citation mismatch.'],
    review_status: 'lawyer_review_required',
  },
  source_label: 'Saved demonstration result',
  audit_mode: 'full',
  original_question: 'Can an employer enforce a one-year worldwide restraint against a former employee?',
  facts: 'The employee had customer connections and access to confidential information.',
  assurance_policy_version: 'proofmark-veritas-policy-1.0',
  assurance_questions: [
    { key: 'existence', question: 'Does the authority exist and is it correctly identified?', status: 'flagged', summary: 'One real citation is paired with the wrong real case name.', finding_count: 1, failure_levels: [2] },
    { key: 'fidelity', question: 'Does the cited material support the proposition?', status: 'flagged', summary: 'One uncited legal assertion lacks proposition-linked support.', finding_count: 1, failure_levels: [3] },
    { key: 'legal_significance', question: 'Does it mean what the AI says, with the legal weight claimed?', status: 'flagged', summary: 'Two claims use absolute language for fact-sensitive authorities.', finding_count: 2, failure_levels: [4] },
    { key: 'completeness', question: 'What material issue or landmark candidate did the AI miss?', status: 'flagged', summary: 'The bounded issue checklist produced lawyer-review prompts.', finding_count: 1, failure_levels: [5] },
  ],
  score_gates: [
    { gate_id: 'citation_integrity', label: 'Citation integrity gate', status: 'triggered', effect: 'Composite capped by policy', basis_tier: 'A', reason: 'A real citation is paired with a different real case name.' },
    { gate_id: 'unsupported_assertion', label: 'Unsupported assertion gate', status: 'triggered', effect: 'Composite capped at 49', basis_tier: 'A', reason: 'An extracted legal assertion requiring authority had no citation.' },
    { gate_id: 'currency', label: 'Currency gate', status: 'not_assessed', effect: 'No cap applied', basis_tier: 'none', reason: 'No lawyer-approved currency record was available; the system abstained.' },
    { gate_id: 'direct_contradiction', label: 'Direct contradiction gate', status: 'not_assessed', effect: 'No cap applied', basis_tier: 'none', reason: 'Legal NLI is not implemented as a hard gate.' },
  ],
  score_cap: 49,
  claim_graph: {
    version: 'proofmark-claim-graph-1.0',
    nodes: [
      ...demoClaims.map((item) => ({ id: 'claim:' + item.order, node_type: 'claim' as const, label: item.text, proposition: item.proposition, resolution_status: 'not_applicable' as const, requires_authority: item.requires_authority ?? 'true' })),
      ...demoClaims.filter((item) => item.citation).map((item) => ({ id: 'authority:' + item.citation!.replace(/[^A-Za-z0-9]/g, ''), node_type: 'authority' as const, label: item.citation!, proposition: null, resolution_status: item.verdict === 'likely_fabricated' ? 'negative_registry_check' as const : 'resolved' as const, requires_authority: null })),
    ],
    edges: demoClaims.filter((item) => item.citation).map((item) => ({
      claim_id: 'claim:' + item.order,
      authority_id: 'authority:' + item.citation!.replace(/[^A-Za-z0-9]/g, ''),
      relation: item.evidence.length ? 'supports' as const : item.verdict === 'likely_fabricated' ? 'unresolved' as const : 'purports_to_support' as const,
      mapping_confidence: item.parser_confidence,
    })),
  },
  completeness_searches: [{
    finding: 'Pilot landmark set engaged',
    issue_tag: 'legitimate_proprietary_interest',
    corpus_scope: 'Six-case Singapore employment-restraint benchmark',
    landmark_set: ['[2007] SGCA 53', '[2024] SGHC 29'],
    landmark_set_version: 'sg-rot-lpi-landmarks-pilot-1',
    validation_status: 'benchmark-curated; legal-team sign-off required',
    retrieval_configuration: 'Exact citation-set comparison; no semantic counter-authority retrieval.',
    independence_attestation: 'Static VERITAS reference-set comparison only; independent counter-authority retrieval is not implemented.',
    searched_and_not_found: [],
    confidence_band: 'unvalidated pilot',
    measured_accuracy: null,
  }],
}
