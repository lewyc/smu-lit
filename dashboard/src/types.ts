export type ParserMode = 'auto' | 'local' | 'gemini'

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
  source_provenance?: 'officially_sourced' | 'gold_fixture' | 'rejected'
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
  source_provenance?: 'officially_sourced' | 'gold_fixture' | 'rejected'
  assessment_status?: 'ai_supported' | 'gold_fixture' | 'unannotated' | 'rejected'
  source_host?: string | null
  discovery_query?: string | null
  retrieved_at?: string | null
  document_hash?: string | null
  extractor_version?: string | null
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
}

export interface AuditMetrics {
  citation_integrity: number
  grounded_coverage: number
  contextual_support: number
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
}

export interface AuditDetail extends AuditSummary {
  input_text: string
  engine_version: string
  corpus_version: string
  taxonomy_version: string
  parser_requested: ParserMode
  parser_fallback_reason: string | null
  processing_duration_ms: number
  claims: AuditedClaim[]
  handoff: {
    issue: string
    established_points: string[]
    relevant_authorities: string[]
    unresolved_questions: string[]
    review_status: 'lawyer_review_required' | 'ready'
  } | null
  source_label: string
}

export interface AuditSubmission {
  answer: string
  parser_mode: ParserMode
  persist: boolean
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
  runBenchmark(): Promise<BenchmarkResult>
  listAuthorities(): Promise<Authority[]>
  getCorpus(): Promise<CorpusMetadata>
  startCorpusRefresh(): Promise<RefreshRun>
  getLatestCorpusRefresh(): Promise<RefreshRun | null>
  loadDemoAnswer(): Promise<string>
}
