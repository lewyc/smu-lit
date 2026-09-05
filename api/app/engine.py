from __future__ import annotations

import hashlib
import json
import re
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import Settings
from app.corpus import ActiveCorpusRepository, CorpusRepository, GoldFixtureCorpusRepository
from app.evaluation import context_profile, evaluate_framework, overall_score
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

ENGINE_VERSION = "proofmark-rules-0.3.0"
LOCAL_PARSER_VERSION = "local-claims.2"


class EvidenceMatcher:
    """Pre-computes lexical passage vectors once for the active immutable snapshot."""

    def __init__(self, corpus: CorpusRepository) -> None:
        self.corpus = corpus
        self._vectors: dict[str, tuple[TfidfVectorizer, object]] = {}
        for authority in corpus.list_authorities():
            if authority.passages:
                vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
                self._vectors[authority.citation_key] = (
                    vectorizer,
                    vectorizer.fit_transform([passage.text for passage in authority.passages]),
                )

    def rank(self, claim: ParsedClaim, authority) -> list[Evidence]:
        vector_data = self._vectors.get(authority.citation_key)
        if not vector_data:
            return []
        vectorizer, matrix = vector_data
        scores = cosine_similarity(vectorizer.transform([claim.text]), matrix).flatten()
        candidate_indexes = list(range(len(authority.passages)))
        if claim.pinpoint:
            candidate_indexes = [
                index for index, passage in enumerate(authority.passages) if self._label_covers(passage.paragraph_label, claim.pinpoint)
            ]
            if not candidate_indexes:
                return []
        evidence: list[Evidence] = []
        ordered_indexes = sorted(candidate_indexes, key=lambda index: scores[index], reverse=True)[:3]
        for index in ordered_indexes:
            passage = authority.passages[int(index)]
            supports = claim.proposition in passage.supported_propositions and passage.assessment_status in {"ai_supported", "gold_fixture"}
            relation = "supports" if supports else "unresolved"
            explanation = (
                "Exact official paragraph selected for this controlled proposition."
                if passage.source_provenance == "officially_sourced" and supports
                else "Gold-fixture passage explicitly supports this controlled proposition."
                if supports
                else "Lexically related passage; no proposition-supported evidence was retained."
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
                    officially_sourced=passage.source_provenance == "officially_sourced",
                    ai_supported=passage.assessment_status == "ai_supported",
                )
            )
        supporting = [item for item in evidence if item.relation == "supports"]
        return supporting[:3] if supporting else evidence[:1]

    @staticmethod
    def _label_covers(label: str, pinpoint: str) -> bool:
        def interval(value: str) -> tuple[int, int] | None:
            numbers = [int(item) for item in __import__("re").findall(r"\d+", value)]
            if not numbers:
                return None
            return numbers[0], numbers[-1]

        passage_range = interval(label)
        requested = interval(pinpoint)
        return bool(passage_range and requested and passage_range[0] <= requested[0] and passage_range[1] >= requested[1])


class VerdictEngine:
    def __init__(self, corpus: CorpusRepository, matcher: EvidenceMatcher) -> None:
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
            identity = re.match(r"(?P<year>\d{4})SG[A-Z()]+(?P<number>\d+)$", key)
            if identity:
                same_number = [
                    item
                    for item in self.corpus.list_authorities()
                    if item.citation_key.startswith(identity.group("year"))
                    and re.search(r"(\d+)$", item.citation_key)
                    and re.search(r"(\d+)$", item.citation_key).group(1) == identity.group("number")
                ]
                if same_number:
                    result = self._result(
                        claim,
                        "unsupported",
                        "The year and decision number match a stored authority, but the supplied court code does not.",
                        f"Check whether the intended citation was {same_number[0].citation}.",
                        [],
                    )
                    result.decision_rule_id = "PM-CIT-004"
                    result.severity = "serious"
                    return result
            negative = self.corpus.negative_check(key)
            if negative and negative.get("exists") is False:
                return self._result(
                    claim,
                    "likely_fabricated",
                    (
                        "No matching authority was found in the recorded official-registry check "
                        f"({negative['checked_at']}, {negative['checker']})."
                    ),
                    "Re-run the official Singapore Courts search and confirm the citation.",
                    [],
                )
            return self._result(
                claim,
                "unverified",
                "The citation cannot be resolved within the active immutable snapshot.",
                "Check the citation in an official or comprehensive legal database.",
                [],
            )

        if claim.case_name_mention and not self._case_name_consistent(claim.case_name_mention, authority.case_name):
            result = self._result(
                claim,
                "unsupported",
                "The case name stated in the answer does not match the canonical case name for this neutral citation.",
                f"Confirm the citation identity against {authority.case_name}.",
                [],
            )
            result.decision_rule_id = "PM-CIT-005"
            result.severity = "serious"
            return result

        evidence = self.matcher.rank(claim, authority)
        supporting = [item for item in evidence if item.relation == "supports"]
        if claim.pinpoint and not evidence:
            result = self._result(
                claim,
                "unsupported",
                f"{authority.citation} exists, but the supplied pinpoint {claim.pinpoint} is not present in the retained snapshot.",
                "Check the exact paragraph in the official judgment; ProofMark will not substitute another paragraph.",
                [],
            )
            result.pinpoint_status = "missing"
            result.decision_rule_id = "PM-CIT-006"
            result.severity = "serious"
            return result
        if not supporting:
            result = self._result(
                claim,
                "unsupported",
                (f"{authority.citation} resolves to an official judgment, but no retained paragraph supports '{claim.proposition}'."),
                "A proposition-linked paragraph from this or another authority is required.",
                evidence,
            )
            if claim.pinpoint:
                result.pinpoint_status = "wrong_proposition"
                result.decision_rule_id = "PM-CIT-007"
                result.severity = "serious"
            return result

        if claim.overgeneralisation_terms or claim.parser_confidence < 0.6:
            reason = (
                "The authority is relevant, but absolute wording "
                f"({', '.join(claim.overgeneralisation_terms)}) conflicts with its limitations."
                if claim.overgeneralisation_terms
                else "The authority is relevant, but the proposition mapping is ambiguous."
            )
            result = self._result(
                claim,
                "context_review",
                reason,
                "A lawyer must compare the clause, facts, and recorded limitations.",
                evidence,
            )
            result.pinpoint_status = "matched" if claim.pinpoint else "not_supplied"
            result.decision_rule_id = "PM-PROP-003"
            return result

        if any(item.passage.annotation_disagrees for item in supporting):
            result = self._result(
                claim,
                "context_review",
                "The official paragraph is AI-supported, but local and AI taxonomy labels disagree.",
                "A lawyer must resolve the proposition-label disagreement against the full judgment.",
                evidence,
            )
            result.pinpoint_status = "matched" if claim.pinpoint else "not_supplied"
            result.decision_rule_id = "PM-PROP-004"
            return result

        if authority.source_provenance != "gold_fixture":
            provenance_label = (
                "officially sourced and AI-supported"
                if authority.source_provenance == "officially_sourced"
                else "user supplied and not independently validated"
            )
            result = self._result(
                claim,
                "context_review",
                (
                    f"The citation and paragraph are {provenance_label}, "
                    "but automated semantic evidence is intentionally never presented as legal certainty."
                ),
                "Lawyer review is required to confirm why the authority matters on these facts.",
                evidence,
            )
            result.pinpoint_status = "matched" if claim.pinpoint else "not_supplied"
            result.decision_rule_id = "PM-TRUST-001"
            result.assessment_confidence = "medium"
            return result

        # The only pathway to verified is the separated, hand-labelled benchmark corpus.
        result = self._result(
            claim,
            "verified",
            f"{authority.citation} resolves exactly to a benchmark gold passage for '{claim.proposition}'.",
            None,
            evidence,
        )
        result.pinpoint_status = "matched" if claim.pinpoint else "not_supplied"
        result.decision_rule_id = "PM-GOLD-001"
        result.severity = "informational"
        result.assessment_confidence = "high"
        return result

    @staticmethod
    def _result(claim, verdict, rationale, missing, evidence) -> AuditedClaim:
        rule_ids = {
            "verified": "PM-GOLD-001",
            "context_review": "PM-PROP-001",
            "unsupported": "PM-CIT-003",
            "likely_fabricated": "PM-CIT-001",
            "unverified": "PM-CIT-002",
            "out_of_scope": "PM-SCOPE-001",
        }
        severities = {
            "verified": "informational",
            "context_review": "review",
            "unsupported": "serious",
            "likely_fabricated": "critical",
            "unverified": "informational",
            "out_of_scope": "informational",
        }
        return AuditedClaim(
            **claim.model_dump(),
            verdict=verdict,
            rationale=rationale,
            missing_evidence=missing,
            lawyer_review_required=verdict != "verified",
            evidence=evidence,
            decision_rule_id=rule_ids[verdict],
            severity=severities[verdict],
            assessment_confidence="high" if verdict in {"verified", "likely_fabricated"} else "medium" if evidence else "low",
        )

    @staticmethod
    def _case_name_consistent(mention: str, canonical: str) -> bool:
        ignored = {"pte", "ltd", "limited", "inc", "s", "the"}

        def sides(value: str) -> list[set[str]]:
            return [
                {token for token in re.findall(r"[a-z0-9]+", side.lower()) if token not in ignored}
                for side in re.split(r"\s+v\s+", value, maxsplit=1, flags=re.IGNORECASE)
            ]

        mentioned, official = sides(mention), sides(canonical)
        return len(mentioned) == 2 and len(official) == 2 and all(left & right for left, right in zip(mentioned, official, strict=True))


class HandoffBuilder:
    @staticmethod
    def build(claims: list[AuditedClaim]) -> HandoffBrief | None:
        flagged = [claim for claim in claims if claim.verdict != "verified"]
        if not flagged:
            return None
        authorities = sorted({evidence.authority_citation for claim in claims for evidence in claim.evidence})
        established = [f"Claim {claim.order}: {claim.rationale}" for claim in claims if claim.verdict == "verified"]
        unresolved = [f"Claim {claim.order}: {claim.missing_evidence or claim.rationale}" for claim in flagged]
        return HandoffBrief(
            issue="Review non-verified claims before the answer is relied on or sent.",
            established_points=established or ["No claim was fully verified in this runtime snapshot."],
            relevant_authorities=authorities or ["No resolved authority for the flagged claims."],
            unresolved_questions=unresolved,
            review_status="lawyer_review_required",
        )


class AuditEngine:
    def __init__(self, settings: Settings, corpus: CorpusRepository | None = None) -> None:
        self.settings = settings
        self.corpus = corpus or ActiveCorpusRepository()
        self.verdicts = VerdictEngine(self.corpus, EvidenceMatcher(self.corpus))

    def replace_corpus(self, corpus: CorpusRepository) -> None:
        """Install warmed immutable vectors after a successful refresh."""
        self.corpus = corpus
        self.verdicts = VerdictEngine(corpus, EvidenceMatcher(corpus))

    def request_cache_key(self, submission: AuditSubmission, currency_registry_version: str = "currency-none") -> str:
        """A cache lookup is safe only when every legal and parsing input matches."""
        return self._cache_key(
            submission,
            self._requested_parser_version(submission),
            currency_registry_version,
        )

    def cache_hit(self, audit: AuditDetail, currency_registry_version: str = "currency-none") -> AuditDetail:
        """Materialise a traceable result without treating a previous user input as authority."""
        metadata = self.corpus.get_metadata()
        return audit.model_copy(
            update={
                "public_id": uuid4(),
                "created_at": datetime.now(UTC),
                "processing_duration_ms": 0.0,
                "cache_status": "hit",
                "is_stale": False,
                "source_label": "Source-versioned cached audit result",
                "active_corpus_version": metadata.version,
                "sources_current_as_of": metadata.snapshot_created_at,
                "source_checked_at": datetime.now(UTC),
                "active_currency_registry_version": currency_registry_version,
            },
            deep=True,
        )

    def apply_freshness(self, audit: AuditDetail, currency_registry_version: str = "currency-none") -> AuditDetail:
        metadata = self.corpus.get_metadata()
        stale = audit.corpus_version != metadata.version or audit.currency_registry_version != currency_registry_version
        return audit.model_copy(
            update={
                "is_stale": stale,
                "active_corpus_version": metadata.version,
                "sources_current_as_of": metadata.snapshot_created_at,
                "active_currency_registry_version": currency_registry_version,
            },
            deep=True,
        )

    def _requested_parser_version(self, submission: AuditSubmission) -> str:
        if submission.parser_mode == "local" or not self.settings.gemini_api_key:
            return LOCAL_PARSER_VERSION
        return f"gemini-claims:{self.settings.claim_model}"

    def _cache_key(
        self,
        submission: AuditSubmission,
        parser_version: str,
        currency_registry_version: str,
    ) -> str:
        metadata = self.corpus.get_metadata()
        material = {
            "answer": submission.answer,
            "original_question": submission.original_question or "",
            "facts": submission.facts or "",
            "audit_mode": submission.audit_mode,
            "corpus_version": metadata.version,
            "engine_version": ENGINE_VERSION,
            "parser_version": parser_version,
            "taxonomy_version": TAXONOMY_VERSION,
            "currency_registry_version": currency_registry_version,
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def audit(
        self,
        submission: AuditSubmission,
        currency_statuses: dict[str, str] | None = None,
        currency_registry_version: str = "currency-none",
    ) -> AuditDetail:
        started = time.perf_counter()
        parse_result = parse_with_mode(submission.answer, submission.parser_mode, self.settings)
        claims = [self.verdicts.classify(claim) for claim in parse_result.claims]
        self._apply_currency_statuses(claims, currency_statuses or {})
        counts = Counter(claim.verdict for claim in claims)
        for verdict in ("verified", "context_review", "unsupported", "likely_fabricated", "unverified", "out_of_scope"):
            counts.setdefault(verdict, 0)
        in_scope = [claim for claim in claims if claim.verdict != "out_of_scope"]
        cited = [claim for claim in in_scope if claim.citation]
        resolved = [claim for claim in cited if claim.verdict not in {"likely_fabricated", "unverified"}]
        grounded = [claim for claim in in_scope if any(item.relation == "supports" for item in claim.evidence)]
        weighted = sum(1 if claim.verdict == "verified" else 0.5 if claim.verdict == "context_review" else 0 for claim in in_scope)
        profile = context_profile(submission.original_question, submission.facts) if submission.audit_mode == "full" else None
        flags, modules = evaluate_framework(claims, submission.audit_mode, profile)
        metadata = self.corpus.get_metadata()
        parser_version = f"gemini-claims:{self.settings.claim_model}" if parse_result.parser_used == "gemini" else LOCAL_PARSER_VERSION
        return AuditDetail(
            public_id=uuid4(),
            created_at=datetime.now(UTC),
            status="complete",
            parser_used=parse_result.parser_used,
            input_preview=submission.answer[:120],
            input_text=submission.answer,
            summary_counts=dict(counts),
            metrics=AuditMetrics(
                citation_integrity=self._percent(len(resolved), len(cited)),
                grounded_coverage=self._percent(len(grounded), len(in_scope)),
                contextual_support=round(100 * weighted / len(in_scope), 1) if in_scope else 0,
                citation_integrity_module=modules["citation"],
                propositional_accuracy_module=modules["proposition"],
                relevance_currency_module=modules["currency"],
                balance_completeness_module=modules["balance"],
                overall_score=overall_score(modules, submission.audit_mode),
            ),
            is_saved_demo=False,
            engine_version=ENGINE_VERSION,
            corpus_version=metadata.version,
            taxonomy_version=TAXONOMY_VERSION,
            parser_requested=submission.parser_mode,
            parser_version=parser_version,
            parser_fallback_reason=parse_result.fallback_reason,
            processing_duration_ms=round((time.perf_counter() - started) * 1000, 2),
            audit_cache_key=self._cache_key(submission, parser_version, currency_registry_version),
            cache_status="bypassed" if not submission.reuse_cache else "miss",
            source_checked_at=datetime.now(UTC),
            active_corpus_version=metadata.version,
            sources_current_as_of=metadata.snapshot_created_at,
            currency_registry_version=currency_registry_version,
            active_currency_registry_version=currency_registry_version,
            claims=claims,
            handoff=HandoffBuilder.build(claims),
            source_label="Live audit against warmed immutable snapshot",
            audit_mode=submission.audit_mode,
            original_question=submission.original_question,
            facts=submission.facts,
            context_profile=profile,
            flags=flags,
            evaluation_provenance={
                "decision_policy": "deterministic-rules-only",
                "verified_policy": "gold-benchmark-only",
                "case_map_schema_version": "proofmark-case-map-1.0",
                "currency_policy": "approved-treatment-edges-only",
                "currency_registry_version": currency_registry_version,
                "feedback_policy": "reviewed-revisions; no automatic retraining",
                "parser_model": self.settings.claim_model if parse_result.parser_used == "gemini" else "local",
            },
        )

    @staticmethod
    def _apply_currency_statuses(claims: list[AuditedClaim], statuses: dict[str, str]) -> None:
        for claim in claims:
            if claim.citation:
                status = statuses.get(normalise_citation(claim.citation))
                if status in {"current_reviewed", "negative_treatment"}:
                    claim.currency_status = status

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float:
        return round(100 * numerator / denominator, 1) if denominator else 0

    def benchmark(self, performance_runs: int = 250) -> BenchmarkResult:
        # Fixtures are intentionally the only route to the 'verified' class.
        gold_engine = AuditEngine(self.settings, GoldFixtureCorpusRepository())
        fixtures = [
            ("Employment restraints are prima facie unenforceable [2024] SGHC 29.", "verified", "proposition"),
            ("A legitimate interest is required [2007] SGCA 53.", "verified", "proposition"),
            ("All worldwide restraints are automatically void [2019] SGHC 96.", "context_review", "context"),
            ("Singapore-wide restraints are always unreasonable [2010] SGCA 3.", "context_review", "context"),
            ("Confidential information is always misused.", "unsupported", "citation"),
            ("A two-year rule exists [2099] SGCA 999.", "likely_fabricated", "citation"),
            ("The PDPA permits publication of personal data.", "out_of_scope", "scope"),
            ("The blue-pencil test does not permit a court to rewrite a restraint [2012] SGCA 39.", "verified", "proposition"),
            ("Non-solicitation and non-dealing restrictions require separate scrutiny [2024] SGHC 94.", "verified", "proposition"),
            ("A legitimate interest is required [2007] SGCA 53 at [999].", "unsupported", "citation"),
            ("A legitimate interest is required [2007] SGHC 53.", "unsupported", "citation"),
            ("A legitimate interest is required [2024] SGHC 29 at [18].", "unsupported", "proposition"),
        ]
        results = [gold_engine.audit(AuditSubmission(answer=text, parser_mode="local")).claims[0].verdict for text, _, _ in fixtures]
        correct = sum(int(actual == expected) for actual, (_, expected, _) in zip(results, fixtures, strict=True))
        confusion: dict[str, dict[str, int]] = {}
        for actual, (_, expected, _) in zip(results, fixtures, strict=True):
            confusion.setdefault(expected, {})[actual] = confusion.setdefault(expected, {}).get(actual, 0) + 1
        module_accuracy: dict[str, float | None] = {}
        for module in ("citation", "proposition", "context", "scope", "currency", "balance"):
            indexes = [index for index, fixture in enumerate(fixtures) if fixture[2] == module]
            module_accuracy[module] = (
                self._percent(len([index for index in indexes if results[index] == fixtures[index][1]]), len(indexes)) if indexes else None
            )
        predicted_fabricated = [index for index, actual in enumerate(results) if actual == "likely_fabricated"]
        true_fabricated = [index for index in predicted_fabricated if fixtures[index][1] == "likely_fabricated"]
        fabricated_false_positives = len(predicted_fabricated) - len(true_fabricated)
        latencies: list[float] = []
        errors = 0
        perf_input = AuditSubmission(answer=fixtures[0][0], parser_mode="local")
        for _ in range(performance_runs):
            try:
                latencies.append(gold_engine.audit(perf_input).processing_duration_ms)
            except Exception:
                errors += 1
        ordered = sorted(latencies)
        p95_index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered)) - 1))
        authorities = self.corpus.list_authorities()
        passages = [passage for authority in authorities for passage in authority.passages]
        officially_sourced = [item for item in authorities if item.source_provenance == "officially_sourced"]
        return BenchmarkResult(
            fixture_count=len(fixtures),
            correct_count=correct,
            fixture_accuracy=round(100 * correct / len(fixtures), 1),
            p50_latency_ms=round(statistics.median(ordered), 2) if ordered else 0,
            p95_latency_ms=ordered[p95_index] if ordered else 0,
            performance_runs=performance_runs,
            error_count=errors,
            engine_version=ENGINE_VERSION,
            corpus_version=self.corpus.get_metadata().version,
            source_provenance_rate=self._percent(len(officially_sourced), len(authorities)),
            citation_heading_match_rate=self._percent(
                len([item for item in officially_sourced if item.document_hash]), len(officially_sourced)
            ),
            annotation_disagreement_rate=self._percent(len([item for item in passages if item.annotation_disagrees]), len(passages)),
            coverage=self.corpus.get_metadata().coverage,
            gold_authority_count=len(GoldFixtureCorpusRepository().list_authorities()),
            module_accuracy=module_accuracy,
            fabrication_precision=self._percent(len(true_fabricated), len(predicted_fabricated)),
            fabrication_false_positive_count=fabricated_false_positives,
            confusion_matrix=confusion,
        )
