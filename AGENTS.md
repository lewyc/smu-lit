# ProofMark / VERITAS SG execution brief

## Delivery decision: implement Tier 0 and a bounded Tier 1 demo now

For this project, the current demo target is a complete Tier 0 foundation plus
a bounded, non-gating Tier 1 contextual-review path. Tier 1 is allowed in the
demo only over the legally reviewed 25-authority catalogue and its approved
paragraph-backed Case Maps. The broader 78-case research queue remains offline
discovery data until each record has an official source, hash, pinpointable
paragraphs and legal approval.

Tier 2 independent cross-authority omission retrieval and Tier 3 staffed legal
escalation remain deferred. Do not describe either deferred capability as
current product behaviour, and do not present Tier 1 review prompts as proof of
entailment, completeness, controlling status or legal correctness.

## North-star goal

Deliver a pitch-ready, defensible evaluator that answers the first VERITAS
question reliably:

```text
AI answer + supplied question/facts
-> deterministic citation parsing and identity checks
-> official-source/pinpoint/quote checks against a frozen curated snapshot
-> deterministic treatment, court/jurisdiction and modal-language checks
-> Tier 1 curated Case Map/context checks over approved authorities
-> evidence-linked per-claim status, uncertainty reason and lawyer handoff
```

Tier 0 establishes basic citation and evidence integrity. Tier 1 adds a
bounded contextual review signal over approved Case Maps; it does **not** decide
ratio, factual fit, controlling status, completeness, or give legal advice. Both
tiers must abstain or send a clear review flag when the curated evidence cannot
support a result.

Build its interfaces so they may later become product functions: versioned
evidence, immutable source provenance, tenant-safe data boundaries and
auditable review decisions. Do not claim production infrastructure exists
until it has been deployed and tested.

## VERITAS alignment and boundaries

The proposal's four questions remain the product architecture:

| Question | VERITAS purpose | Current status |
| --- | --- | --- |
| Q1 | Citation existence, identity and pinpoint integrity | **Active: Tier 0** |
| Q2 | Whether cited material entails the proposition | **Active for demo: Tier 1 constrained retrieval/review** |
| Q3 | Legal significance, context, authority and calibration | **Bounded Tier 1 review prompts; legal conclusion deferred** |
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

## Active roadmap: Tier 1 demo over the reviewed 25-authority catalogue

Tier 1 is the next demo milestone after the Tier 0 release gates are stable.
It is a constrained contextual-review workflow, not an automatic legal-answer
engine. New Tier 1 work must use a separate, versioned catalogue/index and
must not silently replace the six-authority Tier 0 snapshot.

### T1.0 - Approve and load the demo catalogue

1. Complete legal review for the selected 25 authorities: official URL,
   citation identity, court/date, document hash, numbered paragraphs, source
   role, treatment/currency and approved Case Map evidence.
2. Add a catalogue validator and immutable catalogue version. The active Tier
   0 corpus remains unchanged; Tier 1 reads the approved catalogue through an
   explicit research/context repository.
3. Keep the 78-case queue outside user-audit runtime. It may be used for
   offline discovery and shadow evaluation, but not for proof, verdicts or
   omission claims until separately sourced and approved.

### T1.1 - Add constrained contextual review

1. Atomise each answer into claims, citations, pinpoints, propositions and
   modality; keep model output as a proposal, never as evidence.
2. Retrieve only approved paragraph-backed Case Map evidence from the 25-case
   catalogue, using facts plus the controlled proposition as the query.
3. Compare proposition, limitations, factual distinctions and authority role.
   Use deterministic rules and lawyer-reviewed labels; Legal NLI may provide a
   review signal but cannot create a `verified` result.
4. Emit explainable `context_review` reasons such as qualified support,
   source-role uncertainty, factual mismatch or insufficient approved
   evidence. Preserve Tier 0 identity/pinpoint/quote gates as hard gates.

### T1.2 - Demo UX and benchmark

1. Add an explicit Tier 1 demo mode or review panel, clearly labelled as
   contextual review and requiring lawyer confirmation.
2. Show evidence paragraphs, limitations, source role, treatment state,
   catalogue version and uncertainty reasons in the handoff.
3. Extend the adversarial benchmark with proposition mismatch, qualified
   language, factual distinction, party submission/obiter and source-provenance
   cases. Report contextual-support precision, review-flag recall and P95
   latency separately from Tier 0 citation metrics.
4. Keep Tier 1 failures conservative: they may cap or route to review, but may
   not promote an ordinary runtime record to `verified`.

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

The 25-authority catalogue is now the Tier 1 demo target once legal review is
complete. It remains separate from `ActiveCorpusRepository`, never reads raw
CSV during an audit and must be versioned independently from the Tier 0
snapshot. The 78-case queue remains a research backlog/shadow index and is not
shown as proof or as an omitted-authority finding.

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
| P0 | Correct README/pitch/Assurance claims to Tier 0/Tier 1 scope | Product + engineering | No overstatement of retrieval, legal certainty or SG-LegalCite affiliation |
| P1 | Approve and version the 25-authority Tier 1 catalogue | Legal research + engineering | Every record has official source, hash, numbered evidence, approved Case Map and reviewer metadata |
| P1 | Build constrained Tier 1 context/retrieval path | Engineering + legal review | Approved catalogue evidence produces explainable `context_review` prompts without changing Tier 0 identity gates |
| P1 | Add Tier 1 demo panel and contextual benchmark | Product + QA | Evidence, limitations, source role, treatment and uncertainty are visible; contextual metrics are recorded separately |
| P1 support | Maintain the 78-case research queue offline | Legal research + engineering | Queue remains metadata-only/shadow retrieval and cannot create proof, omission flags or `verified` results |
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
