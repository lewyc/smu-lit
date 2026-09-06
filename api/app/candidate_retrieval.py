"""Offline, review-gated cross-authority candidate retrieval.

This module is deliberately separate from cited-authority evidence matching.
Its results are research leads and never participate in verdicts or scores.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import sklearn
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from app.models import (
    AuditedClaim,
    Authority,
    CandidateAuthorityLead,
    CandidateIndexStatus,
    CandidateParagraph,
    CandidateSearchResult,
    CaseMapDetail,
)
from app.parsers import normalise_citation
from app.research_catalog import MANIFEST_FILENAME, canonical_json_hash, load_catalogue

CANDIDATE_INDEX_VERSION = "proofmark-candidate-index.1"
RETRIEVAL_VERSION = "proofmark-hybrid-tfidf-svd.1"
BUILDER_VERSION = "proofmark-candidate-index-builder.1"
REVIEW_LABEL = "Potentially relevant authority — requires source and treatment review"
DEFAULT_CATALOGUE_DIR = Path(__file__).resolve().parent.parent / "data" / "research_catalog" / "v1"
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "candidate_index" / "v1"
INDEX_MANIFEST = "manifest.json"
INDEX_CHUNKS = "chunks.json"
INDEX_VECTORS = "index.npz"
LEXICAL_WEIGHT = 0.55
DENSE_WEIGHT = 0.35
PROPOSITION_WEIGHT = 0.10
MAX_RESULTS = 5
MIN_CALIBRATION_QUERIES = 20
RANKING_CONFIG = {
    "lexical": {"ngram_range": [1, 2], "stop_words": "english"},
    "dense": {"method": "truncated_svd", "max_dimensions": 64, "n_iter": 7, "random_seed": 0},
    "weights": {"lexical": LEXICAL_WEIGHT, "dense": DENSE_WEIGHT, "proposition": PROPOSITION_WEIGHT},
    "max_results": MAX_RESULTS,
}


class CandidateIndexError(RuntimeError):
    """Raised when a candidate index cannot be safely built or loaded."""


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise_dense(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0.0, 1.0)


def _chunk_text(chunk: dict[str, object]) -> str:
    return " ".join(
        str(value)
        for value in (
            chunk["case_name"],
            chunk["citation"],
            chunk.get("proposition") or "",
            chunk["statement"],
            " ".join(chunk["limitations"]),
            " ".join(chunk["applicability_factors"]),
            " ".join(item["text"] for item in chunk["paragraphs"]),
        )
        if value
    )


def _catalogue_chunks(records: list[dict[str, object]]) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for record in records:
        authority = Authority.model_validate(record["authority"])
        case_map = CaseMapDetail.model_validate(record["case_map"])
        paragraphs = {item.paragraph_label: item.text for item in authority.passages}
        for annotation in case_map.annotations:
            anchored = [
                {"paragraph_label": label, "text": paragraphs[label]}
                for label in annotation.paragraph_labels
                if label in paragraphs
            ]
            if not anchored:
                raise CandidateIndexError(f"Case Map annotation {annotation.id} has no approved paragraph anchor")
            chunks.append(
                {
                    "chunk_id": f"{authority.citation_key}:{annotation.id}",
                    "citation": authority.citation,
                    "citation_key": authority.citation_key,
                    "case_name": authority.case_name,
                    "court": authority.court,
                    "official_url": authority.official_url,
                    "proposition": annotation.proposition_code,
                    "statement": annotation.statement,
                    "paragraphs": anchored,
                    "limitations": sorted(set(annotation.limitations)),
                    "applicability_factors": sorted(set(annotation.applicability_factors)),
                    "source_role": annotation.annotation_type,
                    "treatment_status": record["treatment_status"],
                    "case_map_version": case_map.version,
                }
            )
    if not chunks:
        raise CandidateIndexError("The approved catalogue contains no Case Map chunks")
    return sorted(chunks, key=lambda item: str(item["chunk_id"]))


def _fit_vectors(chunks: list[dict[str, object]]) -> tuple[TfidfVectorizer, csr_matrix, np.ndarray, np.ndarray]:
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), dtype=np.float64)
    lexical = vectorizer.fit_transform([_chunk_text(item) for item in chunks]).tocsr()
    dimensions = min(64, lexical.shape[0] - 1, lexical.shape[1] - 1)
    if dimensions < 1:
        raise CandidateIndexError("At least two searchable chunks and features are required")
    svd = TruncatedSVD(n_components=dimensions, n_iter=7, random_state=0)
    dense = normalize(svd.fit_transform(lexical))
    return vectorizer, lexical, svd.components_, np.asarray(dense, dtype=np.float64)


def _save_vectors(
    path: Path,
    vectorizer: TfidfVectorizer,
    lexical: csr_matrix,
    svd_components: np.ndarray,
    dense: np.ndarray,
) -> None:
    np.savez_compressed(
        path,
        terms=np.asarray(vectorizer.get_feature_names_out(), dtype=np.str_),
        idf=np.asarray(vectorizer.idf_, dtype=np.float64),
        lexical_data=lexical.data,
        lexical_indices=lexical.indices,
        lexical_indptr=lexical.indptr,
        lexical_shape=np.asarray(lexical.shape, dtype=np.int64),
        svd_components=np.asarray(svd_components, dtype=np.float64),
        dense=np.asarray(dense, dtype=np.float64),
    )


@dataclass(frozen=True)
class _RankedChunk:
    index: int
    lexical: float
    dense: float
    combined: float


class CandidateAuthorityIndex:
    def __init__(
        self,
        *,
        manifest: dict[str, object] | None = None,
        chunks: list[dict[str, object]] | None = None,
        vectorizer: TfidfVectorizer | None = None,
        lexical: csr_matrix | None = None,
        svd_components: np.ndarray | None = None,
        dense: np.ndarray | None = None,
        unavailable_reason: str | None = None,
    ) -> None:
        self.manifest = manifest
        self.chunks = chunks or []
        self.vectorizer = vectorizer
        self.lexical = lexical
        self.svd_components = svd_components
        self.dense = dense
        self.unavailable_reason = unavailable_reason

    @property
    def ready(self) -> bool:
        return all(
            value is not None
            for value in (self.manifest, self.vectorizer, self.lexical, self.svd_components, self.dense)
        ) and bool(self.chunks)

    @classmethod
    def unavailable(cls, reason: str) -> CandidateAuthorityIndex:
        return cls(unavailable_reason=reason)

    @classmethod
    def load_or_unavailable(
        cls,
        catalogue_dir: Path = DEFAULT_CATALOGUE_DIR,
        index_dir: Path = DEFAULT_INDEX_DIR,
    ) -> CandidateAuthorityIndex:
        try:
            return cls.load(catalogue_dir, index_dir)
        except Exception as exc:
            return cls.unavailable(str(exc))

    @classmethod
    def load(cls, catalogue_dir: Path, index_dir: Path) -> CandidateAuthorityIndex:
        manifest_path = index_dir / INDEX_MANIFEST
        chunks_path = index_dir / INDEX_CHUNKS
        vectors_path = index_dir / INDEX_VECTORS
        if not all(path.is_file() for path in (manifest_path, chunks_path, vectors_path)):
            raise CandidateIndexError("The approved candidate index has not been built")
        records = load_catalogue(catalogue_dir, require_ready=True)
        catalogue_manifest = json.loads((catalogue_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        if manifest.get("index_version") != CANDIDATE_INDEX_VERSION:
            raise CandidateIndexError("Candidate index version is unsupported")
        if manifest.get("retrieval_version") != RETRIEVAL_VERSION:
            raise CandidateIndexError("Candidate retrieval version is unsupported")
        if manifest.get("builder_version") != BUILDER_VERSION:
            raise CandidateIndexError("Candidate index builder version is unsupported")
        if manifest.get("authority_count") != 25 or len(records) != 25:
            raise CandidateIndexError("Candidate retrieval requires exactly 25 approved authorities")
        if manifest.get("catalogue_hash") != catalogue_manifest.get("approved_authorities_sha256"):
            raise CandidateIndexError("Candidate index does not match the approved catalogue")
        if manifest.get("chunks_sha256") != _file_hash(chunks_path) or manifest.get("vectors_sha256") != _file_hash(vectors_path):
            raise CandidateIndexError("Candidate index artifact hash mismatch")
        if manifest.get("chunk_count") != len(chunks):
            raise CandidateIndexError("Candidate index chunk count mismatch")
        expected_content_hash = canonical_json_hash(
            {
                "index_version": manifest.get("index_version"),
                "builder_version": manifest.get("builder_version"),
                "catalogue_version": manifest.get("catalogue_version"),
                "catalogue_hash": manifest.get("catalogue_hash"),
                "chunks_sha256": manifest.get("chunks_sha256"),
                "vectors_sha256": manifest.get("vectors_sha256"),
                "retrieval_version": manifest.get("retrieval_version"),
                "display_threshold": manifest.get("display_threshold"),
                "ranking_config": manifest.get("ranking_config"),
                "dimensions": manifest.get("dimensions"),
                "build_dependencies": manifest.get("build_dependencies"),
            }
        )
        if manifest.get("content_hash") != expected_content_hash:
            raise CandidateIndexError("Candidate index content hash mismatch")
        if manifest.get("ranking_config") != RANKING_CONFIG:
            raise CandidateIndexError("Candidate ranking configuration is unsupported")
        if manifest.get("build_dependencies") != {"numpy": np.__version__, "scikit_learn": sklearn.__version__}:
            raise CandidateIndexError("Candidate index dependency versions do not match this runtime")
        threshold = manifest.get("display_threshold")
        if not isinstance(threshold, int | float) or not 0 <= float(threshold) <= 1:
            raise CandidateIndexError("Candidate display threshold is invalid")
        approved_keys = {Authority.model_validate(item["authority"]).citation_key for item in records}
        required_chunk_fields = {
            "chunk_id",
            "citation",
            "citation_key",
            "case_name",
            "court",
            "official_url",
            "statement",
            "paragraphs",
            "limitations",
            "applicability_factors",
            "source_role",
            "treatment_status",
            "case_map_version",
        }
        if any(not isinstance(item, dict) or not required_chunk_fields.issubset(item) for item in chunks):
            raise CandidateIndexError("Candidate index contains an invalid chunk record")
        if any(item.get("citation_key") not in approved_keys for item in chunks):
            raise CandidateIndexError("Candidate index contains an authority outside the approved catalogue")
        expected_chunks = _catalogue_chunks(records)
        if chunks != expected_chunks:
            raise CandidateIndexError("Candidate chunks do not exactly match the approved Case Maps")
        with np.load(vectors_path, allow_pickle=False) as arrays:
            terms = [str(item) for item in arrays["terms"]]
            idf = arrays["idf"].copy()
            lexical_data = arrays["lexical_data"].copy()
            lexical_indices = arrays["lexical_indices"].copy()
            lexical_indptr = arrays["lexical_indptr"].copy()
            shape = tuple(int(item) for item in arrays["lexical_shape"])
            dense = arrays["dense"].copy()
            svd_components = arrays["svd_components"].copy()
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), vocabulary={term: index for index, term in enumerate(terms)})
        vectorizer.idf_ = idf
        lexical = csr_matrix((lexical_data, lexical_indices, lexical_indptr), shape=shape)
        if lexical.shape[0] != len(chunks) or dense.shape[0] != len(chunks):
            raise CandidateIndexError("Candidate vector rows do not match the chunk registry")
        expected_vectorizer, expected_lexical, expected_components, expected_dense = _fit_vectors(expected_chunks)
        if terms != list(expected_vectorizer.get_feature_names_out()) or not np.array_equal(idf, expected_vectorizer.idf_):
            raise CandidateIndexError("Candidate lexical vocabulary does not match the approved chunks")
        if lexical.shape != expected_lexical.shape or (lexical != expected_lexical).nnz:
            raise CandidateIndexError("Candidate lexical vectors do not match the approved chunks")
        if not np.allclose(svd_components, expected_components, rtol=1e-12, atol=1e-12):
            raise CandidateIndexError("Candidate SVD vectors do not match the approved chunks")
        if not np.allclose(dense, expected_dense, rtol=1e-12, atol=1e-12):
            raise CandidateIndexError("Candidate dense vectors do not match the approved chunks")
        if manifest.get("dimensions") != int(svd_components.shape[0]):
            raise CandidateIndexError("Candidate index dimension metadata is invalid")
        return cls(
            manifest=manifest,
            chunks=chunks,
            vectorizer=vectorizer,
            lexical=lexical,
            svd_components=svd_components,
            dense=dense,
        )

    def status(self) -> CandidateIndexStatus:
        if not self.ready:
            return CandidateIndexStatus(status="unavailable", reason=self.unavailable_reason or "Candidate index unavailable")
        assert self.manifest is not None
        return CandidateIndexStatus(
            status="ready",
            catalogue_version=str(self.manifest["catalogue_version"]),
            catalogue_hash=str(self.manifest["catalogue_hash"]),
            index_version=str(self.manifest["index_version"]),
            index_hash=str(self.manifest["content_hash"]),
            retrieval_version=str(self.manifest["retrieval_version"]),
            authority_count=int(self.manifest["authority_count"]),
            chunk_count=int(self.manifest["chunk_count"]),
        )

    def cache_identity(self, audit_mode: str) -> dict[str, object]:
        if audit_mode != "full":
            return {"candidate_search": "not_requested"}
        status = self.status()
        return {
            "candidate_search": status.status,
            "candidate_catalogue_version": status.catalogue_version,
            "candidate_catalogue_hash": status.catalogue_hash,
            "candidate_index_version": status.index_version,
            "candidate_index_hash": status.index_hash,
            "candidate_retrieval_version": status.retrieval_version,
            "candidate_ranking_config": RANKING_CONFIG,
        }

    def _rank(self, query: str, proposition: str | None) -> list[_RankedChunk]:
        if not self.ready:
            return []
        assert self.vectorizer is not None and self.lexical is not None
        assert self.svd_components is not None and self.dense is not None
        query_vector = self.vectorizer.transform([query])
        lexical_scores = cosine_similarity(query_vector, self.lexical).flatten()
        query_dense = normalize(query_vector @ self.svd_components.T)
        dense_scores = _normalise_dense(cosine_similarity(query_dense, self.dense).flatten())
        ranked = []
        for index, chunk in enumerate(self.chunks):
            proposition_score = 1.0 if proposition and chunk.get("proposition") == proposition else 0.0
            combined = (
                LEXICAL_WEIGHT * float(lexical_scores[index])
                + DENSE_WEIGHT * float(dense_scores[index])
                + PROPOSITION_WEIGHT * proposition_score
            )
            ranked.append(
                _RankedChunk(
                    index=index,
                    lexical=float(lexical_scores[index]),
                    dense=float(dense_scores[index]),
                    combined=combined,
                )
            )
        return sorted(ranked, key=lambda item: (-item.combined, str(self.chunks[item.index]["chunk_id"])))

    def search(
        self,
        *,
        audit_mode: str,
        original_question: str | None,
        facts: str | None,
        claims: list[AuditedClaim],
    ) -> CandidateSearchResult:
        if audit_mode != "full":
            return CandidateSearchResult(status="not_requested")
        status = self.status()
        if status.status != "ready":
            return CandidateSearchResult(status="unavailable", unavailable_reason=status.reason)
        eligible = [claim for claim in claims if claim.verdict != "out_of_scope" and claim.requires_authority != "false"]
        cited = {normalise_citation(claim.citation) for claim in claims if claim.citation}
        threshold = float(self.manifest["display_threshold"])  # type: ignore[index]
        aggregate: dict[str, dict[str, object]] = {}
        for claim in eligible:
            query = " ".join(
                item.strip()
                for item in (original_question or "", facts or "", claim.text, claim.proposition.replace("_", " "))
                if item.strip()
            )
            for ranked in self._rank(query, claim.proposition):
                chunk = self.chunks[ranked.index]
                citation_key = str(chunk["citation_key"])
                if citation_key in cited or ranked.combined < threshold:
                    continue
                current = aggregate.get(citation_key)
                if current is None or ranked.combined > float(current["combined"]):
                    claim_orders = set(current["claim_orders"]) if current else set()
                    propositions = set(current["propositions"]) if current else set()
                    claim_orders.add(claim.order)
                    propositions.add(claim.proposition)
                    aggregate[citation_key] = {
                        "chunk": chunk,
                        "lexical": ranked.lexical,
                        "dense": ranked.dense,
                        "combined": ranked.combined,
                        "claim_orders": claim_orders,
                        "propositions": propositions,
                    }
                else:
                    current["claim_orders"].add(claim.order)  # type: ignore[union-attr]
                    current["propositions"].add(claim.proposition)  # type: ignore[union-attr]
        ordered = sorted(aggregate.values(), key=lambda item: (-float(item["combined"]), str(item["chunk"]["citation_key"])))[:MAX_RESULTS]
        leads = []
        for rank, item in enumerate(ordered, start=1):
            chunk = item["chunk"]
            propositions = sorted(item["propositions"])
            leads.append(
                CandidateAuthorityLead(
                    rank=rank,
                    citation=chunk["citation"],
                    citation_key=chunk["citation_key"],
                    case_name=chunk["case_name"],
                    court=chunk["court"],
                    official_url=chunk["official_url"],
                    matched_claim_orders=sorted(item["claim_orders"]),
                    matched_propositions=propositions,
                    paragraphs=[CandidateParagraph.model_validate(value) for value in chunk["paragraphs"]],
                    limitations=chunk["limitations"],
                    source_role=chunk["source_role"],
                    treatment_status=chunk["treatment_status"],
                    lexical_score=round(float(item["lexical"]), 4),
                    dense_score=round(float(item["dense"]), 4),
                    combined_score=round(float(item["combined"]), 4),
                    case_map_version=int(chunk["case_map_version"]),
                    match_rationale=(
                        "The approved catalogue matched the supplied question, facts, and controlled proposition "
                        f"({', '.join(propositions)}). This ranking is a research lead, not a legal conclusion."
                    ),
                )
            )
        return CandidateSearchResult(
            status="complete",
            catalogue_version=status.catalogue_version,
            catalogue_hash=status.catalogue_hash,
            index_version=status.index_version,
            index_hash=status.index_hash,
            retrieval_version=status.retrieval_version,
            searched_claim_count=len(eligible),
            result_count=len(leads),
            candidates=leads,
        )


def _calibration_metrics(index: CandidateAuthorityIndex, queries: list[dict[str, object]], threshold: float) -> dict[str, float]:
    relevant_total = 0
    retrieved_total = 0
    correct_total = 0
    reciprocal_ranks = []
    for fixture in queries:
        expected = {normalise_citation(item) for item in fixture["expected_citations"]}
        ranked = index._rank(_fixture_query(fixture), str(fixture.get("proposition") or ""))
        cited = {normalise_citation(item) for item in fixture.get("cited_citations", [])}
        retrieved = []
        for item in ranked:
            citation_key = index.chunks[item.index]["citation_key"]
            if item.combined < threshold or citation_key in cited or citation_key in retrieved:
                continue
            retrieved.append(citation_key)
            if len(retrieved) == MAX_RESULTS:
                break
        relevant_total += len(expected)
        retrieved_total += len(retrieved)
        correct_total += len(expected.intersection(retrieved))
        first = next((position for position, value in enumerate(retrieved, start=1) if value in expected), None)
        reciprocal_ranks.append(1 / first if first else 0.0)
    return {
        "precision_at_5": correct_total / retrieved_total if retrieved_total else 0.0,
        "recall_at_5": correct_total / relevant_total if relevant_total else 0.0,
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0,
    }


def _fixture_query(fixture: dict[str, object]) -> str:
    return " ".join(
        str(fixture.get(key) or "").strip()
        for key in ("question", "facts", "claim_text", "proposition")
        if str(fixture.get(key) or "").strip()
    )


def _validate_calibration(calibration: object, approved_keys: set[str]) -> list[dict[str, object]]:
    if not isinstance(calibration, dict):
        raise CandidateIndexError("Calibration file must be an object")
    queries = calibration.get("queries")
    if calibration.get("review_status") != "approved" or not calibration.get("reviewer") or not calibration.get("reviewed_at"):
        raise CandidateIndexError("Calibration queries require recorded legal-review approval")
    if not isinstance(queries, list) or len(queries) < MIN_CALIBRATION_QUERIES:
        raise CandidateIndexError("At least 20 reviewed calibration queries are required")
    validated = []
    for fixture in queries:
        if not isinstance(fixture, dict):
            raise CandidateIndexError("Each calibration query must be an object")
        for field in ("question", "facts", "claim_text", "proposition"):
            if not isinstance(fixture.get(field), str) or not str(fixture[field]).strip():
                raise CandidateIndexError(f"Calibration query requires {field}")
        expected = fixture.get("expected_citations")
        if not isinstance(expected, list) or any(not isinstance(item, str) for item in expected):
            raise CandidateIndexError("Calibration expected_citations must be an array of citations")
        expected_keys = {normalise_citation(item) for item in expected}
        if not expected_keys.issubset(approved_keys):
            raise CandidateIndexError("Calibration expected citation is outside the approved catalogue")
        cited = fixture.get("cited_citations", [])
        if not isinstance(cited, list) or any(not isinstance(item, str) for item in cited):
            raise CandidateIndexError("Calibration cited_citations must be an array of citations when supplied")
        validated.append(fixture)
    if not any(fixture["expected_citations"] for fixture in validated):
        raise CandidateIndexError("Calibration requires at least one positive candidate label")
    return validated


def build_candidate_index(catalogue_dir: Path, index_dir: Path, calibration_path: Path) -> dict[str, object]:
    records = load_catalogue(catalogue_dir, require_ready=True)
    if len(records) != 25:
        raise CandidateIndexError("Candidate index builds require exactly 25 approved authorities")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    approved_keys = {Authority.model_validate(item["authority"]).citation_key for item in records}
    queries = _validate_calibration(calibration, approved_keys)
    chunks = _catalogue_chunks(records)
    vectorizer, lexical, svd_components, dense = _fit_vectors(chunks)
    provisional = CandidateAuthorityIndex(
        manifest={"display_threshold": 0.0},
        chunks=chunks,
        vectorizer=vectorizer,
        lexical=lexical,
        svd_components=svd_components,
        dense=dense,
    )
    candidate_thresholds = sorted(
        {
            round(item.combined, 6)
            for fixture in queries
            for item in provisional._rank(_fixture_query(fixture), str(fixture.get("proposition") or ""))
        }
    )
    qualifying = []
    for threshold in candidate_thresholds:
        metrics = _calibration_metrics(provisional, queries, threshold)
        if metrics["precision_at_5"] >= 0.80:
            qualifying.append((threshold, metrics))
    if not qualifying:
        raise CandidateIndexError("Calibration could not achieve 80% candidate precision")
    display_threshold, metrics = min(qualifying, key=lambda item: item[0])
    index_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = index_dir / INDEX_CHUNKS
    vectors_path = index_dir / INDEX_VECTORS
    chunks_path.write_bytes(_json_bytes(chunks))
    _save_vectors(vectors_path, vectorizer, lexical, svd_components, dense)
    catalogue_manifest = json.loads((catalogue_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    dimensions = int(svd_components.shape[0])
    build_dependencies = {"numpy": np.__version__, "scikit_learn": sklearn.__version__}
    content_material = {
        "index_version": CANDIDATE_INDEX_VERSION,
        "builder_version": BUILDER_VERSION,
        "catalogue_version": catalogue_manifest["catalogue_version"],
        "catalogue_hash": catalogue_manifest["approved_authorities_sha256"],
        "chunks_sha256": _file_hash(chunks_path),
        "vectors_sha256": _file_hash(vectors_path),
        "retrieval_version": RETRIEVAL_VERSION,
        "display_threshold": display_threshold,
        "ranking_config": RANKING_CONFIG,
        "dimensions": dimensions,
        "build_dependencies": build_dependencies,
    }
    manifest = {
        "index_version": CANDIDATE_INDEX_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "builder_version": BUILDER_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "catalogue_version": catalogue_manifest["catalogue_version"],
        "catalogue_hash": catalogue_manifest["approved_authorities_sha256"],
        "authority_count": len(records),
        "chunk_count": len(chunks),
        "dimensions": dimensions,
        "ranking_config": RANKING_CONFIG,
        "build_dependencies": build_dependencies,
        "display_threshold": display_threshold,
        "calibration": {
            "fixture_count": len(queries),
            "reviewer": calibration["reviewer"],
            "reviewed_at": calibration["reviewed_at"],
            **{key: round(value, 4) for key, value in metrics.items()},
        },
        "chunks_sha256": content_material["chunks_sha256"],
        "vectors_sha256": content_material["vectors_sha256"],
        "content_hash": canonical_json_hash(content_material),
    }
    (index_dir / INDEX_MANIFEST).write_bytes(_json_bytes(manifest))
    return manifest


def benchmark_candidate_index(index: CandidateAuthorityIndex, calibration: object) -> dict[str, object]:
    if not index.ready or index.manifest is None:
        raise CandidateIndexError("A ready candidate index is required for benchmarking")
    approved_keys = {str(item["citation_key"]) for item in index.chunks}
    queries = _validate_calibration(calibration, approved_keys)
    threshold = float(index.manifest["display_threshold"])
    latencies = []
    for fixture in queries:
        started = time.perf_counter()
        index._rank(_fixture_query(fixture), str(fixture.get("proposition") or ""))
        latencies.append((time.perf_counter() - started) * 1000)
    metrics = _calibration_metrics(index, queries, threshold)
    ordered = sorted(latencies)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "catalogue_version": index.manifest["catalogue_version"],
        "catalogue_hash": index.manifest["catalogue_hash"],
        "index_version": index.manifest["index_version"],
        "index_hash": index.manifest["content_hash"],
        "retrieval_version": index.manifest["retrieval_version"],
        "query_count": len(queries),
        "display_threshold": threshold,
        **{key: round(value, 4) for key, value in metrics.items()},
        "p50_latency_ms": round(statistics.median(ordered), 3),
        "p95_latency_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3),
        "release_gate": {
            "precision_at_5_at_least_80_percent": metrics["precision_at_5"] >= 0.80,
            "p95_under_250ms": ordered[max(0, int(len(ordered) * 0.95) - 1)] < 250,
        },
    }
