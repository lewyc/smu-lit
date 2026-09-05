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
}

export interface Authority {
  id: string
  citation: string
  citation_key: string
  case_name: string
  court: string
  decision_date: string
  official_url: string
  source_status: 'research_verified' | 'verification_required'
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
}

export interface AuditRepository {
  listAudits(filters?: AuditFilters): Promise<AuditSummary[]>
  getAudit(publicId: string): Promise<AuditDetail>
  submitAudit(input: AuditSubmission): Promise<AuditDetail>
  runBenchmark(): Promise<BenchmarkResult>
  listAuthorities(): Promise<Authority[]>
  loadDemoAnswer(): Promise<string>
}
