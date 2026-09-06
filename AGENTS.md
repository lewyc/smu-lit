# ProofMark execution brief

## North-star goal

Deliver a pitch-ready, defensible Singapore employment restraint-of-trade
evaluation demo that can complete this loop from a frozen local snapshot:

```text
AI answer + supplied question/facts
-> atomised legal claims and controlled propositions
-> deterministic citation and pinpoint checks
-> approved official-paragraph Case Map evidence check
-> optional offline candidate-authority retrieval
-> conservative verdicts, review flags, and a one-minute lawyer handoff
```

The stretch outcome is not an autonomous legal-research system. It is a
traceable evaluator that can identify both unsupported AI claims and
*potentially relevant authorities requiring lawyer review*. A lawyer remains
responsible for controlling status, factual fit, current treatment, and legal
advice.

Build the MVP so its useful functions can graduate into a real product: retain
clear interfaces, versioned evidence, tenant-safe data boundaries and auditable
review decisions. Do not claim that production infrastructure exists until it
is deployed and tested.

## Product truth: preserve these boundaries

- Scope is Singapore employment restraint-of-trade law only.
- An official runtime source, even with an AI-supported paragraph, can reach
  at most `context_review`. `verified` is reserved for hand-labelled,
  benchmark-gold fixtures.
- `likely_fabricated` requires a recorded official negative-registry check;
  unknown citations are `unverified`, not fabricated.
- Candidate retrieval discovers research leads. It must not alter a verdict,
  score, or `verified` status by itself.
- Describe every retrieved lead as **Potentially relevant authority — requires
  source and treatment review**. Never call it an omitted, controlling, or
  supporting authority until human review has established that.
- Surface and label court level; do not apply a simplistic "SGCA first" rule
  or declare any authority controlling automatically.
- Primary official judgments and approved, paragraph-backed Case Maps are the
  truth layer. Dataset fields, LLM labels, secondary commentary, and lexical
  similarity are discovery aids only.
- SG-LegalCite is an independent Singapore legal-citation benchmark, not an
  SAL product. Its citation paragraph is nearby discussion in the *citing*
  judgment and its principle field is LLM-extracted; neither proves the cited
  authority's ratio, exact support, or current treatment.

## Current baseline

Already implemented in the repository:

- FastAPI citation-assurance engine, React dashboard, local demo mode and
  optional Supabase persistence.
- Cited-authority paragraph ranking: TF-IDF ranks passages **within an
  already-resolved cited authority**. It does not retrieve across authorities.
- A separate offline TF-IDF/SVD candidate index is implemented for Full audits.
  It remains unavailable until exactly 25 officially sourced authorities,
  approved Case Maps, and reviewed calibration queries pass the release gate.
  Its research leads never alter verdicts, evidence, gates, or scores.
- SG Courts-only automated refresh, immutable snapshots, provenance,
  background refresh, cached fallback, freshness and re-audit handling.
- Case Map draft generation, text-PDF import, reviewer correction/approval,
  feedback, context/modality/pinpoint checks, and currency-review controls.
- Supabase schema, RLS policies and migrations; dashboard routes for audit,
  authority, Case Map, benchmark and assurance workflows.

Not yet demonstrated locally in this workspace:

- `uv`, dashboard dependencies, and local `.env` files are absent, so the
  documented backend/frontend checks have not been run here.
- No `api/data/frozen_snapshot.json` exists yet.
- Supabase migrations still require project-owner and legal-review approval
  before connected-mode deployment.

## Roadmap

### Phase 0 — Baseline and honest product language

1. Install the documented Python/Node dependencies and run Ruff, pytest,
   TypeScript checks, frontend tests and production build.
2. Configure local demo environment files without committing secrets.
3. Update README, Assurance page and pitch material to distinguish:
   - current cited-authority validation;
   - proposed cross-authority candidate retrieval; and
   - lawyer-reviewed legal conclusions.
4. Run one official refresh with a configured Gemini key and preserve the
   resulting frozen snapshot for presentation fallback.

**Exit criteria:** reproducible local demo; all checks pass; no pitch wording
claims that candidate discovery is legal verification.

### Phase 1 — Acquire and curate offline research data

1. Confirm licences, terms, permitted reuse and dataset version for every
   research source before use. Record source, date, licence/terms reference,
   download hash and owner in a manifest.
2. Keep the raw SG-LegalCite corpus outside this Git repository and outside
   user-audit runtime. Do not commit its roughly 1 GB CSV or query it live.
3. Build a versioned offline import/filter script that identifies
   restraint-of-trade candidates from SG-LegalCite and any other permitted
   research metadata.
4. Begin with 25 high-quality candidates, not broad coverage. For every
   retained candidate, retrieve the official SG Courts judgment and validate
   citation, court, URL, date, document hash and numbered paragraphs.
5. Have legal reviewers create or approve a Case Map for each retained
   authority: exact paragraphs, controlled propositions, limitations,
   factual distinctions, authority-role label, source provenance and treatment
   status.
6. Export only a compact, versioned, derived candidate snapshot suitable for
   local demo use.

**Exit criteria:** a documented, legally reviewable curated authority set;
each displayable candidate has an official source and evidence status.

### Phase 2 — Cross-authority candidate retrieval

1. Populate and legally approve the 25-authority catalogue required by the
   implemented pre-built hybrid candidate index.
2. Query it using supplied question/facts plus the extracted controlled
   proposition. Do not treat Gemini output as a factual record; it atomises
   claims and assigns controlled fields.
3. Return the top 3–5 results with match rationale, court level, provenance,
   Case Map status and the mandatory research-lead label.
4. Keep this path separate from existing cited-authority TF-IDF ranking and
   from the deterministic verdict rules.
5. Keep retrieved leads separate from the existing static `potential_omission`
   checklist flag and from every conclusion or score calculation.

**Exit criteria:** the implemented retrieval path has a legally approved index,
reviewed calibration pack, Precision@5/Recall@5/MRR evidence, and fast offline
candidate suggestions that cannot be mistaken for verified support or advice.

### Phase 3 — Runtime evidence and review integration

1. Ensure normal audits read only approved, paragraph-backed Case Map
   annotations when assessing proposition support, limitations, factual fit,
   authority role and provenance.
2. Maintain the current verdict policy:
   - unknown citation: `unverified`;
   - recorded official negative check: `likely_fabricated`;
   - failed pinpoint or proposition: `unsupported`;
   - qualified, limited or fact-sensitive support: `context_review`.
3. Expose currency/treatment state as a review signal. Unreviewed or negative
   treatment must trigger transparency and lawyer review, not an invented
   legal conclusion.
4. Preserve immutable snapshots, Case Map revisions and audit history.

**Exit criteria:** every verdict and flag links to a traceable source,
paragraph, version and review state.

### Phase 4 — Evaluation, UX and pitch freeze

1. Build 15–20 hostile, hand-labelled audit examples spanning fabricated and
   malformed citations, wrong court code, wrong pinpoint, wrong proposition,
   overstatement, limiting authority, candidate omission and out-of-scope use.
2. Measure evaluator quality: citation-identity accuracy, pinpoint accuracy,
   contextual-support precision, wording/calibration accuracy, false-positive
   fabrication rate and P95 audit latency.
3. Measure retrieval separately with Recall@5 and MRR. Good retrieval must
   never be described as legal correctness.
4. Polish one audit-detail journey: overall result, per-claim explanation,
   exact official paragraph, review reason, candidate leads, lawyer handoff,
   corpus freshness and provenance badges.
5. Run 250 warmed audits against the frozen snapshot; retain the P95 target
   below 1.5 seconds. Rehearse without live eLitigation, Gemini or Supabase.

**Exit criteria:** a one-minute, offline-safe demo with measured performance,
clear safety explanations and repeatable expected results.

### Phase 5 — After the hackathon

- Durable scheduler/workers and physical retention purge.
- Deployed Supabase connected mode, production observability and organisation
  administration.
- Broader, licensed sources only when organisational licence and terms permit.
- More legal domains only after independent corpus, benchmark and review plans.

Do not spend MVP time on model fine-tuning, a 7B legal model, live full-corpus
search, broad multi-domain coverage, automated legal conclusions or training
on user submissions.

## Product-grade expansion path

The MVP is a safe, local proof of the workflow. The following are deliberate
upgrade paths for turning the same workflow into a real product. They are not
current product claims and should be sequenced only after legal, licensing,
security and operational readiness reviews.

| MVP now | Product-grade change |
| --- | --- |
| Six gold fixtures plus a small frozen JSON snapshot | Versioned, immutable corpus store with millions of paragraph records, source hashes, retrieval dates and historical snapshots |
| Manual/eLitigation refresh capped at 25 cases | Licensed and permitted source connectors, durable ingestion workers, change detection, retries, provenance checks and legal-source contracts |
| TF-IDF within a cited case | Hybrid full-corpus search: lexical retrieval, vector retrieval, reranking, then strict citation/pinpoint validation |
| Gemini labels selected paragraphs | LLM output remains a proposal; lawyer-reviewed Case Maps and deterministic rules determine product verdicts |
| In-process scheduler and local memory | Queue-backed workers, Postgres/pgvector or a search engine, object storage, caches, monitoring and horizontally scalable APIs |
| Demo authentication | Enterprise SSO, tenant isolation, lawyer/reviewer/admin roles, immutable audit logs, encryption, retention and deletion controls |
| Fixed test fixtures | Continuously versioned benchmarks, adversarial tests, human-review sampling, drift monitoring, and model/prompt version tracking |
| `potential_omission` prototype | Formal research workflow: candidate authority, relevance explanation, authority hierarchy, treatment status and lawyer disposition |
| Basic handoff | Matter-ready report with source excerpts, exact pinpoints, uncertainty reasons, review tasks, and export/API integration |

### Product-readiness gates

Advance an MVP feature to product use only when all of these gates are met:

1. **Rights and source gate:** documented licence/terms, source contract where
   required, provenance manifest and permitted retention/use.
2. **Evidence gate:** official primary-source record, exact paragraph anchors,
   reviewed Case Map, authority/treatment metadata and immutable version.
3. **Safety gate:** deterministic fallback behaviour, no unsupported legal
   conclusion, clear uncertainty/review messaging and adversarial test coverage.
4. **Security gate:** authenticated tenant boundary, role checks, audit logs,
   encryption and tested retention/deletion controls.
5. **Operational gate:** durable job processing, monitoring, backups, error
   handling, capacity testing, incident ownership and documented recovery.
6. **Quality gate:** benchmark thresholds, reviewed error samples, false-positive
   monitoring and model/prompt/data-version traceability.

### Product roadmap beyond the demo

1. **Data platform:** move compact snapshots into a versioned corpus service;
   add permitted source connectors and document-level change detection.
2. **Retrieval platform:** introduce hybrid lexical/vector retrieval and
   reranking across the approved corpus, while retaining exact evidence and
   pinpoint checks as the final gate.
3. **Review operations:** provide reviewer queues, Case Map lifecycle tools,
   treatment/currency review, assignment, disposition and immutable audit logs.
4. **Enterprise deployment:** add SSO, organisation administration, least-
   privilege roles, encryption, data-residency decisions, retention/deletion
   operations and export/API integrations.
5. **Continuous assurance:** version datasets, rules and prompts; run
   regression/adversarial tests, measure drift and sample live outputs for
   human quality review.
6. **Domain expansion:** add new legal domains only as independent launches
   with their own permitted sources, taxonomy, expert-reviewed Case Maps,
   benchmarks and release gates.

## Current action plan

| Priority | Action | Likely owner | Definition of done |
| --- | --- | --- | --- |
| P0 | Set up `uv`, Node dependencies and local environment files | Engineering | All documented checks run locally; no secrets committed |
| P0 | Produce and archive a frozen official snapshot | Engineering + research | `frozen_snapshot.json` exists; dashboard works with network unavailable |
| P0 | Legal sign-off on the six gold fixtures and Case Map labels | Legal research/counsel | Approved source paragraphs, limitations and expected benchmark labels |
| P0 | Correct README/pitch/Assurance claims | Product + engineering | No SAL affiliation error; discovery and verification are clearly separated |
| P1 | Create data-source manifest and curated candidate-selection protocol | Research lead | Licences, hashes, source provenance and reviewer status recorded |
| P1 | Curate first 25 official, restraint-of-trade authorities | Legal research + engineering | Official source and approved/queued Case Map for every candidate |
| P1 | Approve and build the compact candidate-index artifact | Engineering + legal review | Exactly 25 approved records and 20 reviewed queries produce a versioned offline index |
| P1 | Certify top-5 candidate retrieval | Engineering + legal review | Precision@5/Recall@5/MRR recorded; no candidate changes a score or verdict |
| P2 | Expand hostile benchmark and collect quality metrics | QA + legal research | 15–20 reviewed examples; retrieval and evaluator metrics reported separately |
| P2 | Polish one audit-detail pitch flow and rehearse it | Product + design | One-minute, frozen-snapshot demo with good and bad citations |
| Optional | Deploy/review Supabase connected mode | Project owner + engineering | Migrations/RLS reviewed, applied and exercised with demo users |

## Working rules for contributors and agents

- Read this file and the root README before changing architecture, legal claims,
  data handling, verdict logic or database policy.
- Do not silently broaden scope beyond Singapore employment restraint-of-trade.
- Do not modify raw source snapshots, approved Case Maps or historical audits;
  create versioned superseding records.
- Do not commit credentials, user answers, raw research corpora or unreviewed
  third-party legal text.
- Verify official URLs, neutral citations and numbered paragraph labels before
  presenting evidence as official.
- Never fabricate or alter a case name, citation, court, paragraph, URL,
  treatment record or judgment text to make a test or demonstration pass.
  Synthetic legal authorities must not appear in the corpus or legal fixtures.
- Fail loudly when required corpus data, source hashes, paragraph anchors,
  reviewed treatment records or human decisions are missing. Do not generate
  substitute legal content, weaken an expected result or add a fabricated
  fixture to conceal the missing evidence.
- Keep model roles constrained: models may atomise claims and propose controlled
  labels; deterministic code and human review control evidence, verdicts,
  treatment and legal conclusions.
- Update the relevant test and benchmark fixture when altering parser, taxonomy,
  retrieval, Case Map, verdict or RLS behaviour.
- Run the verification commands in README before declaring a change complete.
