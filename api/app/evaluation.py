from __future__ import annotations

import re

from app.assurance import assurance_policy
from app.models import AuditedClaim, ContextProfile, EvaluationFlag, ModuleScore

ISSUE_CHECKLIST = {
    "legitimate_proprietary_interest",
    "reasonableness_between_parties",
    "reasonableness_public_interest",
}

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
    weights = assurance_policy()["weights"]
    flags: list[EvaluationFlag] = []
    in_scope = [claim for claim in claims if claim.verdict != "out_of_scope"]
    for claim in in_scope:
        if claim.verdict == "unsupported" and not claim.citation:
            flags.append(
                EvaluationFlag(
                    code="unsupported_legal_assertion",
                    module="propositional_accuracy",
                    severity="serious",
                    message="An extracted legal assertion that requires authority has no supporting citation.",
                    claim_order=claim.order,
                )
            )
        if any(check.status == "not_found" for check in claim.quote_checks):
            flags.append(
                EvaluationFlag(
                    code="unverified_quote",
                    module="citation_integrity",
                    severity="serious",
                    message="Quoted wording was not found in the cited judgment after exact and whitespace-normalised checks.",
                    claim_order=claim.order,
                )
            )
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
    proposition_score = _percentage(
        len([c for c in in_scope if any(e.relation == "supports" for e in c.evidence)]),
        len(in_scope),
    )
    currency_known = [c for c in in_scope if c.currency_status != "not_verified"]
    currency_score = (
        _percentage(len([c for c in currency_known if c.currency_status == "current_reviewed"]), len(currency_known))
        if currency_known
        else 0
    )

    if mode == "full":
        present = {claim.proposition for claim in in_scope}
        expected = set(ISSUE_CHECKLIST)
        source_text = " ".join(claim.text.lower() for claim in claims)
        if "confidential" in source_text or (profile and profile.confidential_information_access):
            expected.add("confidential_information")
        if "customer" in source_text or (profile and profile.customer_connection):
            expected.add("customer_connections")
        if "injunction" in source_text or (profile and profile.relief_sought == "injunction"):
            expected.add("interim_injunction_standard")
        if "sever" in source_text or "blue pencil" in source_text:
            expected.add("severance_blue_pencil")
        missing = sorted(expected - present)
        for proposition in missing:
            flags.append(
                EvaluationFlag(
                    code="potential_omission",
                    module="balance_completeness",
                    severity="review",
                    message=f"The issue checklist expects consideration of {proposition.replace('_', ' ')}.",
                )
            )
        if not {"reasonableness_between_parties", "reasonableness_public_interest"}.issubset(present):
            flags.append(
                EvaluationFlag(
                    code="potentially_one_sided",
                    module="balance_completeness",
                    severity="review",
                    message="The answer may not address both private reasonableness and public-interest considerations.",
                )
            )
        if "policy_freedom_to_trade" not in present:
            flags.append(
                EvaluationFlag(
                    code="policy_factor_not_addressed",
                    module="balance_completeness",
                    severity="review",
                    message="Freedom-of-trade and bargaining-power policy considerations were not identified.",
                )
            )
        balance_score = _percentage(len(expected & present), len(expected))
        balance = ModuleScore(score=balance_score, weight=weights["balance"], assessed=True)
    else:
        balance = ModuleScore(
            score=None,
            weight=weights["balance"],
            assessed=False,
            reason_not_assessed="Balance and omissions require the original question and facts in full mode.",
        )

    modules = {
        "citation": ModuleScore(score=citation_score, weight=weights["citation"], assessed=True),
        "proposition": ModuleScore(score=proposition_score, weight=weights["proposition"], assessed=True),
        "currency": ModuleScore(
            score=currency_score if currency_known else None,
            weight=weights["currency"],
            assessed=bool(currency_known),
            reason_not_assessed=None if currency_known else "No lawyer-approved authority-treatment record is available.",
        ),
        "balance": balance,
    }
    return flags, modules


def overall_score(modules: dict[str, ModuleScore], mode: str) -> float | None:
    if mode != "full" or not all(item.assessed for item in modules.values()):
        return None
    total_weight = sum(item.weight for item in modules.values())
    return round(sum((item.score or 0) * item.weight for item in modules.values()) / total_weight, 1)


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
