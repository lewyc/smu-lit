from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.assurance import assurance_policy
from app.case_maps import CaseMapService, LocalFeedbackRepository
from app.config import get_settings
from app.corpus import DEMO_ANSWER, ActiveCorpusRepository, GoldFixtureCorpusRepository
from app.engine import ENGINE_VERSION, AuditEngine
from app.evaluation import hierarchies
from app.models import (
    AnnotationRevision,
    AuditDetail,
    AuditSubmission,
    AuditSummary,
    BenchmarkResult,
    CaseMapDetail,
    CaseMapGenerateRequest,
    CorpusRefreshRequest,
    FeedbackResolution,
    FeedbackSubmission,
    HealthResponse,
    LegalCurrencyRecord,
    LegalCurrencyRecordSubmission,
    PractitionerFeedback,
    RefreshRun,
)
from app.parsers import normalise_citation
from app.refresh import CorpusRefreshService, RefreshManager
from app.repositories import (
    LocalAuditRepository,
    SupabaseAuditRepository,
    SupabaseCorpusRefreshRepository,
    SupabaseGovernanceRepository,
)
from app.scheduler import RefreshScheduler
from app.taxonomy import PROPOSITIONS, TAXONOMY_VERSION

settings = get_settings()
active_corpus = ActiveCorpusRepository()
engine = AuditEngine(settings, active_corpus)
local_audits = LocalAuditRepository()


class CaseMapSourceCorpus:
    """Uses gold only for preprocessing demos until an official snapshot exists."""

    def __init__(self, runtime: ActiveCorpusRepository) -> None:
        self.runtime = runtime
        self.gold = GoldFixtureCorpusRepository()

    def _source(self):
        return self.runtime if self.runtime.list_authorities() else self.gold

    def list_authorities(self):
        return self._source().list_authorities()

    def resolve(self, citation_key: str):
        return self._source().resolve(citation_key)

    def get_metadata(self):
        return self._source().get_metadata()

    def negative_check(self, citation_key: str):
        return self._source().negative_check(citation_key)


case_map_sources = CaseMapSourceCorpus(active_corpus)
case_maps = CaseMapService(settings, case_map_sources)
feedback_repository = LocalFeedbackRepository()
local_currency_records: list[LegalCurrencyRecord] = []
refresh_repositories: dict[UUID, SupabaseCorpusRefreshRepository] = {}


def _finish_refresh(run: RefreshRun) -> None:
    if run.status == "complete":
        engine.replace_corpus(active_corpus)
    repository = refresh_repositories.get(run.public_id)
    if repository:
        try:
            repository.finish(run, active_corpus if run.status == "complete" else None)
        except Exception as exc:
            run.status = "fallback"
            run.fallback_reason = f"The local snapshot completed, but Supabase persistence failed ({type(exc).__name__})."


refresh_manager = RefreshManager(
    CorpusRefreshService(active_corpus, settings),
    on_complete=_finish_refresh,
)
refresh_scheduler = RefreshScheduler(refresh_manager, settings.refresh_interval_hours)


@asynccontextmanager
async def lifespan(_: FastAPI):
    refresh_scheduler.start()
    try:
        yield
    finally:
        refresh_scheduler.stop()


app = FastAPI(
    title="ProofMark API",
    version="0.1.0",
    description=("Pilot legal citation assurance API. Not legal advice and not a comprehensive case-law database."),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def _token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def _repository(token: str | None):
    if settings.data_mode != "supabase":
        return local_audits
    if not token:
        raise HTTPException(status_code=401, detail="Supabase sign-in required")
    try:
        return SupabaseAuditRepository(settings, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _refresh_repository(token: str | None) -> SupabaseCorpusRefreshRepository | None:
    if settings.data_mode != "supabase":
        return None
    if not token:
        raise HTTPException(status_code=401, detail="Supabase sign-in required")
    try:
        return SupabaseCorpusRefreshRepository(settings, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _member(token: str | None, reviewer_required: bool = False) -> SupabaseAuditRepository | None:
    if settings.data_mode != "supabase":
        return None
    repository = _repository(token)
    if reviewer_required and repository.role not in {"reviewer", "owner"}:
        raise HTTPException(status_code=403, detail="Reviewer or owner role required")
    return repository


def _governance(token: str | None, reviewer_required: bool = False) -> SupabaseGovernanceRepository | None:
    if settings.data_mode != "supabase":
        return None
    if not token:
        raise HTTPException(status_code=401, detail="Supabase sign-in required")
    try:
        repository = SupabaseGovernanceRepository(settings, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if reviewer_required and repository.role not in {"reviewer", "owner"}:
        raise HTTPException(status_code=403, detail="Reviewer or owner role required")
    return repository


def _currency_context(token: str | None) -> tuple[dict[str, str], str]:
    if settings.data_mode == "supabase":
        if not token:
            return {}, "currency-none"
        return _governance(token).currency_context()  # type: ignore[union-attr]

    statuses: dict[str, str] = {}
    material: list[dict[str, str]] = []
    for record in local_currency_records:
        citation_key = normalise_citation(record.authority_citation)
        status = "negative_treatment" if record.treatment in {"limits", "overrules", "supersedes", "amends"} else "current_reviewed"
        if statuses.get(citation_key) != "negative_treatment":
            statuses[citation_key] = status
        material.append(
            {
                "citation_key": citation_key,
                "treatment": record.treatment,
                "reviewed_at": record.reviewed_at.isoformat(),
            }
        )
    if not material:
        return statuses, "currency-none"
    version = (
        "currency-"
        + hashlib.sha256(
            json.dumps(sorted(material, key=lambda item: json.dumps(item, sort_keys=True)), sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
    )
    return statuses, version


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        engine_version=ENGINE_VERSION,
        corpus_version=engine.corpus.get_metadata().version,
        data_mode=settings.data_mode,
        supabase_configured=bool(settings.supabase_url and settings.supabase_secret_key),
        gemini_configured=bool(settings.gemini_api_key),
    )


@app.get("/api/v1/corpora")
def corpora():
    return [engine.corpus.get_metadata()]


@app.get("/api/v1/corpora/freshness")
def corpus_freshness():
    metadata = engine.corpus.get_metadata()
    return {
        "active_corpus_version": metadata.version,
        "sources_current_as_of": metadata.snapshot_created_at,
        "is_cached_snapshot": metadata.is_cached,
        "scheduler": refresh_scheduler.status(),
        "latest_refresh": refresh_manager.latest(),
    }


@app.get("/api/v1/authorities")
def authorities():
    return engine.corpus.list_authorities()


@app.get("/api/v1/case-map-sources")
def case_map_source_authorities():
    return case_map_sources.list_authorities()


@app.post("/api/v1/corpora/refresh", response_model=RefreshRun, status_code=202)
def refresh_corpus(
    request: CorpusRefreshRequest,
    token: Annotated[str | None, Depends(_token)],
) -> RefreshRun:
    # Browser clients never write database rows. Demo mode uses a local executor;
    # Supabase mode is persisted by the server-side service in a production deployment.
    repository = _refresh_repository(token)
    run = refresh_manager.start(request.limit)
    if repository:
        repository.create(run)
        refresh_repositories[run.public_id] = repository
    return run


@app.get("/api/v1/corpora/refreshes/latest", response_model=RefreshRun | None)
def latest_refresh(token: Annotated[str | None, Depends(_token)]) -> RefreshRun | None:
    repository = _refresh_repository(token)
    if repository:
        return repository.latest()
    return refresh_manager.latest()


@app.get("/api/v1/demo-answer")
def demo_answer():
    return {"answer": DEMO_ANSWER}


@app.post("/api/v1/audits", response_model=AuditDetail)
def submit_audit(
    submission: AuditSubmission,
    token: Annotated[str | None, Depends(_token)],
) -> AuditDetail:
    currency_statuses, currency_registry_version = _currency_context(token)
    repository = None
    if settings.data_mode == "demo":
        repository = local_audits
    elif submission.persist or (submission.reuse_cache and token):
        repository = _repository(token)
    if submission.reuse_cache and repository:
        cached = repository.find_cached(engine.request_cache_key(submission, currency_registry_version))
        if cached:
            result = engine.cache_hit(cached, currency_registry_version)
            return repository.save(result) if (settings.data_mode == "demo" or submission.persist) else result
    audit = engine.audit(submission, currency_statuses, currency_registry_version)
    if settings.data_mode == "demo":
        return local_audits.save(audit)
    if submission.persist:
        return _repository(token).save(audit)
    return audit


@app.get("/api/v1/audits", response_model=list[AuditSummary])
def list_audits(token: Annotated[str | None, Depends(_token)]):
    return _repository(token).list()


@app.get("/api/v1/audits/{public_id}", response_model=AuditDetail)
def get_audit(public_id: UUID, token: Annotated[str | None, Depends(_token)]):
    audit = _repository(token).get(public_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    _, currency_registry_version = _currency_context(token)
    return engine.apply_freshness(audit, currency_registry_version)


@app.post("/api/v1/audits/{public_id}/re-audit", response_model=AuditDetail)
def re_audit(public_id: UUID, token: Annotated[str | None, Depends(_token)]) -> AuditDetail:
    repository = _repository(token)
    prior = repository.get(public_id)
    if not prior:
        raise HTTPException(status_code=404, detail="Audit not found")
    if not prior.input_text:
        raise HTTPException(
            status_code=410,
            detail="This audit's retained input has expired and cannot be re-audited.",
        )
    submission = AuditSubmission(
        answer=prior.input_text,
        # Historical full audits remain readable, but a re-audit is a new Tier 0
        # citation-only result rather than an implicit Tier 1/2 evaluation.
        audit_mode="citation_only",
        parser_mode=prior.parser_requested,
        persist=settings.data_mode == "supabase",
        reuse_cache=False,
    )
    currency_statuses, currency_registry_version = _currency_context(token)
    audit = engine.audit(submission, currency_statuses, currency_registry_version)
    audit.re_audited_from_public_id = public_id
    if prior.audit_mode == "full":
        audit.evaluation_provenance["legacy_context_not_reapplied"] = True
    return repository.save(audit)


@app.delete("/api/v1/audits/{public_id}", status_code=204)
def delete_audit(public_id: UUID, token: Annotated[str | None, Depends(_token)]):
    if not _repository(token).delete(public_id):
        raise HTTPException(status_code=404, detail="Audit not found or cannot be deleted by this user")


@app.post("/api/v1/case-maps/generate", response_model=CaseMapDetail)
def generate_case_map(request: CaseMapGenerateRequest, token: Annotated[str | None, Depends(_token)]):
    governance = _governance(token)
    try:
        result = case_maps.generate(request.citation)
        return governance.persist_case_map(result) if governance else result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/case-maps/import-pdf", response_model=CaseMapDetail)
async def import_case_map_pdf(
    file: Annotated[UploadFile, File()],
    expected_citation: Annotated[str, Form()],
    official_url: Annotated[str | None, Form()] = None,
    token: Annotated[str | None, Depends(_token)] = None,
):
    governance = _governance(token)
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")
    content = await file.read(15 * 1024 * 1024 + 1)
    try:
        result = case_maps.import_pdf(content, file.filename or "uploaded-judgment.pdf", expected_citation, official_url)
        return governance.persist_case_map(result) if governance else result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/case-maps", response_model=list[CaseMapDetail])
def list_case_maps(token: Annotated[str | None, Depends(_token)]):
    _member(token)
    return case_maps.list()


@app.get("/api/v1/case-maps/{public_id}", response_model=CaseMapDetail)
def get_case_map(public_id: UUID, token: Annotated[str | None, Depends(_token)]):
    _member(token)
    item = case_maps.get(public_id)
    if not item:
        raise HTTPException(status_code=404, detail="Case Map not found")
    return item


@app.patch("/api/v1/case-maps/{public_id}/annotations/{annotation_id}", response_model=CaseMapDetail)
def revise_case_map(
    public_id: UUID,
    annotation_id: str,
    revision: AnnotationRevision,
    token: Annotated[str | None, Depends(_token)],
):
    governance = _governance(token, reviewer_required=True)
    try:
        result = case_maps.revise(public_id, annotation_id, revision)
        return governance.persist_case_map(result) if governance else result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/case-maps/{public_id}/approve", response_model=CaseMapDetail)
def approve_case_map(public_id: UUID, token: Annotated[str | None, Depends(_token)]):
    member = _governance(token, reviewer_required=True)
    try:
        result = case_maps.approve(public_id, UUID(member.user_id) if member else None)
        return member.persist_case_map(result) if member else result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/feedback", response_model=PractitionerFeedback)
def submit_feedback(submission: FeedbackSubmission, token: Annotated[str | None, Depends(_token)]):
    governance = _governance(token)
    audit = _repository(token).get(submission.audit_public_id)
    if not audit or not any(claim.order == submission.claim_order for claim in audit.claims):
        raise HTTPException(status_code=404, detail="Audit claim not found")
    for claim in audit.claims:
        if claim.order == submission.claim_order:
            claim.pending_feedback = True
    if settings.data_mode == "demo":
        local_audits.save(audit)
    feedback = feedback_repository.submit(submission)
    return governance.persist_feedback(feedback) if governance else feedback


@app.get("/api/v1/feedback", response_model=list[PractitionerFeedback])
def list_feedback(token: Annotated[str | None, Depends(_token)]):
    _member(token)
    return feedback_repository.list()


@app.post("/api/v1/feedback/{public_id}/resolve", response_model=PractitionerFeedback)
def resolve_feedback(
    public_id: UUID,
    resolution: FeedbackResolution,
    token: Annotated[str | None, Depends(_token)],
):
    member = _governance(token, reviewer_required=True)
    try:
        result = feedback_repository.resolve(public_id, resolution, UUID(member.user_id) if member else None)
        return member.persist_feedback_resolution(result) if member else result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/currency-records", response_model=LegalCurrencyRecord, status_code=201)
def record_legal_currency(
    submission: LegalCurrencyRecordSubmission,
    token: Annotated[str | None, Depends(_token)],
) -> LegalCurrencyRecord:
    """Stores human-approved treatment data; generative output can never create it."""
    governance = _governance(token, reviewer_required=True)
    if governance:
        try:
            return governance.persist_legal_currency_record(submission)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    record = LegalCurrencyRecord(
        **submission.model_dump(),
        review_status="approved",
        reviewed_at=datetime.now(UTC),
    )
    local_currency_records.append(record)
    return record


@app.get("/api/v1/currency-records", response_model=list[LegalCurrencyRecord])
def list_legal_currency_records(token: Annotated[str | None, Depends(_token)]):
    _member(token)
    if settings.data_mode != "demo":
        raise HTTPException(
            status_code=501,
            detail="Use the reviewer register in the connected deployment to list persistent currency records.",
        )
    return list(local_currency_records)


@app.get("/api/v1/hierarchies")
def get_hierarchies():
    return hierarchies()


@app.post("/api/v1/benchmarks/run", response_model=BenchmarkResult)
def run_benchmark():
    return engine.benchmark()


@app.get("/api/v1/assurance")
def assurance():
    policy = assurance_policy()
    return {
        "engine_version": ENGINE_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "corpus": engine.corpus.get_metadata(),
        "propositions": sorted(PROPOSITIONS),
        "assurance_policy": policy,
        "decision_rules": {
            "truth_source": "controlled annotations and official-registry checks",
            "ranking": "TF-IDF ranks passages but never selects the verdict",
            "gemini_boundary": (
                "Gemini can atomise claims and propose exact paragraph-anchored Case Map labels; "
                "it cannot create passage text, decide currency or binding status, or provide verdicts"
            ),
            "verified_boundary": (
                "Only isolated gold benchmark annotations can produce verified; approved runtime maps remain context_review."
            ),
            "feedback_boundary": (
                "Feedback opens review and may create a superseding annotation version; "
                "it never changes scores or retrains Gemini automatically."
            ),
        },
        "current_architecture": [
            "Local synchronous FastAPI audit engine",
            "Asynchronous, capped SG Courts snapshot refresh with cached fallback",
            "In-process 24-hour refresh scheduler (MVP); no refresh occurs during an audit",
            "Read-only immutable snapshot with warmed TF-IDF vectors",
            "Optional Supabase Auth and tenant-isolated persistence",
            "Versioned Case Map drafts, deterministic quote validation and lawyer approval",
            "Citation-only audits; historical full-mode records remain readable",
            "Practitioner feedback review queue without automatic self-learning",
            "Five-level failure taxonomy and four-question assurance spine",
            "Tier A/B/C Case Map provenance envelopes",
            "Gate-before-weight scoring and a versioned claim graph",
            "One bounded landmark-set comparison with negative-finding disclosure",
        ],
        "production_architecture": [
            "Durable scheduled refresh jobs with source-freshness monitoring",
            "Supabase Queues with stateless workers",
            "Stateless official-judgment refresh workers and monitoring",
            "pgvector alongside lexical retrieval",
            "Organisation administration and monitoring",
            "LicensedSourceConnector for SAL/SLR/LawNet only where tenant licensing permits",
            "Independent counter-authority retrieval and calibrated Legal NLI",
            "Corpus-scale treatment graph, bias studies, and statistically valid calibration",
        ],
        "prohibited_uses": [
            "Legal advice or autonomous legal decision-making",
            "Treating absence from the pilot corpus as proof a case does not exist",
            "Sending a flagged answer without lawyer review",
        ],
        "retention": {
            "default_days": settings.audit_retention_days,
            "policy": (
                "Raw answers are retained only for the configured period to enable reproducibility and "
                "re-audit. An audit owner may delete a saved audit earlier. Expired records are excluded "
                "from retrieval and cache reuse; a production maintenance worker physically purges them."
            ),
        },
        "cache_policy": (
            "Prior user answers are never legal authority or model-training data. Cache reuse requires "
            "an exact key across the answer, question, facts, audit mode, corpus, engine, parser and taxonomy versions."
        ),
    }
