from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ParserMode = Literal["auto", "local", "gemini"]
ParserUsed = Literal["local", "gemini"]
AuditVerdict = Literal[
    "verified",
    "context_review",
    "unsupported",
    "likely_fabricated",
    "unverified",
    "out_of_scope",
]
EvidenceRelation = Literal["supports", "limits", "contradicts", "unresolved"]
SourceProvenance = Literal["officially_sourced", "gold_fixture", "rejected"]
AssessmentStatus = Literal["ai_supported", "gold_fixture", "unannotated", "rejected"]
OutcomeDirection = Literal[
    "supports_enforcement",
    "limits_enforcement",
    "mixed",
    "unknown",
]
RefreshStatus = Literal["queued", "running", "complete", "failed", "fallback"]


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
    passages: list[Passage]


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


class GeminiClaim(BaseModel):
    order: int
    text: str = Field(min_length=1)
    citation: str | None = None
    pinpoint: str | None = None
    proposition: str
    parser_confidence: float = Field(ge=0, le=1)
    overgeneralisation_terms: list[str] = Field(default_factory=list)


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


class AuditedClaim(ParsedClaim):
    verdict: AuditVerdict
    rationale: str
    missing_evidence: str | None = None
    lawyer_review_required: bool
    evidence: list[Evidence]


class AuditMetrics(BaseModel):
    citation_integrity: float = Field(ge=0, le=100)
    grounded_coverage: float = Field(ge=0, le=100)
    contextual_support: float = Field(ge=0, le=100)


class HandoffBrief(BaseModel):
    issue: str
    established_points: list[str]
    relevant_authorities: list[str]
    unresolved_questions: list[str]
    review_status: Literal["lawyer_review_required", "ready"]


class AuditSubmission(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)
    parser_mode: ParserMode = "auto"
    persist: bool = False


class AuditSummary(BaseModel):
    public_id: UUID
    created_at: datetime
    status: Literal["queued", "running", "complete", "failed"]
    parser_used: ParserUsed
    input_preview: str
    summary_counts: dict[str, int]
    metrics: AuditMetrics
    is_saved_demo: bool = False


class AuditDetail(AuditSummary):
    input_text: str
    engine_version: str
    corpus_version: str
    taxonomy_version: str
    parser_requested: ParserMode
    parser_fallback_reason: str | None
    processing_duration_ms: float
    claims: list[AuditedClaim]
    handoff: HandoffBrief | None
    source_label: str


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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    engine_version: str
    corpus_version: str
    data_mode: str
    supabase_configured: bool
    gemini_configured: bool
