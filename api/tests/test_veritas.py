from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.veritas import (
    CONFIG_PATH,
    CorpusIntegrityError,
    HumanReviewDecisionSubmission,
    HumanReviewQueue,
    VeritasDemoRunner,
    load_operating_config,
)


def test_all_five_official_source_demos_pass_and_execute_tiers() -> None:
    suite = VeritasDemoRunner().run()
    assert suite.demo_count == 5
    assert suite.passed_count == 5
    assert suite.targets_are_measurements is False
    assert all(len(result.tier_trace) == 4 for result in suite.results)
    assert all(result.tier_trace[0].status == "complete" for result in suite.results)
    assert all(result.tier_trace[0].latency_target_ms is None for result in suite.results)
    assert {result.detected_code for result in suite.results} == {
        "court_confirmed_fictitious",
        "case_name_mismatch",
        "verified_quote_no_support",
        "non_majority_as_holding",
        "approved_negative_treatment",
    }


def test_demo_one_keeps_false_citation_redacted() -> None:
    demo = VeritasDemoRunner().run().results[0]
    assert demo.verdict == "likely_fabricated"
    assert demo.citation_gate == "triggered"
    assert "redacted" in demo.explanation
    assert all(evidence.citation == "[2026] SGHC 49" for evidence in demo.evidence)


def test_tier_three_requires_two_independent_qualified_lawyers() -> None:
    queue = HumanReviewQueue()
    item = queue.enqueue("demo_5", "Currency treatment requires authoritative resolution")
    first = queue.decide(
        item.public_id,
        HumanReviewDecisionSubmission(
            reviewer_name="Lawyer One",
            reviewer_role="qualified_lawyer",
            decision="confirm",
            rationale="I checked the official anchored passage and confirm the issue-specific treatment.",
        ),
    )
    assert first.status == "under_review"
    assert not first.gold_candidate

    with pytest.raises(ValueError, match="Independent review"):
        queue.decide(
            item.public_id,
            HumanReviewDecisionSubmission(
                reviewer_name="Lawyer One",
                reviewer_role="qualified_lawyer",
                decision="confirm",
                rationale="A duplicate reviewer must not count as an independent second decision.",
            ),
        )

    second = queue.decide(
        item.public_id,
        HumanReviewDecisionSubmission(
            reviewer_name="Lawyer Two",
            reviewer_role="qualified_lawyer",
            decision="confirm",
            rationale="I independently checked the official anchored passage and confirm the result.",
        ),
    )
    assert second.status == "resolved"
    assert second.gold_candidate


def test_missing_or_modified_source_fails_loudly(tmp_path: Path) -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["demo_sources"][0]["text"] += " altered"
    path = tmp_path / "bad-config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorpusIntegrityError, match="hash mismatch"):
        load_operating_config(path)


def test_veritas_api_exposes_config_demos_and_real_review_queue() -> None:
    client = TestClient(app)
    config = client.get("/api/v1/veritas/config")
    assert config.status_code == 200
    assert config.json()["measurement_policy"]["latency_targets_ms"]["tier_0"] is None
    demos = client.post("/api/v1/veritas/demos/run")
    assert demos.status_code == 200
    assert demos.json()["passed_count"] == 5
    reviews = client.get("/api/v1/veritas/reviews")
    assert reviews.status_code == 200
    assert reviews.json()
