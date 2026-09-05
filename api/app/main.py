from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.corpus import DEMO_ANSWER, ActiveCorpusRepository
from app.engine import ENGINE_VERSION, AuditEngine
from app.models import (
    AuditDetail,
    AuditSubmission,
    AuditSummary,
    BenchmarkResult,
    CorpusRefreshRequest,
    HealthResponse,
    RefreshRun,
)
from app.refresh import CorpusRefreshService, RefreshManager
from app.repositories import (
    LocalAuditRepository,
    SupabaseAuditRepository,
    SupabaseCorpusRefreshRepository,
)
from app.taxonomy import PROPOSITIONS, TAXONOMY_VERSION

settings = get_settings()
active_corpus = ActiveCorpusRepository()
engine = AuditEngine(settings, active_corpus)
local_audits = LocalAuditRepository()
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
            run.fallback_reason = (
                "The local snapshot completed, but Supabase persistence failed "
                f"({type(exc).__name__})."
            )


refresh_manager = RefreshManager(
    CorpusRefreshService(active_corpus, settings),
    on_complete=_finish_refresh,
)

app = FastAPI(
    title="ProofMark API",
    version="0.1.0",
    description=("Pilot legal citation assurance API. Not legal advice and not a comprehensive case-law database."),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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


@app.get("/api/v1/authorities")
def authorities():
    return engine.corpus.list_authorities()


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
    audit = engine.audit(submission)
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
    return audit


@app.post("/api/v1/benchmarks/run", response_model=BenchmarkResult)
def run_benchmark():
    return engine.benchmark()


@app.get("/api/v1/assurance")
def assurance():
    return {
        "engine_version": ENGINE_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "corpus": engine.corpus.get_metadata(),
        "propositions": sorted(PROPOSITIONS),
        "decision_rules": {
            "truth_source": "controlled annotations and official-registry checks",
            "ranking": "TF-IDF ranks passages but never selects the verdict",
            "gemini_boundary": (
                "Gemini can atomise claims and select extracted paragraph labels during "
                "infrequent corpus refreshes; it cannot create passage text or provide verdicts"
            ),
        },
        "current_architecture": [
            "Local synchronous FastAPI audit engine",
            "Asynchronous, capped SG Courts snapshot refresh with cached fallback",
            "Read-only immutable snapshot with warmed TF-IDF vectors",
            "Optional Supabase Auth and tenant-isolated persistence",
        ],
        "production_architecture": [
            "Supabase Queues with stateless workers",
            "Stateless official-judgment refresh workers and monitoring",
            "pgvector alongside lexical retrieval",
            "Organisation administration and monitoring",
            "LicensedSourceConnector for SAL/SLR/LawNet only where tenant licensing permits",
        ],
        "prohibited_uses": [
            "Legal advice or autonomous legal decision-making",
            "Treating absence from the pilot corpus as proof a case does not exist",
            "Sending a flagged answer without lawyer review",
        ],
    }
