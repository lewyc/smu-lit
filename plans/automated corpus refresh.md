# ProofMark: Automated Official-Judgment Corpus Refresh, Freshness, and Re-audit

## Summary

Extend ProofMark into a true legal-AI evaluator with an automated corpus-refresh pipeline for Singapore employment restraint-of-trade judgments.

The MVP will:

- Discover up to 25 relevant official SG Courts judgments from taxonomy-derived searches.
- Fetch, hash, paragraph-split, and AI-annotate those judgments automatically.
- Build an immutable active corpus snapshot used for instant audit-time citation and context checking.
- Display two separate facts for positive evidence: **Officially sourced** and **AI-supported**.
- Reserve the existing six cases for the hand-labelled benchmark gold set only.
- Treat SAL/SLR/LawNet as a future licensed-source connector; do not scrape or ingest its content now.

The system will never let AI-created annotations alone produce the existing `verified` verdict. Machine-discovered evidence can support `context_review`; fake-citation, unsupported, unverified, and out-of-scope rules remain deterministic.

## Implemented operational update

The refresh pipeline below is implemented together with these operational safeguards.

- A local, in-process scheduler starts with FastAPI and runs the capped SG Courts refresh every 24 hours by default. PROOFMARK_REFRESH_INTERVAL_HOURS controls the interval; zero disables it. It waits one interval after application startup, so the refresh CLI and dashboard button remain the immediate pre-pitch options.
- GET /api/v1/corpora/freshness exposes active corpus version, sources-current-as-of timestamp, cached-snapshot state, scheduler status, and latest refresh metadata. Refresh work remains outside normal audit requests.
- Each completed audit stores its immutable corpus version, source timestamp, engine/parser/taxonomy versions, approved currency-register version, and cache outcome.
- Cache reuse requires an exact hash of answer, original question, facts, audit mode, corpus version, engine version, parser version, taxonomy version, and approved currency-register version. A hit becomes a new traceable audit record; user answers are never legal authority, model-training material, or semantic memory.
- An audit is stale when its corpus version or approved organisation-specific currency register differs from the current review context. POST /api/v1/audits/{public_id}/re-audit produces a new linked audit; history is never overwritten.
- Raw answer text is retained for 30 days by default. Expired rows are excluded from retrieval and cache reuse, and an audit owner can delete a saved audit early through DELETE /api/v1/audits/{public_id}. A durable physical-purge worker remains a production requirement before real client material is processed.
- Reviewer/owner-only legal currency records cover later treatment, statutory amendments, and supersession. Gemini cannot create them. Approved negative treatment produces a visible currency signal and lawyer-review flag, and any register change invalidates cached results.
- The migration for audit freshness/cache/retention and legal currency records is in the repository but has not been applied to the hosted Supabase project. Connected-mode persistence needs it deployed after review.

### Implemented API, dashboard, and database behaviour

- Refresh runs only from the scheduler, CLI, or refresh action. An audit never starts a crawl, source fetch, or model call.
- Historical audit output is preserved exactly as run. Staleness is calculated at read time against the active corpus and approved currency register, then the dashboard offers Re-audit latest instead of rewriting prior verdicts.
- The audit report shows cache state, source timestamp, currency-register version, a precise stale-result banner, and the re-audit action.
- Audit cache, retention, and re-audit lineage are persisted with parser version, cache key/status, source timestamp, currency-register version, retention expiry, and parent audit reference.
- Legal currency records use explicit grants and RLS: members can read their organisation records, browser clients cannot write them, and FastAPI validates reviewer/owner membership before server-side persistence.
- Tests cover cache misses for changed source/context/version/review state, distinct public IDs for cache hits, stale/re-audit behaviour, retention-aware lookup, and blocked browser writes to legal currency records.
- The benchmark now has six gold fixtures. The two newer extracts remain subject to legal-team verification before presentation.

## Implementation Changes

### Automated source and corpus pipeline

- Add a versioned Singapore employment-restraint `TopicProfile`, generated from the existing proposition taxonomy rather than a manually selected case list. Its fixed query set covers restraint of trade, restrictive covenants, non-competes, customer connections, trained workforce, scope, and interim injunctions.
- Add replaceable source interfaces:
  - `SourceConnector.discover(profile, limit)` returns candidate official judgment URLs and citations.
  - `SourceConnector.fetch(candidate)` retrieves source HTML with a strict allowlist of SG Courts hosts.
  - `JudgmentExtractor` validates the citation against the document heading, splits numbered paragraphs, and creates SHA-256 hashes.
  - `EvidenceAnnotator` uses Gemini structured output to identify proposition, limitation, outcome direction, confidence, and paragraph labels.
- Implement `SGCourtsConnector` only. It will perform a capped, throttled refresh: maximum 25 judgments, one request per second, bounded retries with backoff, deduplication by normalized citation, and no full-text search or crawling outside the configured result set.
- Do not accept generated passage text from Gemini. Gemini may return only paragraph labels and controlled taxonomy fields; ProofMark copies the evidence text from the extracted official document itself.
- Reject a source candidate if its host is not allowlisted, citation/heading does not match, no numbered paragraphs are extracted, the citation duplicates a prior candidate, or Gemini cites a paragraph not extracted from that judgment.
- Generate an automatic frozen snapshot before the presentation with a CLI refresh command. The live refresh button uses the same pipeline; on source, network, quota, or parsing failure, it retains the most recent successful immutable snapshot and clearly labels it as cached.
- If source terms, robots guidance, or the live search interface prevent reliable automated retrieval, disable live refresh and show the existing generated snapshot rather than silently falling back to SAL/SLR/LawNet material.

### Evidence semantics and audit engine

- Replace the current binary corpus `source_status` model with provenance and assessment metadata:
  - `officially_sourced`: retrieved from a validated SG Courts judgment URL.
  - `ai_supported`: Gemini selected an exact stored paragraph for a controlled proposition.
  - `gold_fixture`: hand-labelled benchmark-only material.
  - `rejected`: discovered material that failed provenance or annotation gates.
- Add provenance metadata to authority and passage records: source host, discovery query, retrieval timestamp, document hash, extractor version, annotation model/version, confidence, and machine-readable limitations.
- Keep the existing verdict taxonomy unchanged. For auto-discovered authority:
  - exact official citation + AI-supported paragraph → `context_review`, with both evidence badges visible;
  - exact official citation but no proposition-linked paragraph → `unsupported`;
  - unresolved citation with recorded official negative check → `likely_fabricated`;
  - unresolved citation without negative proof → `unverified`.
- Keep `verified` available only to benchmark gold fixtures, preventing the product from presenting automated semantic interpretation as legal certainty.
- Precompute TF-IDF vectors once when a corpus snapshot is activated. Audits query the active snapshot only; they never crawl the web or call Gemini during a normal user audit.
- Add annotation disagreement as a safety signal: if local taxonomy classification and Gemini’s controlled proposition differ, retain the passage but force `context_review` and state the disagreement in the handoff.

### Supabase and API

- Extend the declarative Supabase schema with:
  - `corpus_refresh_runs`: source, profile version, trigger time, status, document counts, rejection counts, fallback reason, and duration.
  - provenance/assessment fields on `authorities` and `authority_passages`.
  - a coverage summary per immutable `authority_corpora` version: court level, decision-year band, proposition, and outcome direction.
- Each successful refresh creates a new immutable `authority_corpora` version, inserts only its associated authorities and passages, then atomically marks it active. Older snapshots remain readable for audit reproducibility.
- Apply RLS and explicit grants to refresh metadata and corpus tables: authenticated users may read source/corpus metadata; browser clients have no write access; only the FastAPI service writes refresh results using the server-side secret. This follows Supabase’s requirement to configure both grants and RLS for exposed tables. [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security)
- Add endpoints:
  - `POST /api/v1/corpora/refresh` starts a live SG Courts refresh.
  - `GET /api/v1/corpora/refreshes/latest` returns progress, counts, failure/fallback information, and active snapshot version.
  - Extend `GET /api/v1/corpora` and `GET /api/v1/authorities` with provenance, coverage, and active-version metadata.
- In demo mode, run refresh work in a local background executor with an in-memory job status. In Supabase mode, persist status in `corpus_refresh_runs`. Present PGMQ/stateless workers as the production-scale successor, not as a fake implementation.

### Dashboard and benchmark

- On `/authorities`, add an **AI refresh from SG Courts** action, progress state, active-snapshot timestamp, 25-document cap, fallback banner, and source/annotation badges on every passage.
- On `/audits/:id`, show separate evidence badges: **Official SG Courts source** and **AI-supported proposition**. Show `context_review` for all machine-discovered positive evidence and explain that legal review remains required.
- On `/benchmark`, preserve the six-case gold fixture pack as a separate controlled correctness test. Add:
  - source-provenance rate;
  - citation-heading match rate;
  - annotation disagreement rate;
  - coverage matrix by court level, decision year, proposition, and outcome direction.
- On `/assurance`, replace “four-decision pilot corpus” with the active automated snapshot count and add a future-only `LicensedSourceConnector` for SAL/SLR/LawNet. State that licensed content will be used only where organisational licensing and terms permit private tenant ingestion; no SAL/SLR/LawNet content is fetched in this MVP.
- Frame scalability clearly: refresh is asynchronous and infrequent; normal audits are read-only lookups against a warmed immutable snapshot, enabling horizontally scalable API instances for thousands of daily queries.

## Test Plan

- Use saved, minimal SG Courts-like HTML fixtures to test discovery parsing, heading/citation matching, paragraph extraction, deduplication, hash generation, and rejection of non-allowlisted URLs.
- Test Gemini structured output rejects invented paragraph labels, invalid taxonomy values, invalid confidence, and unavailable/quota-failed requests; all failures retain the last successful frozen snapshot.
- Test that automatically sourced passages can never yield `verified`, while gold fixtures retain their expected classifications.
- Test citation fabrication behavior remains strict: no `likely_fabricated` result without a recorded negative official-registry check.
- Test a mocked 25-judgment refresh produces an immutable corpus version, activates it atomically, and exposes correct coverage metrics.
- Test refresh RLS: anonymous users cannot read or write; authenticated users can read allowed corpus/refresh metadata; browser clients cannot create refreshes or alter extracted authorities/passages.
- Test dashboard loading, progress, live-failure fallback, visible provenance badges, and that pasted audit text survives refresh or session errors.
- Retain the existing 250-run local audit performance batch. Acceptance target remains P95 below 1.5 seconds after the active snapshot is warmed; source refresh latency is reported separately and is not included in audit latency.

## Assumptions and Defaults

- Gemini API access is available through `GEMINI_API_KEY`.
- The live source is limited to SG Courts/eLitigation official judgment pages and a maximum of 25 judgments per refresh.
- A successful automated refresh is run once before the pitch to create the frozen snapshot; presentation mode uses live refresh when available and cached snapshot fallback when not.
- The six selected cases become benchmark gold fixtures only; they are not the active automated runtime corpus. The two newer extracts remain subject to legal-team verification before presentation.
- Licensed SAL/SLR/LawNet material is future architecture only and is never scraped, copied, or indexed in the hackathon MVP.
