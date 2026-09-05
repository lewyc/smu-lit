from app.config import Settings
from app.corpus import AUTHORITIES, DEMO_ANSWER
from app.engine import AuditEngine
from app.models import AuditSubmission
from app.parsers import LocalClaimParser, normalise_citation


def engine() -> AuditEngine:
    return AuditEngine(Settings(PROOFMARK_DATA_MODE="demo"))


def test_neutral_citation_normalisation_is_tolerant() -> None:
    assert normalise_citation("[2024]   sghc   29") == "2024SGHC29"
    assert normalise_citation("[2007] SGCA 53") == "2007SGCA53"


def test_local_parser_extracts_multiple_claims_and_pinpoints() -> None:
    claims = LocalClaimParser().parse(DEMO_ANSWER)
    assert len(claims) == 7
    assert claims[0].citation == "[2024] SGHC 29"
    assert claims[0].pinpoint == "[18]"
    assert claims[2].overgeneralisation_terms == ["automatically", "all non-competes"]


def test_all_seeded_authorities_resolve_exactly() -> None:
    corpus = engine().corpus
    assert all(corpus.resolve(authority.citation_key) for authority in AUTHORITIES)


def test_demo_answer_exercises_expected_verdicts() -> None:
    audit = engine().audit(AuditSubmission(answer=DEMO_ANSWER, parser_mode="local"))
    assert [claim.verdict for claim in audit.claims] == [
        "verified",
        "verified",
        "context_review",
        "context_review",
        "unsupported",
        "likely_fabricated",
        "out_of_scope",
    ]
    assert audit.handoff is not None
    assert audit.handoff.review_status == "lawyer_review_required"


def test_unknown_citation_is_not_called_fabricated_without_negative_check() -> None:
    audit = engine().audit(
        AuditSubmission(answer="A restraint is invalid [2025] SGHC 999.", parser_mode="local")
    )
    assert audit.claims[0].verdict == "unverified"


def test_gemini_absence_falls_back_without_changing_verdicts() -> None:
    audit = engine().audit(AuditSubmission(answer=DEMO_ANSWER, parser_mode="auto"))
    assert audit.parser_used == "local"
    assert "not configured" in (audit.parser_fallback_reason or "")
    assert audit.claims[0].verdict == "verified"


def test_benchmark_fixture_pack_is_exact() -> None:
    result = engine().benchmark(performance_runs=3)
    assert result.fixture_accuracy == 100
    assert result.error_count == 0
