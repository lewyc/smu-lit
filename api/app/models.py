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


class Passage(BaseModel):
    id: str
    paragraph_label: str
    text: str
    supported_propositions: list[str]
    limitations: list[str] = Field(default_factory=list)


class Authority(BaseModel):
    id: str
    citation: str
    citation_key: str
    case_name: str
    court: str
    decision_date: date
    official_url: str
    source_status: Literal["research_verified", "verification_required"]
    passages: list[Passage]


class CorpusMetadata(BaseModel):
    version: str
    name: str
    jurisdiction: str
    scope_statement: str
    content_hash: str
    source_status: Literal["research_verified", "verification_required"]
    limitations: list[str]


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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    engine_version: str
    corpus_version: str
    data_mode: str
    supabase_configured: bool
    gemini_configured: bool
