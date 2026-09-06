from __future__ import annotations

import json

import pytest

from app.benchmark_cli import run_release_benchmark


def test_release_benchmark_requires_250_runs(tmp_path) -> None:
    with pytest.raises(ValueError, match="at least 250"):
        run_release_benchmark(performance_runs=249, output=tmp_path / "benchmark.json")


def test_release_benchmark_writes_gate_evidence(tmp_path) -> None:
    output = tmp_path / "benchmark.json"
    payload = run_release_benchmark(performance_runs=250, output=output)

    assert output.exists()
    assert payload["release"] == "tier0-v1-citation-integrity"
    assert all(payload["release_gate"].values())
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["benchmark"]["error_count"] == 0
    assert stored["benchmark"]["citation_identity_precision"] == 100
    assert stored["benchmark"]["pinpoint_precision"] == 100
    assert stored["benchmark"]["quote_accuracy"] == 100
    assert stored["benchmark"]["gate_confusion_matrix"]
