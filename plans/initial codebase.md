# ProofMark Initial Codebase Plan

## Summary

Build a working vertical slice in `C:\Users\yikch\Downloads\SMULIT\smu-lit` with three top-level subsystems:

- `dashboard/`: React 19, Vite, TypeScript, Supabase Auth, and a Tech4city-inspired assurance dashboard.
- `api/`: Python 3.12, FastAPI, deterministic legal-audit engine, local TF-IDF evidence ranking, and optional Gemini claim parsing.
- `supabase/`: migrations, RLS policies, indexes, and seed data for the connected backend at `zxjaccusnmunjgktzkme.supabase.co`.

The initial codebase must complete this pipeline:

```text
Pasted AI answer
→ extract legal claims and nearby citations
→ normalise and resolve Singapore neutral citations
→ compare each claim with lawyer-annotated propositions and passages
→ classify it as verified, context review, unsupported, likely fabricated, or unverified
→ calculate transparent audit metrics
→ generate an evidence-linked lawyer handoff
→ persist and display the audit
```

It will cover a bounded Singapore employment restraint-of-trade corpus. It must visibly state that it is a pilot evaluation tool, not a comprehensive case-law database or legal-advice system.

Production-only items—PGMQ workers, pgvector, automated judgment ingestion, organisation administration, and a deployed API—will be represented on the Assurance screen but not implemented in this slice.

## Implementation Changes

### 1. Project foundation and local runtime

- Initialize the dashboard with the same core stack as Tech4city: React/Vite, TypeScript, `@supabase/supabase-js`, Lucide icons, Recharts, Vitest, and pinned dependencies with a committed lockfile.
- Use custom CSS variables and semantic classes instead of a component library. Adapt the Tech4city palette and layout:
  - navy headings and body text;
  - teal for verified evidence;
  - amber for context/human review;
  - coral-red only for strong failure signals;
  - grey for unverified or withheld results;
  - fixed 212px desktop sidebar, mobile drawer, white panels, subtle rules, uppercase eyebrow labels, and generous spacing.
- Create the API as a Python 3.12 `uv` project with FastAPI, Pydantic, Uvicorn, scikit-learn, Supabase Python client, Google GenAI SDK, pytest, and Ruff.
- Provide root documentation and example environment files. Never commit Supabase secret keys, passwords, Gemini keys, or real legal-AI submissions.
- Support two explicit modes:
  - `demo`: local corpus and FastAPI processing, with no login or Supabase dependency;
  - `supabase`: Supabase login and persistence, while the same FastAPI engine performs the audit.
- If FastAPI is unavailable, the dashboard may display one bundled completed audit for pitch continuity, but it must label that result “Saved demonstration result” rather than pretending the pipeline just ran.

### 2. Audit engine

Structure the engine around replaceable interfaces:

- `ClaimParser`: returns atomic claims, citation strings, pinpoints, proposition codes, and parser confidence.
- `CorpusRepository`: supplies the active corpus version, authorities, passages, proposition annotations, and verified negative citation checks.
- `CitationResolver`: performs neutral-citation normalisation and exact lookup.
- `EvidenceMatcher`: identifies passages annotated for the relevant proposition and ranks those passages lexically.
- `VerdictEngine`: applies deterministic classification rules.
- `HandoffBuilder`: creates a structured lawyer-review brief.
- `AuditRepository`: persists and retrieves audits; implement local and Supabase variants.

Implement two claim parsers:

- `LocalClaimParser`, always available:
  - split prose into sentences;
  - detect Singapore neutral citations using a tolerant `[year] SG… number` pattern;
  - associate citations and pinpoints with the nearest claim;
  - map restraint-of-trade phrases to a controlled proposition taxonomy;
  - detect overgeneralising terms such as “always”, “automatically”, and “all non-competes”.
- `GeminiClaimParser`, optional:
  - enabled only when `GEMINI_API_KEY` exists;
  - default to the current stable `gemini-3.5-flash-lite`, configurable through `GEMINI_MODEL`;
  - require structured JSON matching the same Pydantic claim schema;
  - allow Gemini to atomise and categorise claims, but never to choose a verdict or fabricate supporting passages;
  - use a short timeout and fall back immediately to local parsing on quota, network, timeout, or schema errors;
  - record which parser produced each claim.

Google’s current SDK supports Pydantic structured outputs, while free-tier capacity is variable, so this adapter must remain optional. [Gemini structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output) [Gemini rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits)

Define the initial proposition taxonomy as:

- `prima_facie_unenforceable`
- `legitimate_proprietary_interest`
- `reasonableness_between_parties`
- `reasonableness_public_interest`
- `confidential_information`
- `customer_connections`
- `stable_trained_workforce`
- `geographic_scope`
- `duration_scope`
- `activity_scope`
- `interim_injunction_standard`
- `outside_corpus_scope`

Verdict rules:

- `verified`: exact authority exists, the claim maps to a proposition explicitly supported by a stored passage, and no stored limitation is violated.
- `context_review`: authority exists, but the claim overgeneralises, conflicts with a limitation tag, relies on distinguishable facts, or has ambiguous proposition mapping.
- `unsupported`: a legal claim has no citation or its citation does not support the identified proposition.
- `likely_fabricated`: permitted only when the citation has a recorded negative registry check against the official Singapore Courts search, including checker, URL, and timestamp.
- `unverified`: citation or proposition cannot be resolved within the declared pilot corpus.
- `out_of_scope`: claim falls outside Singapore employment restraint-of-trade law.

TF-IDF similarity ranks candidate passages but does not determine truth. Every non-verified result must state what evidence is missing and whether lawyer review is required.

### 3. Corpus, Supabase, and scalability foundations

Seed the first corpus with verified passages and metadata from:

- *Man Financial (S) Pte Ltd v Wong Bark Chuan David* [2007] SGCA 53;
- *CLAAS Medical Centre Pte Ltd v Ng Boon Ching* [2010] SGCA 3;
- *HT SRL v Wee Shuo Woon* [2019] SGHC 96;
- *Shopee Singapore Pte Ltd v Lim Teck Yong* [2024] SGHC 29.

The legal-research team must verify the selected paragraphs, proposition annotations, limitations, case names, court levels, and official URLs before the UI may label anything “Verified.” The seed should contain at least:

- one correctly supported answer;
- one real-but-overgeneralised use of an authority;
- one real citation supporting a different proposition;
- one uncited conclusion;
- one officially checked likely-fabricated citation;
- one out-of-scope answer.

Create the following relational model:

- `organisations` and `organisation_members`: tenant and role membership.
- `authority_corpora`: immutable version, jurisdiction, scope statement, content hash, and active status.
- `authorities`: canonical citation, normalised citation key, case name, court, date, official URL, and source status.
- `authority_passages`: immutable paragraph text, paragraph label, supported propositions, limitations, and lexical-search vector.
- `citation_registry_checks`: existence or non-existence check, official source, checker, and timestamp.
- `audit_runs`: organisation, creator, input, status, corpus version, engine version, parser mode, timings, and summary metrics.
- `audit_claims`: ordered claim, citation, proposition, parser confidence, verdict, rationale, and escalation requirement.
- `claim_evidence`: claim-to-passage relation, support type, ranking score, and evidence explanation.
- `handoff_briefs`: issue, established facts, relevant authorities, unresolved question, and review status.
- `audit_events`: append-only lifecycle and failure events.
- `benchmark_runs`: fixture count, verdict accuracy, P50/P95 latency, cache-hit rate, and engine/corpus versions.

Use `bigint generated identity` for internal primary keys, UUIDs only for external audit references and `auth.users` references, `timestamptz` for timestamps, foreign keys with indexes, and check constraints for statuses and confidence ranges.

Add indexes for the actual access paths:

- unique corpus-version plus normalised citation;
- authority plus paragraph label;
- organisation plus descending audit creation time;
- audit run plus claim order;
- claim plus evidence relation;
- partial index for queued/running audit runs;
- GIN index for passage full-text search.

Apply RLS and explicit grants to every exposed table:

- no anonymous table access;
- authenticated users may read only audits belonging to an organisation in which they are members;
- authenticated clients may not directly insert or alter derived claims, evidence, handoffs, events, or benchmark results;
- the FastAPI service validates the Supabase bearer token and membership before using its server-side secret to persist derived results;
- authority tables are authenticated read-only;
- RLS tests must cover both allowed same-organisation access and denied cross-organisation access.

Supabase now distinguishes Data API exposure from RLS, so the migration must explicitly configure both rather than assume new tables are exposed. [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security) [Supabase breaking-change index](https://supabase.com/changelog?types=breaking-change)

Keep the initial audit synchronous. Preserve `queued`, `running`, `complete`, and `failed` states so the production architecture can later replace synchronous execution with Supabase Queues and stateless workers. Edge Functions should remain an architecture item for lightweight orchestration; Supabase recommends moving long-running work to background workers. [Supabase Edge Functions](https://supabase.com/docs/guides/functions) [Supabase Queues](https://supabase.com/docs/guides/queues)

### 4. User interface and public interfaces

Implement these dashboard routes:

- `/audits`: audit worklist, filters, source status, summary metrics, and “New audit”.
- `/audits/new`: answer input, corpus selector fixed to the active pilot corpus, parser-mode selector, and seeded-example loader.
- `/audits/:id`: claim evidence rail, expandable exact passages, audit metrics, provenance, and lawyer handoff.
- `/authorities`: searchable corpus inventory and paragraph annotations.
- `/benchmark`: run the fixed fixture pack and display correctness and measured latency.
- `/assurance`: intended use, prohibited uses, corpus boundary, parser fallback, versioning, human accountability, and current-versus-future architecture.
- `/login`: connected-mode email/password login only; omitted in demo mode.

Frontend repository contract:

```ts
interface AuditRepository {
  listAudits(filters?: AuditFilters): Promise<AuditSummary[]>;
  getAudit(publicId: string): Promise<AuditDetail>;
  submitAudit(input: AuditSubmission): Promise<AuditDetail>;
  runBenchmark(): Promise<BenchmarkResult>;
}
```

Core shared types:

```ts
type ParserMode = 'auto' | 'local' | 'gemini';

type AuditVerdict =
  | 'verified'
  | 'context_review'
  | 'unsupported'
  | 'likely_fabricated'
  | 'unverified'
  | 'out_of_scope';

type EvidenceRelation = 'supports' | 'limits' | 'contradicts' | 'unresolved';
```

FastAPI endpoints:

- `GET /api/v1/health`: engine, corpus, Supabase, and Gemini availability without leaking secrets.
- `GET /api/v1/corpora`: available corpus metadata and limitations.
- `POST /api/v1/audits`: validate a maximum 20,000-character answer, execute the audit, optionally persist it, and return the complete result.
- `GET /api/v1/audits/{public_id}`: connected-mode retrieval after ownership validation.
- `POST /api/v1/benchmarks/run`: execute the fixed quality fixtures plus a separate performance batch.
- `GET /api/v1/assurance`: engine version, taxonomy version, decision rules, limits, and production architecture.

Audit response must always include:

- engine, corpus, and parser versions;
- parser actually used and fallback reason;
- processing duration;
- summary counts;
- citation-integrity, grounded-coverage, and contextual-support metrics;
- ordered claims with exact verdict rationale;
- source passages copied only from the stored corpus;
- handoff brief when any claim is not verified.

### 5. Test Plan and Acceptance Criteria

Backend unit and API tests:

- Extract multiple claims and citations from the seeded answer.
- Normalise spacing and case variations in neutral citations.
- Resolve all four seeded authorities exactly.
- Produce `verified` only from explicitly annotated supporting propositions.
- Flag a real-but-overgeneralised authority as `context_review`.
- Never call an unknown citation fabricated without a negative registry record.
- Classify uncited legal conclusions as `unsupported`.
- Withhold out-of-scope claims.
- Fall back to local parsing when Gemini is absent, times out, returns `429`, or violates the output schema.
- Confirm Gemini output cannot supply or override verdicts.
- Ensure handoff briefs contain claim, authority, passage, established point, and unresolved question.
- Reject empty and over-limit submissions without persisting partial audits.
- Avoid logging raw submitted answers.

Database tests:

- Anonymous users cannot access application tables.
- User A can read their organisation’s audit but not User B’s.
- Authenticated browser clients cannot mutate derived verdicts or evidence.
- Service-side writes retain the verified creator and organisation.
- Corpus versions and passages cannot be overwritten after use.
- Every foreign key used in reads or RLS has an index.

Frontend tests:

- Demo mode loads without Supabase credentials.
- Connected mode never silently falls back to demo data.
- Running the seeded audit renders all expected verdict categories.
- Clicking a claim reveals its exact paragraph and source URL.
- Status is communicated by icon and text, not colour alone.
- Assurance limitations remain visible on desktop and mobile.
- Supabase/session errors produce a recoverable message without losing pasted text.

End-to-end acceptance:

- On a clean laptop, two documented commands start FastAPI and the Vite dashboard.
- “Load demonstration answer” followed by “Run audit” produces a complete evidence-linked report.
- Connected mode saves the audit to the supplied Supabase project and still shows it after refresh.
- Removing `GEMINI_API_KEY` does not break or materially alter the seeded verdicts.
- The hand-labelled benchmark fixtures achieve 100% expected classifications; this is described as fixture correctness, not general legal accuracy.
- A separate 250-run performance batch completes without errors and reports measured P50/P95 timings; target local API P95 is below 1.5 seconds after corpus warm-up.
- `npm run typecheck`, frontend tests, production build, Ruff, and pytest all pass.
- No secret, real client data, unsupported legal conclusion, or invented authority appears in the repository or UI.

## Assumptions and Defaults

- The repository begins from its current clean initial commit containing only `README.md`.
- The presentation runs the React dashboard and FastAPI service locally.
- Demo mode is the default presentation path; Supabase mode demonstrates persistence and multi-tenant architecture.
- Python 3.12 is used because it is already installed and has broader ML-package compatibility than the machine’s default Python 3.14.
- The user will place the Supabase publishable and server-side secret keys in ignored local environment files and create or authorize a demo Auth account.
- The official Supabase project URL is `https://zxjaccusnmunjgktzkme.supabase.co`.
- No client uploads, PDF ingestion, live legal-database crawling, pgvector, queue worker, model-training pipeline, or automated legal-opinion generation is included in the initial codebase.
