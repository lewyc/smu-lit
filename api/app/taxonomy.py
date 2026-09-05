TAXONOMY_VERSION = "sg-rot-taxonomy-1.0"

PROPOSITIONS = {
    "prima_facie_unenforceable",
    "legitimate_proprietary_interest",
    "reasonableness_between_parties",
    "reasonableness_public_interest",
    "confidential_information",
    "customer_connections",
    "stable_trained_workforce",
    "geographic_scope",
    "duration_scope",
    "activity_scope",
    "interim_injunction_standard",
    "outside_corpus_scope",
}

PHRASE_MAP: list[tuple[tuple[str, ...], str]] = [
    (("personal data", "pdpa", "privacy", "criminal", "patent", "copyright"), "outside_corpus_scope"),
    (("interim injunction", "serious question to be tried", "balance of convenience"), "interim_injunction_standard"),
    (("confidential information", "trade secret"), "confidential_information"),
    (("customer connection", "customer relationship", "goodwill"), "customer_connections"),
    (("stable trained workforce", "trained workforce", "employee stability"), "stable_trained_workforce"),
    (("geographic", "worldwide", "singapore-wide", "territorial"), "geographic_scope"),
    (("duration", "year", "month", "temporal"), "duration_scope"),
    (("activity", "business scope", "competing business"), "activity_scope"),
    (("public interest", "public policy"), "reasonableness_public_interest"),
    (("between the parties", "as between the parties"), "reasonableness_between_parties"),
    (("legitimate proprietary interest", "legitimate interest", "protectable interest"), "legitimate_proprietary_interest"),
    (("prima facie", "unenforceable", "void restraint", "non-compete"), "prima_facie_unenforceable"),
]

OVERGENERALISATION_TERMS = (
    "always",
    "automatically",
    "all non-competes",
    "all restraints",
    "never enforceable",
    "in every case",
)


def proposition_for(text: str) -> tuple[str, float]:
    lowered = text.lower()
    for phrases, proposition in PHRASE_MAP:
        if any(phrase in lowered for phrase in phrases):
            return proposition, 0.88
    if any(word in lowered for word in ("court", "legal", "law", "enforce", "restraint")):
        return "legitimate_proprietary_interest", 0.45
    return "outside_corpus_scope", 0.7
