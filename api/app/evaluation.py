from __future__ import annotations

import re

from app.models import AuditedClaim, ContextProfile, EvaluationFlag, ModuleScore

COURT_HIERARCHY = [
    {"court_code": "SGCA", "tier": 5, "label": "Singapore Court of Appeal", "default_status": "binding"},
    {"court_code": "SGHC(A)", "tier": 4, "label": "Appellate Division of the High Court", "default_status": "persuasive"},
    {"court_code": "SGHC", "tier": 3, "label": "Singapore High Court", "default_status": "persuasive"},
    {"court_code": "SICC", "tier": 3, "label": "Singapore International Commercial Court", "default_status": "persuasive"},
]

SOURCE_HIERARCHY = [
    {"tier": 1, "label": "Official judgment or legislation"},
    {"tier": 2, "label": "Verified licensed report or database metadata"},
    {"tier": 3, "label": "Recognised journal, textbook or commentary"},
    {"tier": 4, "label": "Other secondary source"},
    {"tier": 5, "label": "User-supplied or unverified material"},
]

DECISION_AUTHORITY = [
    "Deterministic source and citation checks",
    "Gold benchmark annotations",
    "Lawyer-approved Case Map annotations",
    "Approved registry and authority-treatment records",
    "AI-supported paragraph labels",
    "TF-IDF ranking",
    "Pending practitioner feedback",
]


def court_code(citation: str | None) -> str | None:
    match = re.search(r"\]\s*(SG[A-Z()]+)\s+\d+", citation or "", re.IGNORECASE)
    return match.group(1).upper() if match else None


def context_profile(original_question: str | None, facts: str | None) -> ContextProfile:
    text = " ".join(filter(None, [original_question, facts]))
    lowered = text.lower()
    duration = re.search(r"\b(\d+\s*(?:day|week|month|year)s?)\b", lowered)
    geography = next((item for item in ("worldwide", "singapore", "asia", "regional") if item in lowered), None)
    activities = [
        item for item in ("solicit customers", "deal with customers", "join a competitor", "disclose information") if item in lowered
    ]
    interest = next(
        (item for item in ("confidential information", "customer connections", "stable trained workforce") if item in lowered),
        None,
    )
    stage = next((item for item in ("interim injunction", "trial", "appeal") if item in lowered), None)
    relief = "injunction" if "injunction" in lowered else "damages" if "damages" in lowered else None
    role_match = re.search(r"\b(?:employee|role|worked as|was a)\s+(?:an?\s+)?([a-z][a-z -]{2,40})", lowered)
    return ContextProfile(
        duration=duration.group(1) if duration else None,
        geographic_scope=geography,
        restricted_activities=activities,
        alleged_proprietary_interest=interest,
        confidential_information_access=True if "confidential" in lowered else None,
        customer_connection=True if "customer" in lowered else None,
        employee_role=role_match.group(1).strip() if role_match else None,
        procedural_stage=stage,
        relief_sought=relief,
    )


def evaluate_framework(
    claims: list[AuditedClaim], mode: str, profile: ContextProfile | None
) -> tuple[list[EvaluationFlag], dict[str, ModuleScore]]:
    flags: list[EvaluationFlag] = []
    in_scope = [claim for claim in claims if claim.verdict != "out_of_scope"]
    for claim in in_scope:
        if claim.pinpoint_status in {"missing", "wrong_proposition"}:
            flags.append(
                EvaluationFlag(
                    code="wrong_pinpoint",
                    module="citation_integrity",
                    severity="serious",
                    message="The supplied pinpoint is missing or does not support the mapped proposition.",
                    claim_order=claim.order,
                )
            )
        if claim.quote_status == "mismatch":
            flags.append(
                EvaluationFlag(
                    code="quote_mismatch",
                    module="citation_integrity",
                    severity="serious",
                    message="The supplied direct quote does not match the cited, pinpointed retained paragraph.",
                    claim_order=claim.order,
                )
            )
        role_flag = {
            "party_submission": "party_submission_as_holding",
            "dissent": "dissent_as_holding",
            "obiter": "obiter_as_binding",
        }.get(claim.source_role_status)
        if role_flag:
            flags.append(
                EvaluationFlag(
                    code=role_flag,
                    module="citation_integrity",
                    severity="review",
                    message="Reviewer-labelled source role requires lawyer review before the passage is presented as a judicial holding.",
                    claim_order=claim.order,
                )
            )
        if claim.modality == "mandatory" and claim.overgeneralisation_terms:
            flags.append(
                EvaluationFlag(
                    code="modality_overstatement",
                    module="propositional_accuracy",
                    severity="review",
                    message="Absolute language may overstate a qualified, fact-sensitive authority.",
                    claim_order=claim.order,
                )
            )
        if claim.currency_status == "negative_treatment":
            flags.append(
                EvaluationFlag(
                    code="negative_treatment",
                    module="relevance_currency",
                    severity="serious",
                    message="A lawyer-approved record identifies later treatment, supersession, or amendment requiring currency review.",
                    claim_order=claim.order,
                )
            )

    citation_score = _percentage(
        len(
            [
                c
                for c in in_scope
                if c.citation
                and c.citation_identity_status == "matched"
                and c.pinpoint_status not in {"missing", "wrong_proposition"}
                and c.quote_status != "mismatch"
            ]
        ),
        len([c for c in in_scope if c.citation]),
    )
    currency_known = [c for c in in_scope if c.currency_status != "not_verified"]
    currency_score = (
        _percentage(len([c for c in currency_known if c.currency_status == "current_reviewed"]), len(currency_known))
        if currency_known
        else 0
    )

    balance = ModuleScore(
        score=None,
        weight=0,
        assessed=False,
        reason_not_assessed="Completeness and contextual analysis are deferred beyond Tier 0.",
    )

    modules = {
        "citation": ModuleScore(score=citation_score, weight=100, assessed=True),
        "proposition": ModuleScore(
            score=None,
            weight=0,
            assessed=False,
            reason_not_assessed="Proposition entailment is deferred beyond Tier 0.",
        ),
        "currency": ModuleScore(
            score=currency_score if currency_known else None,
            weight=20,
            assessed=bool(currency_known),
            reason_not_assessed=None if currency_known else "No lawyer-approved authority-treatment record is available.",
        ),
        "balance": balance,
    }
    return flags, modules


def overall_score(modules: dict[str, ModuleScore], mode: str) -> float | None:
    return None


def _percentage(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0


def hierarchies() -> dict[str, object]:
    return {
        "court_hierarchy": COURT_HIERARCHY,
        "foreign_research_priority": ["Singapore", "United Kingdom", "Australia", "United States"],
        "foreign_priority_note": "Research ordering only; it is not a precedential-status rule.",
        "source_hierarchy": SOURCE_HIERARCHY,
        "decision_authority": DECISION_AUTHORITY,
    }
