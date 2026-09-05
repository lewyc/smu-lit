from __future__ import annotations

from functools import lru_cache

from app.models import (
    AssuranceQuestionResult,
    AuditedClaim,
    ClaimAuthorityEdge,
    ClaimGraph,
    ClaimGraphNode,
    CompletenessSearch,
    EvaluationFlag,
    FailureFinding,
    ScoreGate,
)
from app.parsers import normalise_citation
from app.veritas import load_operating_config

FAILURE_NAMES = {
    1: "Citation hallucination",
    2: "Citation substitution",
    3: "Citation fidelity failure",
    4: "Contextual hallucination",
    5: "Synthesis and coverage failure",
}


@lru_cache(maxsize=1)
def assurance_policy() -> dict[str, object]:
    return load_operating_config().raw["assurance_policy"]


def build_claim_graph(claims: list[AuditedClaim]) -> ClaimGraph:
    policy = assurance_policy()
    nodes: list[ClaimGraphNode] = []
    edges: list[ClaimAuthorityEdge] = []
    authority_nodes: dict[str, ClaimGraphNode] = {}
    for claim in claims:
        claim_id = f"claim:{claim.order}"
        nodes.append(
            ClaimGraphNode(
                id=claim_id,
                node_type="claim",
                label=claim.text,
                proposition=claim.proposition,
                requires_authority=claim.requires_authority,
            )
        )
        if not claim.citation:
            continue
        key = normalise_citation(claim.citation)
        authority_id = f"authority:{key}"
        status = (
            "negative_registry_check"
            if claim.verdict == "likely_fabricated"
            else "unresolved"
            if claim.verdict == "unverified"
            else "resolved"
        )
        authority_nodes.setdefault(
            authority_id,
            ClaimGraphNode(
                id=authority_id,
                node_type="authority",
                label=claim.citation,
                resolution_status=status,
            ),
        )
        relation = (
            "supports"
            if any(item.relation == "supports" for item in claim.evidence)
            else "unresolved"
            if claim.verdict in {"unverified", "likely_fabricated"}
            else "purports_to_support"
        )
        edges.append(
            ClaimAuthorityEdge(
                claim_id=claim_id,
                authority_id=authority_id,
                relation=relation,
                mapping_confidence=claim.parser_confidence,
            )
        )
    nodes.extend(authority_nodes.values())
    return ClaimGraph(version=str(policy["claim_graph_version"]), nodes=nodes, edges=edges)


def completeness_searches(
    claims: list[AuditedClaim], audit_mode: str, corpus_version: str, scope_statement: str
) -> list[CompletenessSearch]:
    if audit_mode != "full":
        return []
    policy = assurance_policy()
    present_propositions = {claim.proposition for claim in claims}
    cited = {normalise_citation(claim.citation) for claim in claims if claim.citation}
    searches: list[CompletenessSearch] = []
    for graph in policy["issue_graphs"]:
        if not present_propositions.intersection(graph["trigger_propositions"]):
            continue
        missing = [
            citation for citation in graph["landmark_candidates"] if normalise_citation(citation) not in cited
        ]
        searches.append(
            CompletenessSearch(
                finding="Landmark candidate not engaged" if missing else "Pilot landmark set engaged",
                issue_tag=graph["issue_tag"],
                corpus_scope=f"{corpus_version}: {scope_statement}",
                landmark_set=graph["landmark_candidates"],
                landmark_set_version=graph["set_version"],
                validation_status=graph["validation_status"],
                retrieval_configuration="Exact citation-set comparison; no semantic counter-authority retrieval.",
                independence_attestation=(
                    "Static ProofMark reference-set comparison only. The auditee's retrieval stack is not used; "
                    "independent counter-authority retrieval is not implemented in this MVP."
                ),
                searched_and_not_found=missing,
                confidence_band="unvalidated pilot",
                measured_accuracy=None,
            )
        )
    return searches


def add_completeness_flags(
    flags: list[EvaluationFlag], searches: list[CompletenessSearch]
) -> list[EvaluationFlag]:
    enriched = list(flags)
    for search in searches:
        if search.searched_and_not_found:
            enriched.append(
                EvaluationFlag(
                    code="landmark_candidate_not_engaged",
                    module="balance_completeness",
                    severity="review",
                    message=(
                        f"Pilot landmark candidate(s) not engaged for {search.issue_tag.replace('_', ' ')}: "
                        f"{', '.join(search.searched_and_not_found)}. This is a review prompt, not a legal conclusion."
                    ),
                )
            )
    return enriched


def failure_findings(claims: list[AuditedClaim], flags: list[EvaluationFlag]) -> list[FailureFinding]:
    findings: list[FailureFinding] = []
    for claim in claims:
        level: int | None = None
        description = claim.rationale
        if claim.verdict == "likely_fabricated":
            level = 1
        elif claim.decision_rule_id in {"PM-CIT-004", "PM-CIT-005"}:
            level = 2
        elif claim.verdict == "unsupported":
            level = 3
        elif claim.verdict == "context_review" and (
            claim.overgeneralisation_terms or claim.decision_rule_id.startswith("PM-PROP")
        ):
            level = 4
        if level:
            claim.failure_level = level
            findings.append(
                FailureFinding(
                    level=level,
                    name=FAILURE_NAMES[level],
                    description=description,
                    claim_order=claim.order,
                    decision_rule_id=claim.decision_rule_id,
                )
            )
    for flag in flags:
        if flag.code in {
            "potential_omission",
            "potentially_one_sided",
            "missing_limiting_authority",
            "policy_factor_not_addressed",
            "landmark_candidate_not_engaged",
        }:
            findings.append(
                FailureFinding(
                    level=5,
                    name=FAILURE_NAMES[5],
                    description=flag.message,
                    claim_order=flag.claim_order,
                )
            )
    return findings


def score_gates(claims: list[AuditedClaim]) -> tuple[list[ScoreGate], float | None]:
    policy = assurance_policy()
    cap = float(policy["score_cap_when_gate_triggers"])
    fabricated = [claim for claim in claims if claim.verdict == "likely_fabricated"]
    bad_quotes = [check for claim in claims for check in claim.quote_checks if check.status == "not_found"]
    unsupported = [claim for claim in claims if claim.verdict == "unsupported" and not claim.citation]
    negative_currency = [claim for claim in claims if claim.currency_status == "negative_treatment"]
    gates = [
        ScoreGate(
            gate_id="citation_integrity",
            label="Citation integrity gate",
            status="triggered" if fabricated or bad_quotes else "passed",
            effect=f"Composite capped at {cap:g}" if fabricated or bad_quotes else "No cap applied",
            basis_tier="A",
            reason=(
                "Recorded negative-registry evidence or a quotation absent from the cited judgment triggered the gate."
                if fabricated or bad_quotes
                else "No recorded fabricated authority or unverified quotation was found."
            ),
        ),
        ScoreGate(
            gate_id="unsupported_assertion",
            label="Unsupported assertion gate",
            status="triggered" if unsupported else "passed",
            effect=f"Composite capped at {cap:g}" if unsupported else "No cap applied",
            basis_tier="A",
            reason=(
                "At least one extracted legal assertion requiring authority had no citation."
                if unsupported
                else "Every in-scope legal assertion was either cited or withheld from this gate."
            ),
        ),
        ScoreGate(
            gate_id="currency",
            label="Currency gate",
            status="triggered" if negative_currency else "not_assessed",
            effect=f"Composite capped at {cap:g}" if negative_currency else "No cap applied",
            basis_tier="human_verified_C" if negative_currency else "none",
            reason=(
                "A lawyer-approved negative treatment or supersession record was consumed."
                if negative_currency
                else "No lawyer-approved currency record was available; the system abstained."
            ),
        ),
        ScoreGate(
            gate_id="direct_contradiction",
            label="Direct contradiction gate",
            status="not_assessed",
            effect="No cap applied",
            basis_tier="none",
            reason="Legal NLI is not implemented as a gate; lexical similarity cannot prove contradiction.",
        ),
    ]
    return gates, cap if any(item.status == "triggered" for item in gates) else None


def assurance_questions(
    claims: list[AuditedClaim],
    flags: list[EvaluationFlag],
    searches: list[CompletenessSearch],
    audit_mode: str,
) -> list[AssuranceQuestionResult]:
    q1_findings = [
        claim
        for claim in claims
        if claim.verdict in {"likely_fabricated", "unverified"}
        or claim.citation_parse_status == "malformed"
        or claim.decision_rule_id in {"PM-CIT-004", "PM-CIT-005", "PM-CIT-006", "PM-CIT-008"}
    ]
    q2_findings = [claim for claim in claims if claim.verdict == "unsupported"]
    q3_flags = [
        flag
        for flag in flags
        if flag.module in {"propositional_accuracy", "relevance_currency"}
    ]
    q3_claims = [claim for claim in claims if claim.failure_level == 4]
    q4_findings = [flag for flag in flags if flag.module == "balance_completeness"]
    return [
        AssuranceQuestionResult(
            key="existence",
            question="Does the authority exist and is it correctly identified?",
            status="flagged" if q1_findings else "passed",
            summary=(
                f"{len(q1_findings)} identity, existence, pinpoint, or quotation issue(s) require attention."
                if q1_findings
                else "Resolved citations passed the deterministic identity and existence checks."
            ),
            finding_count=len(q1_findings),
            failure_levels=[1, 2],
        ),
        AssuranceQuestionResult(
            key="fidelity",
            question="Does the cited material support the proposition?",
            status="flagged" if q2_findings else "passed",
            summary=(
                f"{len(q2_findings)} claim(s) lacked proposition-linked support."
                if q2_findings
                else "No unsupported proposition was detected within the retained evidence boundary."
            ),
            finding_count=len(q2_findings),
            failure_levels=[3],
        ),
        AssuranceQuestionResult(
            key="legal_significance",
            question="Does it mean what the AI says, with the legal weight claimed?",
            status="flagged" if q3_claims or q3_flags else "partial" if audit_mode != "full" else "passed",
            summary=(
                f"{len(q3_claims) + len(q3_flags)} role, modality, fact-fit, or currency prompt(s) require lawyer review."
                if q3_claims or q3_flags
                else "Partially assessed; original question and facts were not supplied."
                if audit_mode != "full"
                else "No contextual overstatement was detected by the bounded checks."
            ),
            finding_count=len(q3_claims) + len(q3_flags),
            failure_levels=[4],
        ),
        AssuranceQuestionResult(
            key="completeness",
            question="What material issue or landmark candidate did the AI miss?",
            status="not_assessed"
            if audit_mode != "full"
            else "flagged"
            if q4_findings
            else "passed",
            summary=(
                "Completeness requires full mode and is not inferred from citations alone."
                if audit_mode != "full"
                else f"{len(q4_findings)} bounded completeness prompt(s); {len(searches)} search disclosure(s) recorded."
                if q4_findings
                else "The bounded issue checklist found no omission; this is not proof of completeness."
            ),
            finding_count=len(q4_findings),
            failure_levels=[5],
        ),
    ]
