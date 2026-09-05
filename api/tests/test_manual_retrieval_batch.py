import json
from pathlib import Path
from urllib.parse import urlparse

BATCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "research_catalog"
    / "v1"
    / "manual_retrieval_batch_01.json"
)
BATCH_02_PATH = BATCH_PATH.with_name("manual_retrieval_batch_02.json")


def test_manual_batch_is_review_gated_and_metadata_only():
    payload = json.loads(BATCH_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "awaiting_legal_review"
    assert payload["runtime_use"] == "research_only_not_loaded_by_active_corpus"
    records = payload["records"]
    assert len(records) == 13
    assert len({record["citation"] for record in records}) == len(records)
    assert sum(record["dataset_match_count"] for record in records) == 225

    for record in records:
        parsed = urlparse(record["official_url"])
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.elitigation.sg"
        assert record["page_variant"] in {"gd/s", "gdviewer/s"}
        assert record["review_status"] == "draft"
        assert record["document_hash"] is None
        assert record["hash_status"] == "pending_legal_source_export"
        assert "raw_text" not in record
        assert "extract" not in record
        assert "passage" not in record
        assert record["paragraph_targets"]


def test_manual_batch_02_completes_phase_one_target_without_raw_text():
    payload = json.loads(BATCH_02_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "awaiting_legal_review"
    assert payload["runtime_use"] == "research_only_not_loaded_by_active_corpus"
    records = payload["records"]
    assert len(records) == 12
    assert len({record["citation"] for record in records}) == len(records)
    assert sum(record["dataset_match_count"] for record in records) == 324

    all_keys = set()
    for path in (BATCH_PATH, BATCH_02_PATH):
        batch = json.loads(path.read_text(encoding="utf-8"))
        for record in batch["records"]:
            key = record["citation"]
            assert key not in all_keys
            all_keys.add(key)
            assert "raw_text" not in record
            assert "extract" not in record
            assert "passage" not in record

    assert len(all_keys) == 25
