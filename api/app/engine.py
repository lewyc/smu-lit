from __future__ import annotations

import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import Settings
from app.corpus import CORPUS_VERSION, LocalCorpusRepository
from app.models import (
    AuditDetail,
    AuditedClaim,
    AuditMetrics,
    AuditSubmission,
    BenchmarkResult,
    Evidence,
    HandoffBrief,
    ParsedClaim,
)
from app.parsers import normalise_citation, parse_with_mode
from app.taxonomy import TAXONOMY_VERSION

ENGINE_VERSION = "proofmark-rules-0.1.0"


class EvidenceMatcher:
    def __init__(self, corpus: LocalCorpusRepository) -> None:
        self.corpus = corpus

    def rank(self, claim: ParsedClaim, authority) -> list[Evidence]:
        passages = authority.passages
        if not passages:
            return []
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([passage.text for passage in passages] + [claim.text])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
        evidence: list[Evidence] = []
        for index in scores.argsort()[::-1][:3]:
            passage = passages[int(index)]
            supports = claim.proposition in passage.supported_propositions
            relation = "supports" if supports else "unresolved"
            explanation = (
                "Stored annotation explicitly supports this proposition."
                if supports
                else "Lexically related passage; no supporting proposition annotation."
            )
            evidence.append(
                Evidence(
                    relation=relation,
                    score=round(float(scores[index]), 4),
                    explanation=explanation,
                    authority_citation=authority.citation,
                    case_name=authority.case_name,
                    official_url=authority.official_url,
                    passage=passage,
                )
            )
        supporting = [item for item in evidence if item.relation == "supports"]
        return supporting[:3] if supporting else evidence[:1]


class VerdictEngine:
    def __init__(self, corpus: LocalCorpusRepository, matcher: EvidenceMatcher) -> None:
        self.corpus = corpus
        self.matcher = matcher

    def classify(self, claim: ParsedClaim) -> AuditedClaim:
        if claim.proposition == "outside_corpus_scope":
            return self._result(
                claim,
                "out_of_scope",
                "The claim is outside the declared Singapore employment restraint-of-trade corpus.",
                "Use the appropriate legal corpus and subject-matter reviewer.",
                [],
            )
        if not claim.citation:
            return self._result(
                claim,
                "unsupported",
                "This legal conclusion has no nearby authority.",
                "A relevant authority and proposition-linked passage are required.",
                [],
            )

        key = normalise_citation(claim.citation)
        authority = self.corpus.resolve(key)
        if authority is None:
            negative = self.corpus.negative_check(key)
            if negative and negative.get("exists") is False:
                rationale = (
                    "No matching authority was found in the recorded official-registry check "
                    f"({negative['checked_at']}, {negative['checker']})."
                )
                return self._result(
                    claim,
                    "likely_fabricated",
                    rationale,
                    "Re-run the official Singapore Courts search and confirm the citation.",
                    [],
                )
            return self._result(
                claim,
                "unverified",
                "The citation cannot be resolved within the declared pilot corpus.",
                "Check the citation in an official or comprehensive legal database.",
                [],
            )

        evidence = self.matcher.rank(claim, authority)
        supporting = [item for item in evidence if item.relation == "supports"]
        if not supporting:
            return self._result(
                claim,
                "unsupported",
                (
                    f"{authority.citation} is real, but its stored annotations do not support "
                    f"the proposition '{claim.proposition}'."
                ),
                "A proposition-linked passage from this or another authority is required.",
                evidence,
            )

        if claim.overgeneralisation_terms or claim.parser_confidence < 0.6:
            if claim.overgeneralisation_terms:
                reason = (
                    "The authority is relevant, but absolute wording "
                    f"({', '.join(claim.overgeneralisation_terms)}) conflicts with its limitations."
                )
            else:
                reason = "The authority is relevant, but the proposition mapping is ambiguous."
            return self._result(
                claim,
                "context_review",
                reason,
                "A lawyer must compare the clause, facts, and recorded limitations.",
                evidence,
            )

        return self._result(
            claim,
            "verified",
            (
                f"{authority.citation} resolves exactly and a stored passage is explicitly "
                f"annotated for '{claim.proposition}'."
            ),
            None,
            evidence,
        )

    @staticmethod
    def _result(claim, verdict, rationale, missing, evidence) -> AuditedClaim:
        return AuditedClaim(
            **claim.model_dump(),
            verdict=verdict,
            rationale=rationale,
            missing_evidence=missing,
            lawyer_review_required=verdict != "verified",
            evidence=evidence,
        )


class HandoffBuilder:
    @staticmethod
    def build(claims: list[AuditedClaim]) -> HandoffBrief | None:
        flagged = [claim for claim in claims if claim.verdict != "verified"]
        if not flagged:
            return None
        authorities = sorted(
            {
                evidence.authority_citation
                for claim in claims
                for evidence in claim.evidence
            }
        )
        established = [
            f"Claim {claim.order}: {claim.rationale}"
            for claim in claims
            if claim.verdict == "verified"
        ]
        unresolved = [
            f"Claim {claim.order}: {claim.missing_evidence or claim.rationale}"
            for claim in flagged
        ]
        return HandoffBrief(
            issue="Review non-verified claims before the answer is relied on or sent.",
            established_points=established or ["No claim was fully verified in the pilot corpus."],
            relevant_authorities=authorities or ["No resolved authority for the flagged claims."],
            unresolved_questions=unresolved,
            review_status="lawyer_review_required",
        )


class AuditEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.corpus = LocalCorpusRepository()
        self.verdicts = VerdictEngine(self.corpus, EvidenceMatcher(self.corpus))

    def audit(self, submission: AuditSubmission) -> AuditDetail:
        started = time.perf_counter()
        parse_result = parse_with_mode(submission.answer, submission.parser_mode, self.settings)
        claims = [self.verdicts.classify(claim) for claim in parse_result.claims]
        counts = Counter(claim.verdict for claim in claims)
        for verdict in (
            "verified",
            "context_review",
            "unsupported",
            "likely_fabricated",
            "unverified",
            "out_of_scope",
        ):
            counts.setdefault(verdict, 0)
        in_scope = [claim for claim in claims if claim.verdict != "out_of_scope"]
        cited = [claim for claim in in_scope if claim.citation]
        resolved = [
            claim
            for claim in cited
            if claim.verdict not in {"likely_fabricated", "unverified"}
        ]
        grounded = [
            claim for claim in in_scope if any(item.relation == "supports" for item in claim.evidence)
        ]
        weighted = sum(
            1 if claim.verdict == "verified" else 0.5 if claim.verdict == "context_review" else 0
            for claim in in_scope
        )
        metrics = AuditMetrics(
            citation_integrity=self._percent(len(resolved), len(cited)),
            grounded_coverage=self._percent(len(grounded), len(in_scope)),
            contextual_support=round(100 * weighted / len(in_scope), 1) if in_scope else 0,
        )
        duration = round((time.perf_counter() - started) * 1000, 2)
        return AuditDetail(
            public_id=uuid4(),
            created_at=datetime.now(UTC),
            status="complete",
            parser_used=parse_result.parser_used,
            input_preview=submission.answer[:120],
            input_text=submission.answer,
            summary_counts=dict(counts),
            metrics=metrics,
            is_saved_demo=False,
            engine_version=ENGINE_VERSION,
            corpus_version=CORPUS_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            parser_requested=submission.parser_mode,
            parser_fallback_reason=parse_result.fallback_reason,
            processing_duration_ms=duration,
            claims=claims,
            handoff=HandoffBuilder.build(claims),
            source_label="Live local audit engine",
        )

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float:
        return round(100 * numerator / denominator, 1) if denominator else 0

    def benchmark(self, performance_runs: int = 250) -> BenchmarkResult:
        fixtures = [
            ("Employment restraints are prima facie unenforceable [2024] SGHC 29.", "verified"),
            ("A legitimate interest is required [2007] SGCA 53.", "verified"),
            ("All worldwide restraints are automatically void [2019] SGHC 96.", "context_review"),
            ("Singapore-wide restraints are always unreasonable [2010] SGCA 3.", "context_review"),
            ("Confidential information is always misused.", "unsupported"),
            ("A two-year rule exists [2099] SGCA 999.", "likely_fabricated"),
            ("The PDPA permits publication of personal data.", "out_of_scope"),
        ]
        correct = 0
        for text, expected in fixtures:
            detail = self.audit(AuditSubmission(answer=text, parser_mode="local"))
            correct += int(detail.claims[0].verdict == expected)
        latencies: list[float] = []
        errors = 0
        perf_input = AuditSubmission(answer=fixtures[0][0], parser_mode="local")
        for _ in range(performance_runs):
            try:
                latencies.append(self.audit(perf_input).processing_duration_ms)
            except Exception:
                errors += 1
        ordered = sorted(latencies)
        p95_index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered)) - 1))
        return BenchmarkResult(
            fixture_count=len(fixtures),
            correct_count=correct,
            fixture_accuracy=round(100 * correct / len(fixtures), 1),
            p50_latency_ms=round(statistics.median(ordered), 2) if ordered else 0,
            p95_latency_ms=ordered[p95_index] if ordered else 0,
            performance_runs=performance_runs,
            error_count=errors,
            engine_version=ENGINE_VERSION,
            corpus_version=CORPUS_VERSION,
        )
