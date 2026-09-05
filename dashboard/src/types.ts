export type ParserMode = 'auto' | 'local' | 'gemini'
export type AuditMode = 'citation_only' | 'full'

export type AuditVerdict =
  | 'verified'
  | 'context_review'
  | 'unsupported'
  | 'likely_fabricated'
  | 'unverified'
  | 'out_of_scope'

export type EvidenceRelation = 'supports' | 'limits' | 'contradicts' | 'unresolved'

export interface Passage {
  id: string
  paragraph_label: string
  text: string
  supported_propositions: string[]
  limitations: string[]
  source_provenance?: 'officially_sourced' | 'user_supplied' | 'gold_fixture' | 'rejected'
  assessment_status?: 'ai_supported' | 'gold_fixture' | 'unannotated' | 'rejected'
  annotation_confidence?: number | null
  annotation_model?: string | null
  outcome_direction?: 'supports_enforcement' | 'limits_enforcement' | 'mixed' | 'unknown'
  annotation_disagrees?: boolean
}

export interface Authority {
  id: string
  citation: string
  citation_key: string
  case_name: string
  court: string
  decision_date: string
  official_url: string
  source_status: string
  source_provenance?: 'officially_sourced' | 'user_supplied' | 'gold_fixture' | 'rejected'
  assessment_status?: 'ai_supported' | 'gold_fixture' | 'unannotated' | 'rejected'
  source_host?: string | null
  discovery_query?: string | null
  retrieved_at?: string | null
  document_hash?: string | null
  extractor_version?: string | null
  jurisdiction?: string
  court_code?: string | null
  court_tier?: number | null
  target_forum?: string
  precedential_status?: 'binding' | 'persuasive' | 'secondary' | 'unknown'
  hierarchy_reviewed?: boolean
  source_hierarchy_tier?: number | null
  passages: Passage[]
}

export interface Evidence {
  relation: EvidenceRelation
  score: number
  explanation: string
  authority_citation: string
  case_name: string
  official_url: string
  passage: Passage
  officially_sourced: boolean
  ai_supported: boolean
}

export interface AuditedClaim {
  order: number
  text: string
  citation: string | null
  pinpoint: string | null
  proposition: string
  parser_confidence: number
  parser_used: 'local' | 'gemini'
  overgeneralisation_terms: string[]
  verdict: AuditVerdict
  rationale: string
  missing_evidence: string | null
  lawyer_review_required: boolean
  evidence: Evidence[]
  case_name_mention?: string | null
  citation_parse_status?: 'valid' | 'malformed' | 'unresolved'
  modality?: 'mandatory' | 'qualified' | 'permissive' | 'descriptive'
  decision_rule_id?: string
  severity?: 'critical' | 'serious' | 'review' | 'informational'
  pinpoint_status?: 'not_supplied' | 'matched' | 'missing' | 'wrong_proposition'
  currency_status?: 'current_reviewed' | 'negative_treatment' | 'not_verified'
  assessment_confidence?: 'high' | 'medium' | 'low'
  case_map_version?: string | null
  case_map_review_status?: 'draft' | 'approved' | 'rejected' | 'superseded' | null
  pending_feedback?: boolean
  requires_authority?: 'true' | 'false' | 'uncertain'
  failure_level?: 1 | 2 | 3 | 4 | 5 | null
  quote_checks?: QuoteCheck[]
}

export interface QuoteCheck {
  quote: string
  status: 'exact_match' | 'normalised_match' | 'not_found' | 'not_assessed'
  paragraph_label: string | null
  method: 'exact' | 'whitespace_normalised' | 'none'
}

export interface ModuleScore {
  score: number | null
  weight: number
  assessed: boolean
  reason_not_assessed: string | null
}

export interface AuditMetrics {
  citation_integrity: number
  grounded_coverage: number
  contextual_support: number
  citation_integrity_module?: ModuleScore | null
  propositional_accuracy_module?: ModuleScore | null
  relevance_currency_module?: ModuleScore | null
  balance_completeness_module?: ModuleScore | null
  overall_score?: number | null
}

export interface AuditSummary {
  public_id: string
  created_at: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  parser_used: 'local' | 'gemini'
  input_preview: string
  summary_counts: Record<AuditVerdict, number>
  metrics: AuditMetrics
  is_saved_demo: boolean
  cache_status?: 'hit' | 'miss' | 'bypassed'
  is_stale?: boolean
}

export interface AuditDetail extends AuditSummary {
  input_text: string
  engine_version: string
  corpus_version: string
  taxonomy_version: string
  parser_requested: ParserMode
  parser_version?: string
  parser_fallback_reason: string | null
  processing_duration_ms: number
  audit_cache_key?: string | null
  source_checked_at?: string | null
  active_corpus_version?: string | null
  sources_current_as_of?: string | null
  currency_registry_version?: string
  active_currency_registry_version?: string
  re_audited_from_public_id?: string | null
  claims: AuditedClaim[]
  handoff: {
    issue: string
    established_points: string[]
    relevant_authorities: string[]
    unresolved_questions: string[]
    review_status: 'lawyer_review_required' | 'ready'
  } | null
  source_label: string
  audit_mode?: AuditMode
  original_question?: string | null
  facts?: string | null
  context_profile?: Record<string, unknown> | null
  flags?: EvaluationFlag[]
  evaluation_provenance?: Record<string, unknown>
  assurance_policy_version?: string
  assurance_questions?: AssuranceQuestionResult[]
  failure_findings?: FailureFinding[]
  claim_graph?: ClaimGraph | null
  score_gates?: ScoreGate[]
  score_cap?: number | null
  completeness_searches?: CompletenessSearch[]
}

export interface AssuranceQuestionResult {
  key: 'existence' | 'fidelity' | 'legal_significance' | 'completeness'
  question: string
  status: 'passed' | 'flagged' | 'partial' | 'not_assessed'
  summary: string
  finding_count: number
  failure_levels: number[]
}

export interface FailureFinding {
  level: 1 | 2 | 3 | 4 | 5
  name: string
  description: string
  claim_order: number | null
  decision_rule_id: string | null
}

export interface ClaimGraphNode {
  id: string
  node_type: 'claim' | 'authority'
  label: string
  proposition: string | null
  resolution_status: 'resolved' | 'unresolved' | 'negative_registry_check' | 'not_applicable'
  requires_authority: 'true' | 'false' | 'uncertain' | null
}

export interface ClaimAuthorityEdge {
  claim_id: string
  authority_id: string
  relation: 'purports_to_support' | 'supports' | 'unresolved' | 'contradicts'
  mapping_confidence: number
}

export interface ClaimGraph {
  version: string
  nodes: ClaimGraphNode[]
  edges: ClaimAuthorityEdge[]
}

export interface ScoreGate {
  gate_id: string
  label: string
  status: 'passed' | 'triggered' | 'not_assessed'
  effect: string
  basis_tier: 'A' | 'B' | 'human_verified_C' | 'none'
  reason: string
}

export interface CompletenessSearch {
  finding: string
  issue_tag: string
  corpus_scope: string
  landmark_set: string[]
  landmark_set_version: string
  validation_status: string
  retrieval_configuration: string
  independence_attestation: string
  searched_and_not_found: string[]
  confidence_band: string
  measured_accuracy: number | null
}

export interface EvaluationFlag {
  code: string
  module: string
  severity: string
  message: string
  claim_order: number | null
  lawyer_review_required: boolean
}

export interface AuditSubmission {
  answer: string
  audit_mode: AuditMode
  original_question?: string
  facts?: string
  parser_mode: ParserMode
  persist: boolean
  reuse_cache?: boolean
}

export interface CaseMapAnnotation {
  id: string
  annotation_type: 'ratio_candidate' | 'holding' | 'obiter_candidate' | 'party_submission' | 'factual_finding' | 'procedural_history' | 'disposition'
  proposition_code: string | null
  statement: string
  paragraph_labels: string[]
  supporting_quote: string
  modality: 'mandatory' | 'qualified' | 'permissive' | 'descriptive'
  limitations: string[]
  applicability_factors: string[]
  model_confidence: number
  validation_status: 'valid' | 'warning' | 'invalid'
  validation_messages: string[]
  review_status: 'draft' | 'approved' | 'rejected' | 'superseded'
  provenance?: {
    field: string
    tier: 'A' | 'B' | 'C'
    extraction_method: 'deterministic' | 'rule_based' | 'model' | 'human' | 'hybrid'
    confidence: number
    human_verified: boolean
    verified_by: string | null
    supporting_evidence: string[]
    version: number
    superseded_by: number | null
  } | null
}

export interface CaseMapDetail {
  public_id: string
  citation: string
  citation_key: string
  case_name: string
  document_hash: string
  schema_version: string
  version: number
  source_provenance: 'officially_sourced' | 'user_supplied' | 'gold_fixture' | 'rejected'
  source_url: string | null
  model: string
  prompt_version: string
  annotator_version: string
  extractor_version: string | null
  status: 'draft' | 'approved' | 'rejected' | 'superseded' | 'stale'
  annotations: CaseMapAnnotation[]
  validation_errors: string[]
  source_paragraphs: Passage[]
  revision_history: Record<string, unknown>[]
  created_at: string
  updated_at: string
}

export interface FeedbackSubmission {
  audit_public_id: string
  claim_order: number
  category: 'wrong_verdict' | 'wrong_proposition' | 'wrong_pinpoint' | 'incorrect_case_map_role' | 'missing_authority' | 'missing_context' | 'outdated_authority' | 'other'
  explanation: string
}

export interface PractitionerFeedback extends FeedbackSubmission {
  public_id: string
  status: 'submitted' | 'under_review' | 'accepted' | 'rejected'
  created_at: string
  resolution_note: string | null
}

export interface AuditFilters {
  verdict?: AuditVerdict
  search?: string
}

export interface BenchmarkResult {
  fixture_count: number
  correct_count: number
  fixture_accuracy: number
  p50_latency_ms: number
  p95_latency_ms: number
  performance_runs: number
  error_count: number
  engine_version: string
  corpus_version: string
  source_provenance_rate: number
  citation_heading_match_rate: number
  annotation_disagreement_rate: number
  coverage: CoverageCell[]
  gold_authority_count: number
  module_accuracy: Record<string, number | null>
  fabrication_precision: number
  fabrication_false_positive_count: number
  confusion_matrix: Record<string, Record<string, number>>
}

export interface CoverageCell {
  court: string
  decision_year_band: string
  proposition: string
  outcome_direction: 'supports_enforcement' | 'limits_enforcement' | 'mixed' | 'unknown'
  passage_count: number
}

export interface CorpusMetadata {
  version: string
  name: string
  jurisdiction: string
  scope_statement: string
  content_hash: string
  source_status: string
  limitations: string[]
  active: boolean
  snapshot_created_at: string | null
  authority_count: number
  passage_count: number
  profile_version: string | null
  is_cached: boolean
  coverage: CoverageCell[]
}

export interface RefreshRun {
  public_id: string
  status: 'queued' | 'running' | 'complete' | 'failed' | 'fallback'
  source_connector: string
  profile_version: string
  requested_limit: number
  accepted_documents: number
  rejected_documents: number
  accepted_passages: number
  fallback_reason: string | null
  active_corpus_version: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface AuditRepository {
  listAudits(filters?: AuditFilters): Promise<AuditSummary[]>
  getAudit(publicId: string): Promise<AuditDetail>
  submitAudit(input: AuditSubmission): Promise<AuditDetail>
  reAudit(publicId: string): Promise<AuditDetail>
  deleteAudit(publicId: string): Promise<void>
  runBenchmark(): Promise<BenchmarkResult>
  listAuthorities(): Promise<Authority[]>
  listCaseMapSources(): Promise<Authority[]>
  getCorpus(): Promise<CorpusMetadata>
  startCorpusRefresh(): Promise<RefreshRun>
  getLatestCorpusRefresh(): Promise<RefreshRun | null>
  loadDemoAnswer(): Promise<string>
  listCaseMaps(): Promise<CaseMapDetail[]>
  generateCaseMap(citation: string): Promise<CaseMapDetail>
  importCaseMapPdf(file: File, expectedCitation: string, officialUrl?: string): Promise<CaseMapDetail>
  reviseCaseMap(publicId: string, annotationId: string, revision: Partial<CaseMapAnnotation>): Promise<CaseMapDetail>
  approveCaseMap(publicId: string): Promise<CaseMapDetail>
  submitFeedback(input: FeedbackSubmission): Promise<PractitionerFeedback>
  listFeedback(): Promise<PractitionerFeedback[]>
}
