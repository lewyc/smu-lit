# ProofMark / VERITAS SG execution brief

## Delivery decision: implement priority Tier 0 now

For this project, **"highest tier for now" means the proposal's highest-priority
Tier 0**, not the numerically highest Tier 3. Tier 0 is the fast, deterministic,
evidence-traceable assurance layer that runs for every audit. Tier 3 is a
human escalation process and cannot be honestly implemented without a bounded
legal-review operation.

The active delivery target is therefore a defensible Tier 0 Singapore
employment restraint-of-trade demo. Tiers 1-3 remain explicitly deferred. Do
not describe a deferred capability as current product behaviour.

## North-star goal

Deliver a pitch-ready, defensible evaluator that answers the first VERITAS
question reliably:

```text
AI answer + supplied question/facts
-> deterministic citation parsing and identity checks
-> official-source/pinpoint/quote checks against a frozen curated snapshot
-> deterministic treatment, court/jurisdiction and modal-language checks
-> evidence-linked per-claim status, uncertainty reason and lawyer handoff
```

Tier 0 establishes whether an answer can safely be relied on for basic
citation and evidence integrity. It does **not** decide ratio, factual fit,
controlling status, completeness, or give legal advice. It must abstain or
send a clear review flag when the curated evidence cannot support a result.

Build its interfaces so they may later become product functions: versioned
evidence, immutable source provenance, tenant-safe data boundaries and
auditable review decisions. Do not claim production infrastructure exists
until it has been deployed and tested.

## VERITAS alignment and boundaries

The proposal's four questions remain the product architecture:

| Question | VERITAS purpose | Current status |
| --- | --- | --- |
| Q1 | Citation existence, identity and pinpoint integrity | **Active: Tier 0** |
| Q2 | Whether cited material entails the proposition | Deferred: Tier 1 constrained retrieval/NLI |
| Q3 | Legal significance, context, authority and calibration | Deferred: Tier 1/2 plus lawyer review |
| Q4 | Whether relevant authority is missing | Deferred: Tier 2 independent retrieval and review |

- Scope is Singapore employment restraint-of-trade law only.
- Primary official judgments and approved paragraph-backed Case Maps are the
  truth layer. Dataset fields, LLM labels, secondary commentary and lexical
  similarity are discovery aids only.
- `verified` is reserved for hand-labelled benchmark-gold fixtures. An official
  runtime source with a possible match can reach at most `context_review`.
- `likely_fabricated` requires a recorded official negative-registry check.
  Unknown citations are `unverified`, never fabricated by guesswork.
- Surface and label court level. Never apply an automatic "SGCA first" rule or
  declare an authority controlling automatically.
- Tier A Case Map fields (identity, court, date, paragraph index, citations and
  statute) may ground deterministic gates. Tier B structural fields are useful
  context but may not gate alone. Tier C legal judgments (ratio, obiter,
  material facts and legal significance) are advisory unless a lawyer has
  specifically reviewed and approved them.
- SG-LegalCite is an independent Singapore legal-citation benchmark, not an
  SAL product. Its citation paragraph is nearby discussion in the *citing*
  judgment and its principle field is LLM-extracted; neither proves the cited
  authority's ratio, exact support or current treatment.

## Current baseline

Already in the repository:

- FastAPI assurance engine, React dashboard, local demo mode and optional
  Supabase persistence.
- Cited-authority TF-IDF: it ranks passages **within an already-resolved
  authority**; it cannot retrieve across authorities.
- SG Courts-only refresh, immutable snapshots, provenance, cached fallback,
  freshness/re-audit handling, Case Map draft/review workflows and currency
  controls.
- A strictly separate, review-gated research-catalogue foundation. It streams
  the raw SG-LegalCite CSV outside the repository and audit runtime, but its
  contents do not affect audit verdicts or scores.
- Supabase schema, RLS policies and dashboard audit/authority/Case Map/
  benchmark/assurance routes.

Completed local engineering checks: Ruff, backend tests, catalogue validation,
TypeScript checks, frontend tests and production build. Local `.env` files are
ignored.

### Tier 0 release evidence status (2026-09-06)

- The deterministic release benchmark is saved at
  `api/data/release_evidence/tier0_v1/benchmark.json`: 13/13 fixtures correct,
  zero trial errors and 1.14 ms P95 over 250 local-parser runs.
- The disposable local Supabase pgTAP suite is saved at
  `api/data/release_evidence/tier0_v1/rls.json`: 14/14 tests passed. Never run
  fixture-writing RLS tests against the shared hosted project.
- A separate `legal_review.json` is required after the snapshot exists. It must
  cover exactly six authorities and explicitly confirm source-role and
  treatment/currency review; a refresh success does not count as legal approval.
- `python -m app.release_cli check` is the fail-closed release gate. It writes
  `api/data/release_evidence/tier0_v1/release_status.json` and remains non-zero
  until the certified snapshot, connected audit record and offline rehearsal
  are present.
- `python -m app.offline_rehearsal_cli` refuses gold fixtures and unreviewed
  data; it can write a rehearsal record only after a certified six-authority
  snapshot is archived.
- The latest official refresh attempt is recorded in
  `api/data/release_evidence/tier0_v1/refresh_attempt.json`. It fell back with
  zero accepted documents because the official source was unavailable. Do not
  create a snapshot from benchmark fixtures or research-catalogue metadata.
- When the source is available, use
  `python -m app.refresh_cli --tier0-target-pack` so the release snapshot is
  restricted to the six approved target identities.
- Tier 0 is not release-complete until a permitted official refresh succeeds,
  a legal reviewer certifies all six sources and evidence roles, one signed-in
  Supabase audit is verified after reload, and the offline rehearsal passes.

Connected Supabase status (project `zxjaccusnmunjgktzkme`): the pre-existing
12-table demo schema was captured read-only and verified against the initial
migration; only that migration was recorded as already applied. Migrations for
official refresh, audit freshness/currency, Case Maps, and Tier 0 integrity
provenance are now applied. Existing demo data was preserved (1 organisation,
1 membership, 4 authorities, 7 passages, 0 audits). A confirmed demo Auth
membership exists. The project is now migration-clean; do not reset it or use
`migration repair` without a new schema comparison. Remaining external
prerequisites are the official frozen refresh, legal approval of source
records/Case Maps, and a deliberate connected-mode RLS/user-journey exercise.

## Active roadmap: Tier 0

### T0.0 - Freeze a curated, offline evidence snapshot

1. Produce one official SG Courts refresh and archive the exact
   `frozen_snapshot.json`, its source hashes, corpus version, timestamp,
   refresh manifest and rejected/failed counts.
2. Create a small case registry with neutral citation, case name, court,
   official URL, document hash and numbered paragraph index.
3. Demonstrate an audit with refresh/network disabled. The UI must state that
   it is using a frozen/cached source.

### T0.1 - Implement deterministic Q1 integrity gates

For every recognised citation, implement and test:

1. citation parsing and canonical citation/case-name/court consistency;
2. official corpus identity/existence lookup;
3. pinpoint existence and exact numbered-paragraph anchoring;
4. exact quote verification when an answer presents text as a quotation;
5. statute reference and court/jurisdiction format checks where curated data
   exists;
6. hand-curated citator/treatment state where it exists; otherwise return an
   explicit unknown/review state, not a treatment conclusion; and
7. deterministic modal parsing (for example, distinguish "may" from "must")
   and a separate unsupported-legal-assertion flag.

Use only records with Tier A evidence for these gates. Keep a machine-readable
reason and source link for every pass, failure, ambiguity and abstention.

### T0.2 - Safe scoring, verdicts and handoff

1. Keep a gate-plus-weight score: critical identity/pinpoint/quote failures
   cap reliability; non-critical signals cannot erase a gate failure.
2. Preserve these conservative states:
   - unknown citation: `unverified`;
   - recorded official negative check: `likely_fabricated`;
   - failed identity, pinpoint or quote: `unsupported`;
   - qualified, limited, stale or incomplete evidence: `context_review`.
3. Render the precise reason, official paragraph/source link, frozen-snapshot
   version, treatment/currency state and a one-minute lawyer-handoff brief.
4. Existing Gemini claim atomisation may prepare a review display, but it is
   not a Tier 0 evidence gate, factual record or legal conclusion. Provide a
   deterministic fallback when it is unavailable.

### T0.3 - Build proof before pitch claims

1. Hand-label a minimum benchmark containing the five proposal failures:
   fabricated citation, real citation/wrong case name, accurate quote without
   legal support, dissent presented as holding, and overruled/negative-
   treatment authority.
2. Add ordinary valid and out-of-scope examples. Record expected per-claim
   gate results, not merely an overall score.
3. Measure citation-identity and pinpoint precision/recall, quote-check
   accuracy, false-positive fabrication rate, per-gate confusion matrix and
   P95 Tier 0 latency. Do not make accuracy claims before measuring them.
4. Rehearse the frozen snapshot path with a prepared answer containing both
   good and bad citations.

### Tier 0 definition of done

- Offline audit works from an archived, traceable official snapshot.
- Every implemented Q1 outcome has deterministic evidence, an explainable
  status and a safe fallback for missing data.
- The benchmark proves the five planted failure modes and reports measured
  quality/latency.
- README, Assurance page and pitch say exactly what Tier 0 checks, and what it
  defers.

## Deferred roadmap: do not build these into the current demo

### Tier 1 - asynchronous, seconds per audit

Deferred: claim graph extraction as a verdict dependency; constrained Case Map
retrieval; Legal NLI/entailment; party-submission versus judicial-holding
classification; warranted-strength/modal-gap evaluation; and precomputed
landmark recall. These may be explored only as non-gating prototypes after
Tier 0 is measured.

### Tier 2 - sampled/escalated, minutes per audit

Deferred: independent cross-authority search, counter-authority and
"potential omission" detection, superseded-by-superior search, factual
distinction work and broad treatment analysis. This corrects the prior
sequencing: cross-authority candidate retrieval is a Tier 2 research workflow,
not the next live MVP feature.

If later enabled, label every result exactly:

> Potentially relevant authority - requires source and treatment review.

It must never alter an audit score, verdict or `verified` status by itself.

### Tier 3 - bounded human review

Deferred: practitioner resolution of uncertain matters, approval of Tier C
fields, authoritative ratio/obiter decisions, material-facts analysis and
contested treatment status. This needs a named legal-review owner, a queue,
review standards and an audit trail before it is represented as available.

### Research catalogue preparation (offline only)

Continue data collection only as a Tier 0 supporting asset: curate up to 25
official restraint-of-trade authorities with hashes, numbered paragraphs,
provenance and lawyer-approved Case Maps. The catalogue is not loaded by
`ActiveCorpusRepository`, never reads raw CSV during an audit and must not be
shown to users until the later Tier 2 workflow has source/treatment review.

## Product-grade expansion path (after the demo)

| Tier 0 now | Later product-grade change |
| --- | --- |
| Frozen JSON snapshot and small case registry | Versioned immutable corpus store with millions of paragraph records, source hashes, retrieval dates and historical snapshots |
| Manual official refresh | Licensed/permitted source connectors, durable ingestion workers, change detection, retries, provenance checks and legal-source contracts |
| In-case TF-IDF as a non-gating aid | Hybrid full-corpus lexical/vector retrieval, reranking and strict evidence validation |
| Tier A deterministic checks | Lawyer-approved Case Maps and deterministic rules for reviewed Tier B/C evidence |
| Local/in-process operations | Queue-backed workers, PostgreSQL/pgvector or search engine, object storage, caches, monitoring and horizontal scaling |
| Demo authentication | Enterprise SSO, tenant isolation, roles, immutable logs, encryption, retention/deletion controls |
| Fixed benchmark | Versioned adversarial suite, review sampling, drift monitoring and model/prompt tracking |
| Basic handoff | Matter-ready report, review tasks and export/API integration |

Advance a feature to product use only after rights/source, evidence, safety,
security, operational and measured-quality gates are met. New domains require
their own permitted sources, taxonomy, expert-reviewed Case Maps, benchmarks
and release decision.

## Current action plan

| Priority | Action | Likely owner | Definition of done |
| --- | --- | --- | --- |
| P0 | Archive an official frozen snapshot and manifest | Engineering + research | Offline audit works; hashes/version/source status visible |
| P0 | Build/complete the Tier 0 case registry and paragraph index | Engineering + legal research | Every demo authority has official URL, hash, court and numbered paragraphs |
| P0 | Finish deterministic Q1 gates and reason codes | Engineering | Identity, pinpoint and quote checks are deterministic and tested |
| P0 | Curate the minimal treatment/negative registry for demo cases | Legal research | Known treatment outcomes have official provenance; all other cases say unknown/review |
| P0 | Create five planted-failure fixtures and measure Tier 0 | QA + legal research | Per-gate expected results, metrics and P95 recorded |
| P0 | Correct README/pitch/Assurance claims to Tier 0 scope | Product + engineering | No overstatement of retrieval, legal certainty or SG-LegalCite affiliation |
| P0 support | Curate 25 review-gated official authorities offline | Legal research + engineering | Catalogue validates but does not enter runtime or UI |
| Deferred Tier 1 | NLI/context/claim-graph verdict features | Engineering + legal review | Start only after Tier 0 exit criteria are met |
| Deferred Tier 2 | Cross-authority retrieval and `potential_omission` workflow | Engineering + legal review | Start only after Tier 1/2 design and lawyer-review protocol are approved |
| Deferred Tier 3 | Human escalation/review operations | Product + legal lead | Start only with staffed reviewer workflow and audit standards |
| Optional infrastructure | Deploy/review Supabase connected mode | Engineering | Migrations applied and migration history reconciled; complete the RLS/user-journey exercise before calling connected mode certified |

## Working rules for contributors and agents

- Read this file and the root README before changing architecture, legal
  claims, data handling, verdict logic or database policy.
- Do not silently broaden scope beyond Singapore employment restraint-of-trade.
- Do not modify raw source snapshots, approved Case Maps or historical audits;
  create versioned superseding records.
- Do not commit credentials, user answers, raw research corpora or unreviewed
  third-party legal text.
- Verify official URLs, neutral citations and numbered paragraph labels before
  presenting evidence as official.
- Keep model roles constrained: models may atomise claims and propose
  controlled labels; deterministic code and human review control evidence,
  verdicts, treatment and legal conclusions.
- Treat all incomplete/missing evidence as `unverified`, `context_review` or a
  clearly worded review state - never as a favourable legal conclusion.
- Update the relevant test and benchmark fixture when altering parser, case
  registry, Case Map, verdict, scoring or RLS behaviour.
- Run the verification commands in README before declaring a change complete.
