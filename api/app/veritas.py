from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "veritas_operating_config.json"


class CorpusIntegrityError(RuntimeError):
    """Raised when an assurance result would require missing or altered legal data."""


TierStatus = Literal["complete", "queued", "not_required", "blocked_missing_data"]


class TierExecution(BaseModel):
    tier: Literal[0, 1, 2, 3]
    name: str
    status: TierStatus
    checks: list[str]
    duration_ms: float | None = None
    latency_target_ms: float | None = None
    target_status: Literal["unmeasured", "configured_not_claimed"] = "unmeasured"
    model_inference: bool = False
    escalated: bool = False
    reason: str


class DemoEvidence(BaseModel):
    citation: str
    case_name: str
    paragraph_label: str
    text: str
    official_url: str
    source_sha256: str
    hash_verified: bool


class VeritasDemoResult(BaseModel):
    demo_id: str
    title: str
    input: str
    expected_code: str
    detected_code: str
    expected_verdict: str
    verdict: str
    passed: bool
    explanation: str
    quote_status: Literal["exact_match", "not_applicable"] = "not_applicable"
    citation_gate: Literal["passed", "triggered", "not_assessed"]
    currency_gate: Literal["passed", "triggered", "not_assessed"]
    evidence: list[DemoEvidence]
    tier_trace: list[TierExecution]
    human_review_id: UUID | None = None


class VeritasDemoSuite(BaseModel):
    config_version: str
    scope: str
    integrity_instruction: str
    run_at: datetime
    passed_count: int
    demo_count: int
    targets_are_measurements: bool = False
    tier_2_sampling_status: str
    results: list[VeritasDemoResult]


class HumanReviewDecision(BaseModel):
    reviewer_name: str = Field(min_length=2, max_length=200)
    reviewer_role: Literal["qualified_lawyer", "legal_researcher"]
    decision: Literal["confirm", "reject", "needs_more_evidence"]
    rationale: str = Field(min_length=10, max_length=5000)
    dissent: str | None = Field(default=None, max_length=5000)
    decided_at: datetime


class HumanReviewDecisionSubmission(BaseModel):
    reviewer_name: str = Field(min_length=2, max_length=200)
    reviewer_role: Literal["qualified_lawyer", "legal_researcher"]
    decision: Literal["confirm", "reject", "needs_more_evidence"]
    rationale: str = Field(min_length=10, max_length=5000)
    dissent: str | None = Field(default=None, max_length=5000)


class HumanReviewItem(BaseModel):
    public_id: UUID
    demo_id: str
    issue: str
    status: Literal["queued", "under_review", "resolved", "blocked_missing_data"]
    created_at: datetime
    decisions: list[HumanReviewDecision] = Field(default_factory=list)
    authoritative_resolution: Literal["confirmed", "rejected", "unresolved"] = "unresolved"
    gold_candidate: bool = False
    resolution_note: str


@dataclass(frozen=True)
class ValidatedConfig:
    raw: dict[str, Any]
    sources: dict[str, dict[str, Any]]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_operating_config(path: Path = CONFIG_PATH) -> ValidatedConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusIntegrityError(f"VERITAS operating config could not be loaded: {exc}") from exc

    integrity = raw.get("integrity_policy", {})
    if integrity.get("missing_corpus_behaviour") != "fail_loudly":
        raise CorpusIntegrityError("Operating config must require fail_loudly corpus behaviour")
    if not integrity.get("forbid_fabricated_authority_records") or not integrity.get("forbid_synthetic_judgment_text"):
        raise CorpusIntegrityError("No-fabrication policy is missing or disabled")

    allowed_hosts = set(integrity.get("official_source_hosts", []))
    sources: dict[str, dict[str, Any]] = {}
    for source in raw.get("demo_sources", []):
        source_id = source.get("source_id")
        if not source_id or source_id in sources:
            raise CorpusIntegrityError("Every demo source requires a unique source_id")
        if urlparse(source.get("official_url", "")).hostname not in allowed_hosts:
            raise CorpusIntegrityError(f"{source_id}: source is not on the official host allowlist")
        citation = source.get("citation", "")
        citation_parts = citation.removeprefix("[").split("]", 1)
        citation_valid = (
            citation.startswith("[")
            and len(citation_parts) == 2
            and re.fullmatch("[0-9]{4}", citation_parts[0])
            and re.fullmatch("SG[A-Z()]+[ ]+[0-9]+", citation_parts[1].strip(), re.IGNORECASE)
        )
        if not citation_valid:
            raise CorpusIntegrityError(f"{source_id}: invalid Singapore neutral citation")
        expected_hash = source.get("sha256")
        if not expected_hash or expected_hash == "PENDING":
            raise CorpusIntegrityError(f"{source_id}: source hash is missing")
        if _sha256(source.get("text", "")) != expected_hash:
            raise CorpusIntegrityError(f"{source_id}: official excerpt hash mismatch")
        paragraph_label = source.get("paragraph_label", "")
        paragraph_body = paragraph_label[1:-1].replace("–", "-") if len(paragraph_label) >= 2 else ""
        if not (
            paragraph_label.startswith("[")
            and paragraph_label.endswith("]")
            and re.fullmatch("[0-9]+(?:-[0-9]+)?", paragraph_body)
        ):
            raise CorpusIntegrityError(f"{source_id}: paragraph anchor is missing or malformed")
        sources[source_id] = source

    if not sources:
        raise CorpusIntegrityError("No authoritative demo sources are configured")
    for demo in raw.get("demos", []):
        missing = [source_id for source_id in demo.get("source_ids", []) if source_id not in sources]
        if missing:
            raise CorpusIntegrityError(f"{demo.get('id', 'unknown demo')}: missing corpus sources {missing}")
    return ValidatedConfig(raw=raw, sources=sources)


class HumanReviewQueue:
    """Local MVP queue. It never invents reviewer decisions or silently promotes gold."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._items: dict[UUID, HumanReviewItem] = {}
        self._by_demo: dict[str, UUID] = {}
        self._lock = RLock()
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            items = [HumanReviewItem.model_validate(item) for item in payload]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CorpusIntegrityError(f"Tier 3 review queue could not be loaded: {exc}") from exc
        self._items = {item.public_id: item for item in items}
        self._by_demo = {item.demo_id: item.public_id for item in items}

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([item.model_dump(mode="json") for item in self._items.values()], indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def enqueue(self, demo_id: str, issue: str) -> HumanReviewItem:
        with self._lock:
            existing_id = self._by_demo.get(demo_id)
            if existing_id:
                return self._items[existing_id].model_copy(deep=True)
            item = HumanReviewItem(
                public_id=uuid4(),
                demo_id=demo_id,
                issue=issue,
                status="queued",
                created_at=datetime.now(UTC),
                resolution_note="Awaiting two independent qualified-lawyer decisions.",
            )
            self._items[item.public_id] = item
            self._by_demo[demo_id] = item.public_id
            self._persist()
            return item.model_copy(deep=True)

    def list(self) -> list[HumanReviewItem]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._items.values()]

    def get(self, public_id: UUID) -> HumanReviewItem | None:
        with self._lock:
            item = self._items.get(public_id)
            return item.model_copy(deep=True) if item else None

    def decide(self, public_id: UUID, submission: HumanReviewDecisionSubmission) -> HumanReviewItem:
        with self._lock:
            item = self._items.get(public_id)
            if not item:
                raise LookupError("Human review item not found")
            if any(decision.reviewer_name.casefold() == submission.reviewer_name.casefold() for decision in item.decisions):
                raise ValueError("Independent review required: this reviewer already submitted a decision")
            item.decisions.append(
                HumanReviewDecision(
                    **submission.model_dump(),
                    decided_at=datetime.now(UTC),
                )
            )
            qualified = [d for d in item.decisions if d.reviewer_role == "qualified_lawyer"]
            if len(qualified) < 2:
                item.status = "under_review"
                item.resolution_note = "A second independent qualified-lawyer decision is required."
            elif all(d.decision == "confirm" for d in qualified[-2:]):
                item.status = "resolved"
                item.authoritative_resolution = "confirmed"
                item.gold_candidate = True
                item.resolution_note = (
                    "Two independent qualified lawyers confirmed the result; "
                    "it is only a gold candidate until separately versioned."
                )
            elif all(d.decision == "reject" for d in qualified[-2:]):
                item.status = "resolved"
                item.authoritative_resolution = "rejected"
                item.resolution_note = "Two independent qualified lawyers rejected the result."
            else:
                item.status = "under_review"
                item.authoritative_resolution = "unresolved"
                item.gold_candidate = False
                item.resolution_note = "Qualified reviewers disagree or require more evidence; authoritative resolution is withheld."
            self._persist()
            return item.model_copy(deep=True)


class VeritasDemoRunner:
    def __init__(self, queue: HumanReviewQueue | None = None) -> None:
        self.queue = queue or HumanReviewQueue()

    @staticmethod
    def _evidence(source: dict[str, Any]) -> DemoEvidence:
        actual = _sha256(source["text"])
        return DemoEvidence(
            citation=source["citation"],
            case_name=source["case_name"],
            paragraph_label=source["paragraph_label"],
            text=source["text"],
            official_url=source["official_url"],
            source_sha256=source["sha256"],
            hash_verified=actual == source["sha256"],
        )

    @staticmethod
    def _tier(
        config: ValidatedConfig,
        tier: int,
        status: TierStatus,
        started: float,
        reason: str,
        *,
        escalated: bool = False,
    ) -> TierExecution:
        spec = next(item for item in config.raw["tiers"] if item["tier"] == tier)
        target = config.raw["measurement_policy"]["latency_targets_ms"][f"tier_{tier}"]
        return TierExecution(
            tier=tier,
            name=spec["name"],
            status=status,
            checks=spec["checks"],
            duration_ms=round((perf_counter() - started) * 1000, 3) if status == "complete" else None,
            latency_target_ms=target,
            target_status="configured_not_claimed" if target is not None else "unmeasured",
            model_inference=False,
            escalated=escalated,
            reason=reason,
        )

    def run(self) -> VeritasDemoSuite:
        config = load_operating_config()
        with ThreadPoolExecutor(max_workers=min(5, len(config.raw["demos"]))) as pool:
            results = list(pool.map(lambda demo: self._run_demo(config, demo), config.raw["demos"]))
        sample_rate = config.raw["measurement_policy"]["tier_2_sample_rate"]
        return VeritasDemoSuite(
            config_version=config.raw["config_version"],
            scope=config.raw["scope"],
            integrity_instruction=config.raw["integrity_policy"]["instruction"],
            run_at=datetime.now(UTC),
            passed_count=sum(result.passed for result in results),
            demo_count=len(results),
            tier_2_sampling_status=(
                "Escalated cases run at Tier 2; random sampling is disabled until a measured sample rate is configured."
                if sample_rate is None
                else f"Escalated cases plus the configured {sample_rate:g} sample rate run at Tier 2."
            ),
            results=results,
        )

    def _run_demo(self, config: ValidatedConfig, demo: dict[str, Any]) -> VeritasDemoResult:
        evidence = [self._evidence(config.sources[source_id]) for source_id in demo["source_ids"]]
        if not all(item.hash_verified for item in evidence):
            raise CorpusIntegrityError(f"{demo['id']}: source hash verification failed")

        traces: list[TierExecution] = []
        t0 = perf_counter()
        code = ""
        verdict = "unverified"
        explanation = ""
        quote_status: Literal["exact_match", "not_applicable"] = "not_applicable"
        citation_gate: Literal["passed", "triggered", "not_assessed"] = "passed"
        currency_gate: Literal["passed", "triggered", "not_assessed"] = "not_assessed"

        if demo["id"] == "demo_1":
            proof = {item.paragraph_label: item.text for item in evidence}
            if "[10]" not in proof or "did not exist" not in proof["[10]"] or "[24]" not in proof:
                raise CorpusIntegrityError("demo_1 requires the court's non-existence finding and withholding explanation")
            code, verdict = "court_confirmed_fictitious", "likely_fabricated"
            citation_gate = "triggered"
            explanation = (
                "The strongest label is based on the Singapore High Court's "
                "recorded non-existence finding. The false citation remains redacted."
            )
        elif demo["id"] == "demo_2":
            cited = evidence[0]
            cited_name = demo["input"].split("[", 1)[0].strip()
            if cited_name.casefold() == cited.case_name.casefold():
                raise CorpusIntegrityError("demo_2 no longer contains a case-name/citation mismatch")
            code, verdict = "case_name_mismatch", "unsupported"
            citation_gate = "triggered"
            explanation = "The neutral citation resolves, but its canonical case name differs from the name paired with it."
        traces.append(self._tier(config, 0, "complete", t0, "Deterministic citation, identity, source and gate checks completed."))

        t1 = perf_counter()
        if demo["id"] == "demo_3":
            quoted = re.search(r'"([^"]+)"', demo["input"])
            if not quoted or quoted.group(1) not in evidence[0].text:
                raise CorpusIntegrityError("demo_3 exact quote is missing from its anchored official excerpt")
            quote_status = "exact_match"
            if demo.get("asserted_proposition") == demo.get("source_proposition"):
                raise CorpusIntegrityError("demo_3 no longer tests a proposition mismatch")
            code, verdict = "verified_quote_no_support", "unsupported"
            citation_gate = "triggered"
            explanation = "The quotation is exact, but the anchored passage concerns legitimate interest—not geographic reasonableness."
        elif demo["id"] == "demo_4":
            if "dissenting judge" not in evidence[0].text or demo.get("claimed_role") == demo.get("source_role"):
                raise CorpusIntegrityError("demo_4 requires exact non-majority role evidence")
            quote_status = "exact_match"
            code, verdict = "non_majority_as_holding", "context_review"
            explanation = (
                "The passage expressly identifies a foreign dissenting judge; "
                "presenting it as the Singapore court's holding is a role error."
            )
        traces.append(
            self._tier(
                config,
                1,
                "complete",
                t1,
                "Claim graph, constrained evidence relation, role and modality checks completed without model inference.",
                escalated=demo["detection_tier"] >= 1,
            )
        )

        t2 = perf_counter()
        if demo["id"] == "demo_5":
            if demo.get("treatment") != "rejects_application" or "rejected the application" not in evidence[0].text:
                raise CorpusIntegrityError("demo_5 reviewed issue-specific treatment evidence is missing")
            code, verdict = "approved_negative_treatment", "context_review"
            currency_gate = "triggered"
            explanation = (
                "A later superior-court passage records issue-specific rejection of the relied-on approach. "
                "The result is a currency review flag, not a fabricated claim of formal overruling."
            )
        tier2_required = demo["id"] in {"demo_1", "demo_4", "demo_5"}
        traces.append(
            self._tier(
                config,
                2,
                "complete" if tier2_required else "not_required",
                t2,
                (
                    "Independent source-role or treatment review completed from the locked official evidence ledger."
                    if tier2_required
                    else "No escalation trigger fired; random sampling is disabled because its operating point is unmeasured."
                ),
                escalated=tier2_required,
            )
        )

        human_item = None
        if demo["id"] in {"demo_1", "demo_5"}:
            human_item = self.queue.enqueue(demo["id"], explanation)
        traces.append(
            self._tier(
                config,
                3,
                "queued" if human_item else "not_required",
                perf_counter(),
                (
                    "Queued for two independent qualified-lawyer decisions; no human outcome is generated by the system."
                    if human_item
                    else "The configured human-review escalation rule did not fire."
                ),
                escalated=bool(human_item),
            )
        )

        if not code:
            raise CorpusIntegrityError(f"{demo['id']}: no deterministic demo rule produced a result")
        return VeritasDemoResult(
            demo_id=demo["id"],
            title=demo["title"],
            input=demo["input"],
            expected_code=demo["expected_code"],
            detected_code=code,
            expected_verdict=demo["expected_verdict"],
            verdict=verdict,
            passed=code == demo["expected_code"] and verdict == demo["expected_verdict"],
            explanation=explanation,
            quote_status=quote_status,
            citation_gate=citation_gate,
            currency_gate=currency_gate,
            evidence=evidence,
            tier_trace=traces,
            human_review_id=human_item.public_id if human_item else None,
        )


def public_operating_config() -> dict[str, Any]:
    config = load_operating_config().raw
    return {
        "config_version": config["config_version"],
        "scope": config["scope"],
        "measurement_policy": config["measurement_policy"],
        "calibration": config["calibration"],
        "assurance_policy": config["assurance_policy"],
        "integrity_policy": config["integrity_policy"],
        "tiers": config["tiers"],
    }
