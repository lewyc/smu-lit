from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ParserMode = Literal["auto", "local", "gemini"]
ParserUsed = Literal["local", "gemini"]
AuditMode = Literal["citation_only", "full"]
AuditVerdict = Literal[
    "verified",
    "context_review",
    "unsupported",
    "likely_fabricated",
    "unverified",
    "out_of_scope",
]
EvidenceRelation = Literal["supports", "limits", "contradicts", "unresolved"]
SourceProvenance = Literal["officially_sourced", "user_supplied", "gold_fixture", "rejected"]
AssessmentStatus = Literal["ai_supported", "gold_fixture", "unannotated", "rejected"]
OutcomeDirection = Literal[
    "supports_enforcement",
    "limits_enforcement",
    "mixed",
    "unknown",
]
RefreshStatus = Literal["queued", "running", "complete", "failed", "fallback"]
CacheStatus = Literal["hit", "miss", "bypassed"]
Modality = Literal["mandatory", "qualified", "permissive", "descriptive"]
AuthorityRole = Literal[
    "ratio_candidate",
    "holding",
    "obiter_candidate",
    "party_submission",
    "factual_finding",
    "procedural_history",
    "disposition",
]
ReviewStatus = Literal["draft", "approved", "rejected", "superseded"]
ValidationStatus = Literal["valid", "warning", "invalid"]
AssessmentConfidence = Literal["high", "medium", "low"]
Severity = Literal["critical", "serious", "review", "informational"]
CaseMapFieldTier = Literal["A", "B", "C"]
ExtractionMethod = Literal["deterministic", "rule_based", "model", "human", "hybrid"]
AssuranceQuestionKey = Literal["existence", "fidelity", "legal_significance", "completeness"]


class Passage(BaseModel):
    id: str
    paragraph_label: str
    text: str
    supported_propositions: list[str]
    limitations: list[str] = Field(default_factory=list)
    source_provenance: SourceProvenance = "gold_fixture"
    assessment_status: AssessmentStatus = "gold_fixture"
    annotation_confidence: float | None = Field(default=None, ge=0, le=1)
    annotation_model: str | None = None
    outcome_direction: OutcomeDirection = "unknown"
    annotation_disagrees: bool = False


class Authority(BaseModel):
    id: str
    citation: str
    citation_key: str
    case_name: str
    court: str
    decision_date: date
    official_url: str
    source_status: str = "gold_fixture"
    source_provenance: SourceProvenance = "gold_fixture"
    assessment_status: AssessmentStatus = "gold_fixture"
    source_host: str | None = None
    discovery_query: str | None = None
    retrieved_at: datetime | None = None
    document_hash: str | None = None
    extractor_version: str | None = None
    jurisdiction: str = "Singapore"
    court_code: str | None = None
    court_tier: int | None = None
    target_forum: str = "Singapore"
    precedential_status: Literal["binding", "persuasive", "secondary", "unknown"] = "unknown"
    hierarchy_reviewed: bool = False
    source_hierarchy_tier: int | None = None
    passages: list[Passage]

    @model_validator(mode="after")
    def derive_non_conclusive_hierarchy(self) -> Authority:
        match = re.search(r"\]\s*(SG[A-Z()]+)\s+\d+", self.citation, re.IGNORECASE)
        self.court_code = self.court_code or (match.group(1).upper() if match else None)
        self.court_tier = self.court_tier or {"SGCA": 5, "SGHC(A)": 4, "SGHC": 3, "SICC": 3}.get(self.court_code or "")
        if self.source_hierarchy_tier is None:
            self.source_hierarchy_tier = 1 if self.source_provenance in {"officially_sourced", "gold_fixture"} else 5
        return self


class CoverageCell(BaseModel):
    court: str
    decision_year_band: str
    proposition: str
    outcome_direction: OutcomeDirection
    passage_count: int


class CorpusMetadata(BaseModel):
    version: str
    name: str
    jurisdiction: str
    scope_statement: str
    content_hash: str
    source_status: str = "gold_fixture"
    limitations: list[str]
    active: bool = True
    snapshot_created_at: datetime | None = None
    authority_count: int = 0
    passage_count: int = 0
    profile_version: str | None = None
    is_cached: bool = False
    coverage: list[CoverageCell] = Field(default_factory=list)


class RefreshRun(BaseModel):
    public_id: UUID
    status: RefreshStatus
    source_connector: str = "SGCourtsConnector"
    profile_version: str
    requested_limit: int = Field(ge=1, le=25)
    accepted_documents: int = 0
    rejected_documents: int = 0
    accepted_passages: int = 0
    fallback_reason: str | None = None
    active_corpus_version: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None


class CorpusRefreshRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=25)


class ParsedClaim(BaseModel):
    order: int
    text: str = Field(min_length=1)
    citation: str | None = None
    pinpoint: str | None = None
    proposition: str
    parser_confidence: float = Field(ge=0, le=1)
    parser_used: ParserUsed
    overgeneralisation_terms: list[str] = Field(default_factory=list)
    case_name_mention: str | None = None
    citation_parse_status: Literal["valid", "malformed", "unresolved"] = "unresolved"
    modality: Modality = "descriptive"


class GeminiClaim(BaseModel):
    order: int
    text: str = Field(min_length=1)
    citation: str | None = None
    pinpoint: str | None = None
    proposition: str
    parser_confidence: float = Field(ge=0, le=1)
    overgeneralisation_terms: list[str] = Field(default_factory=list)
    case_name_mention: str | None = None
    modality: Modality = "descriptive"


class GeminiClaims(BaseModel):
    claims: list[GeminiClaim]


class Evidence(BaseModel):
    relation: EvidenceRelation
    score: float = Field(ge=0, le=1)
    explanation: str
    authority_citation: str
    case_name: str
    official_url: str
    passage: Passage
    officially_sourced: bool = False
    ai_supported: bool = False


class QuoteCheck(BaseModel):
    quote: str
    status: Literal["exact_match", "normalised_match", "not_found", "not_assessed"]
    paragraph_label: str | None = None
    method: Literal["exact", "whitespace_normalised", "none"] = "none"


class AuditedClaim(ParsedClaim):
    verdict: AuditVerdict
    rationale: str
    missing_evidence: str | None = None
    lawyer_review_required: bool
    evidence: list[Evidence]
    decision_rule_id: str = "PM-UNSPECIFIED"
    severity: Severity = "review"
    pinpoint_status: Literal["not_supplied", "matched", "missing", "wrong_proposition"] = "not_supplied"
    currency_status: Literal["current_reviewed", "negative_treatment", "not_verified"] = "not_verified"
    assessment_confidence: AssessmentConfidence = "low"
    case_map_version: str | None = None
    case_map_review_status: ReviewStatus | None = None
    pending_feedback: bool = False
    requires_authority: Literal["true", "false", "uncertain"] = "true"
    failure_level: Literal[1, 2, 3, 4, 5] | None = None
    quote_checks: list[QuoteCheck] = Field(default_factory=list)


class EvaluationFlag(BaseModel):
    code: Literal[
        "case_name_mismatch",
        "court_code_mismatch",
        "wrong_pinpoint",
        "party_submission_as_holding",
        "obiter_as_binding",
        "modality_overstatement",
        "material_factual_mismatch",
        "lower_authority_as_controlling",
        "secondary_as_law",
        "negative_treatment",
        "potential_omission",
        "potentially_one_sided",
        "missing_limiting_authority",
        "policy_factor_not_addressed",
        "landmark_candidate_not_engaged",
        "unsupported_legal_assertion",
        "unverified_quote",
    ]
    module: Literal["citation_integrity", "propositional_accuracy", "relevance_currency", "balance_completeness"]
    severity: Severity
    message: str
    claim_order: int | None = None
    lawyer_review_required: bool = True


class ModuleScore(BaseModel):
    score: float | None = Field(default=None, ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    assessed: bool
    reason_not_assessed: str | None = None


class ScoreGate(BaseModel):
    gate_id: str
    label: str
    status: Literal["passed", "triggered", "not_assessed"]
    effect: str
    basis_tier: Literal["A", "B", "human_verified_C", "none"]
    reason: str


class FailureFinding(BaseModel):
    level: Literal[1, 2, 3, 4, 5]
    name: str
    description: str
    claim_order: int | None = None
    decision_rule_id: str | None = None


class AssuranceQuestionResult(BaseModel):
    key: AssuranceQuestionKey
    question: str
    status: Literal["passed", "flagged", "partial", "not_assessed"]
    summary: str
    finding_count: int = 0
    failure_levels: list[int] = Field(default_factory=list)


class ClaimGraphNode(BaseModel):
    id: str
    node_type: Literal["claim", "authority"]
    label: str
    proposition: str | None = None
    resolution_status: Literal["resolved", "unresolved", "negative_registry_check", "not_applicable"] = "not_applicable"
    requires_authority: Literal["true", "false", "uncertain"] | None = None


class ClaimAuthorityEdge(BaseModel):
    claim_id: str
    authority_id: str
    relation: Literal["purports_to_support", "supports", "unresolved", "contradicts"]
    mapping_confidence: float = Field(ge=0, le=1)


class ClaimGraph(BaseModel):
    version: str
    nodes: list[ClaimGraphNode]
    edges: list[ClaimAuthorityEdge]


class CompletenessSearch(BaseModel):
    finding: str
    issue_tag: str
    corpus_scope: str
    landmark_set: list[str]
    landmark_set_version: str
    validation_status: str
    retrieval_configuration: str
    independence_attestation: str
    searched_and_not_found: list[str]
    confidence_band: str
    measured_accuracy: float | None = None


class ContextProfile(BaseModel):
    duration: str | None = None
    geographic_scope: str | None = None
    restricted_activities: list[str] = Field(default_factory=list)
    alleged_proprietary_interest: str | None = None
    confidential_information_access: bool | None = None
    customer_connection: bool | None = None
    employee_role: str | None = None
    procedural_stage: str | None = None
    relief_sought: str | None = None


class AuditMetrics(BaseModel):
    citation_integrity: float = Field(ge=0, le=100)
    grounded_coverage: float = Field(ge=0, le=100)
    contextual_support: float = Field(ge=0, le=100)
    citation_integrity_module: ModuleScore | None = None
    propositional_accuracy_module: ModuleScore | None = None
    relevance_currency_module: ModuleScore | None = None
    balance_completeness_module: ModuleScore | None = None
    overall_score: float | None = Field(default=None, ge=0, le=100)


class HandoffBrief(BaseModel):
    issue: str
    established_points: list[str]
    relevant_authorities: list[str]
    unresolved_questions: list[str]
    review_status: Literal["lawyer_review_required", "ready"]


class AuditSubmission(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)
    audit_mode: AuditMode = "citation_only"
    original_question: str | None = Field(default=None, max_length=5_000)
    facts: str | None = Field(default=None, max_length=10_000)
    parser_mode: ParserMode = "auto"
    persist: bool = False
    reuse_cache: bool = True

    @model_validator(mode="after")
    def require_question_for_full_mode(self) -> AuditSubmission:
        if self.audit_mode == "full" and not (self.original_question or "").strip():
            raise ValueError("Full audit mode requires the original legal question")
        return self


class AuditSummary(BaseModel):
    public_id: UUID
    created_at: datetime
    status: Literal["queued", "running", "complete", "failed"]
    parser_used: ParserUsed
    input_preview: str
    summary_counts: dict[str, int]
    metrics: AuditMetrics
    is_saved_demo: bool = False
    cache_status: CacheStatus = "miss"
    is_stale: bool = False


class AuditDetail(AuditSummary):
    input_text: str
    engine_version: str
    corpus_version: str
    taxonomy_version: str
    parser_requested: ParserMode
    parser_version: str = "local-claims.1"
    parser_fallback_reason: str | None
    processing_duration_ms: float
    audit_cache_key: str | None = None
    source_checked_at: datetime | None = None
    active_corpus_version: str | None = None
    sources_current_as_of: datetime | None = None
    currency_registry_version: str = "currency-none"
    active_currency_registry_version: str = "currency-none"
    re_audited_from_public_id: UUID | None = None
    claims: list[AuditedClaim]
    handoff: HandoffBrief | None
    source_label: str
    audit_mode: AuditMode = "citation_only"
    original_question: str | None = None
    facts: str | None = None
    context_profile: ContextProfile | None = None
    flags: list[EvaluationFlag] = Field(default_factory=list)
    evaluation_provenance: dict[str, object] = Field(default_factory=dict)
    assurance_policy_version: str = "legacy-unversioned"
    assurance_questions: list[AssuranceQuestionResult] = Field(default_factory=list)
    failure_findings: list[FailureFinding] = Field(default_factory=list)
    claim_graph: ClaimGraph | None = None
    score_gates: list[ScoreGate] = Field(default_factory=list)
    score_cap: float | None = Field(default=None, ge=0, le=100)
    completeness_searches: list[CompletenessSearch] = Field(default_factory=list)


class CaseMapFieldProvenance(BaseModel):
    field: str
    tier: CaseMapFieldTier
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    human_verified: bool = False
    verified_by: UUID | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    superseded_by: int | None = Field(default=None, ge=1)


class CaseMapAnnotation(BaseModel):
    id: str
    annotation_type: AuthorityRole
    proposition_code: str | None = None
    statement: str = Field(min_length=1)
    paragraph_labels: list[str] = Field(min_length=1)
    supporting_quote: str = Field(min_length=1, max_length=800)
    modality: Modality
    limitations: list[str] = Field(default_factory=list)
    applicability_factors: list[str] = Field(default_factory=list)
    model_confidence: float = Field(ge=0, le=1)
    validation_status: ValidationStatus = "valid"
    validation_messages: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "draft"
    provenance: CaseMapFieldProvenance | None = None


class CaseMapDraft(BaseModel):
    public_id: UUID
    citation: str
    citation_key: str
    case_name: str
    document_hash: str
    schema_version: str
    version: int = 1
    source_provenance: SourceProvenance
    source_url: str | None = None
    model: str
    prompt_version: str
    annotator_version: str
    extractor_version: str | None = None
    status: Literal["draft", "approved", "rejected", "superseded", "stale"] = "draft"
    annotations: list[CaseMapAnnotation]
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None


class CaseMapDetail(CaseMapDraft):
    source_paragraphs: list[Passage] = Field(default_factory=list)
    revision_history: list[dict[str, object]] = Field(default_factory=list)


class CaseMapGenerateRequest(BaseModel):
    citation: str


class AnnotationRevision(BaseModel):
    statement: str | None = None
    annotation_type: AuthorityRole | None = None
    proposition_code: str | None = None
    paragraph_labels: list[str] | None = None
    supporting_quote: str | None = None
    modality: Modality | None = None
    limitations: list[str] | None = None
    applicability_factors: list[str] | None = None


FeedbackCategory = Literal[
    "wrong_verdict",
    "wrong_proposition",
    "wrong_pinpoint",
    "incorrect_case_map_role",
    "missing_authority",
    "missing_context",
    "outdated_authority",
    "other",
]


class FeedbackSubmission(BaseModel):
    audit_public_id: UUID
    claim_order: int
    category: FeedbackCategory
    explanation: str = Field(min_length=3, max_length=5_000)
    proposed_citation: str | None = None
    proposed_paragraph: str | None = None
    proposed_correction: str | None = None


class PractitionerFeedback(FeedbackSubmission):
    public_id: UUID
    organisation_id: int | None = None
    submitted_by: UUID | None = None
    status: Literal["submitted", "under_review", "accepted", "rejected"] = "under_review"
    resolution_note: str | None = None
    resolved_by: UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class FeedbackResolution(BaseModel):
    decision: Literal["accepted", "rejected"]
    resolution_note: str = Field(min_length=3, max_length=5_000)


CurrencyRecordType = Literal["later_treatment", "statutory_amendment", "supersession"]
CurrencyTreatment = Literal["follows", "distinguishes", "limits", "overrules", "supersedes", "amends"]


class LegalCurrencyRecordSubmission(BaseModel):
    authority_citation: str = Field(min_length=8, max_length=100)
    record_type: CurrencyRecordType
    treatment: CurrencyTreatment
    source_citation: str | None = Field(default=None, max_length=100)
    statute_reference: str | None = Field(default=None, max_length=500)
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def require_reviewable_source(self) -> LegalCurrencyRecordSubmission:
        if self.record_type == "statutory_amendment":
            if not (self.statute_reference or "").strip():
                raise ValueError("A statutory amendment requires a statute reference")
            if self.treatment != "amends":
                raise ValueError("A statutory amendment must use the 'amends' treatment")
        elif not (self.source_citation or "").strip():
            raise ValueError("Later treatment and supersession require a source authority citation")
        return self


class LegalCurrencyRecord(LegalCurrencyRecordSubmission):
    review_status: Literal["approved"]
    reviewed_by: UUID | None = None
    reviewed_at: datetime


class BenchmarkResult(BaseModel):
    fixture_count: int
    correct_count: int
    fixture_accuracy: float
    p50_latency_ms: float
    p95_latency_ms: float
    performance_runs: int
    error_count: int
    engine_version: str
    corpus_version: str
    source_provenance_rate: float = 0
    citation_heading_match_rate: float = 0
    annotation_disagreement_rate: float = 0
    coverage: list[CoverageCell] = Field(default_factory=list)
    gold_authority_count: int = 0
    module_accuracy: dict[str, float | None] = Field(default_factory=dict)
    fabrication_precision: float = 0
    fabrication_false_positive_count: int = 0
    confusion_matrix: dict[str, dict[str, int]] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    engine_version: str
    corpus_version: str
    data_mode: str
    supabase_configured: bool
    gemini_configured: bool
