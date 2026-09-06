# ProofMark

ProofMark is a 24-hour hackathon MVP for evaluating citation integrity and
evidential grounding in AI-generated Singapore employment restraint-of-trade
answers. It is a pilot evaluation tool, not legal advice and not a comprehensive
case-law database.

## Working vertical slice

```text
Official snapshot -> paragraph-anchored Case Map draft -> lawyer approval
Pasted AI answer + optional question/facts -> parsed legal claims
-> citation, pinpoint, modality, context, currency and omission checks
-> Q1 existence -> Q2 fidelity -> Q3 legal significance -> Q4 completeness
-> gates before configurable weights -> lawyer handoff and feedback review
-> optional Supabase persistence
```

The dashboard runs locally. In `demo` mode it needs no account or cloud
credentials. In `supabase` mode the browser uses Supabase Auth and the FastAPI
service validates the signed-in user before persisting derived results.

## Start locally

Requirements: Node.js 20+, npm, and `uv` with Python 3.12 available.

```powershell
cd api
Copy-Item .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd dashboard
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`, choose **New audit**, load the demonstration
answer, and run it. API documentation is at `http://127.0.0.1:8000/docs`.

For the five VERITAS credibility scenarios, open **Demos 1–5** and select
**Run demos 1–5**. The page executes source-hash validation, case identity,
quote/proposition, judicial-role, and reviewed currency checks, then shows the
one-direction Tier 0–3 trace. Critical and currency-sensitive results enter a
durable local Tier 3 queue. Two different qualified-lawyer decisions are
required before an item can become a gold candidate; the application never
generates a human decision.

Use **Citation only** for the original answer-only flow. Use **Full** to add the
original question and facts; this enables contextual distinctions, issue
omissions, balance prompts, and the weighted four-module score. A total is
withheld whenever a required module (for example reviewed currency data) is
unavailable rather than renormalising incomplete evidence.

The **Case Maps** workbench can generate a draft from any authority in the
active immutable snapshot. Gemini is optional: without a key, the local
fallback creates conservative paragraph-anchored draft records from existing
labels. Exact quotes and paragraph ownership are validated deterministically.
Reviewer corrections create a superseding version; approval never promotes a
runtime result above `context_review`.

Each Case Map annotation carries a field-level provenance envelope: Tier A
(deterministic record facts), Tier B (structurally inferable), or Tier C
(legally judgmental), plus extraction method, confidence, evidence anchors,
version, and human-review state. A model-extracted Tier C field may inform a
review prompt but cannot trigger a hard score gate. The Supabase schema also
contains a reverse dependency index so a future recomputation worker can find
audits that consumed a corrected Case Map field.

Audit reports use the VERITAS five-level failure taxonomy: non-existent
authority, citation substitution, citation fidelity, contextual
mischaracterisation, and synthesis/coverage. The Claim Graph is returned as a
small JSON bipartite graph rather than adding a graph database. Full mode runs
one bounded landmark-candidate comparison and records the corpus, set version,
configuration, independence limitation, and searched-but-not-found list.
This is not independent counter-authority retrieval and does not prove an
answer complete.

All proposed operating figures live in
`api/data/veritas_operating_config.json`. This includes indicative scoring
weights, gate caps, latency targets, Tier 2 sample rate, confidence-band
boundaries, per-band accuracy, and component measurements. A null value means
unmeasured and must render as unmeasured; configured values are not presented
as achieved results. Changing the assurance policy version invalidates the
exact-result cache. Citation, unsupported-assertion, and
approved-currency gates run before weights. Direct contradiction remains
explicitly unassessed because lexical similarity is not Legal NLI. Exact and
whitespace-normalised quotation checks run against stored judgment text only.

The five demo excerpts are short official eLitigation passages with checked
citations, paragraph labels, source URLs, and SHA-256 hashes. Configuration
loading fails loudly if an excerpt, hash, anchor, source host, or referenced
source is missing or changed. Never add a synthetic case name, citation, court
record, treatment, or judgment passage to make a test pass. The fabricated-case
demo uses the Singapore High Court's own redacted labels “Case A” and “Case B”;
ProofMark deliberately does not reproduce the false citations.

Before the first official refresh, the Case Map workbench alone exposes the six
isolated gold judgments as a clearly labelled preprocessing demo source. This
does not populate the normal audit corpus and therefore cannot create a
`verified` runtime result. Once an official snapshot exists, the workbench
automatically uses that snapshot instead.

Text PDFs up to 15 MB can also create user-supplied Case Map drafts. Encrypted,
scanned, malformed, and unnumbered PDFs are rejected. The binary is discarded
after extraction, and a claimed official URL never upgrades its provenance.

## Research catalogue boundary

ProofMark can prepare a separate, offline research catalogue without changing
its audit verdicts. The initial discovery input is
[SG-LegalCite](https://github.com/anonymousmeowmeow/SG-LegalCite), an
independent Singapore legal-citation benchmark released under CC BY 4.0; it is
not an SAL product. Its nearby citation paragraph is discussion in the citing
judgment and its principle field is LLM-extracted. Those fields can nominate a
research lead, but they do not prove the cited authority's ratio, exact
paragraph support, current treatment, or applicability to an AI answer.

The large raw dataset stays outside this repository and is never read during a
user audit. `api/data/research_catalog/v1/` contains only a compact,
versioned, review-gated catalogue. It is currently empty while legal review is
pending and is deliberately not loaded by the active audit corpus. A future
candidate-retrieval feature may show only: **Potentially relevant authority -
requires source and treatment review**. It cannot change a verdict, score or
`verified` status by itself.

Current lexical TF-IDF ranking is narrower: it ranks paragraphs only within an
authority already resolved from the AI answer's citation. Gemini atomises
claims and proposes controlled labels; it does not create a separate fact
record or legal conclusion. Court level is displayed, but declaring an
authority controlling requires lawyer review.

## Create the presentation snapshot

Before the pitch, add either OPENROUTER_API_KEY (recommended) or GEMINI_API_KEY
to api/.env and run this once while the
official SG Courts/eLitigation site is available:

~~~powershell
cd api
uv run python -m app.refresh_cli
~~~

It uses five taxonomy-derived search queries, a strict SG Courts allowlist,
robots guidance, 1 request/second throttling, bounded retries, and a
25-judgment ceiling. Each accepted source must have a matching neutral citation
in its heading and numbered paragraphs. The optional structured model may select only extracted
paragraph labels and controlled taxonomy values; ProofMark copies all displayed
passage text from the official document.

The resulting api/data/frozen_snapshot.json is the immutable local snapshot
used on normal audits. You can also launch the same process from
**Authority inventory -> AI refresh from SG Courts**. Refresh work never happens
during an audit. If network access, source terms, robots guidance, parsing, or
Gemini annotation fails, ProofMark keeps the last successful snapshot and says
that it is cached. Do not claim a live refresh succeeded when the page shows
the fallback banner.

At startup the API validates snapshot counts and hashes, canonical case
identity, official HTTPS hosts, citation/date consistency, unique authority and
paragraph identifiers, monotonically ordered paragraph labels, provenance, and taxonomy
values. An invalid or missing runtime snapshot leaves `/api/v1/health` in
`degraded` state and audit/Case Map endpoints return `503`; benchmark gold
summaries are never substituted for missing official judgment text. A
source-only snapshot is usable for citation and pinpoint existence checks, but
propositional conclusions remain `unverified` until paragraph annotations are
generated and reviewed.

With OpenRouter, use the following local-only values (the OpenRouter key takes
precedence when both providers are configured):

~~~ini
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-3.5-flash-lite
~~~

## Freshness, re-audit, and retention

The API starts an in-process refresh scheduler every 24 hours by default
(PROOFMARK_REFRESH_INTERVAL_HOURS). It performs the same capped source refresh
as the manual button, while audits continue to use the last successful
immutable snapshot. The **Authority inventory** shows the active snapshot time;
every audit report records that exact snapshot version and a **sources current
as of** timestamp.

When a newer snapshot becomes active, a saved report shows a stale-source
banner. Select **Re-audit latest** to make a new linked audit against the
current corpus; ProofMark does not overwrite the historical result. The
in-process scheduler is intentionally an MVP convenience: it resets when the
API process restarts. A durable scheduled job and stateless workers are the
production path.

ProofMark does not use earlier user answers as legal authority, feedback, or
training data. It may reuse an exact result only when this cache key matches:
answer + original question + facts + audit mode + corpus version + engine
version + parser version + taxonomy version + approved currency-register
version + assurance-policy version.

Thus a new source snapshot, engine rule, parser version, question, facts, or
mode, or lawyer-approved currency review creates a cache miss and a full
re-audit. A cache hit is materialised as a new traceable audit, not silently
substituted for an existing report.

In Supabase mode, raw answer text is retained in the protected audit record and
its protected reproducibility payload for 30 days by default
(PROOFMARK_AUDIT_RETENTION_DAYS). Expired audits are excluded from retrieval
and cache reuse; the audit owner can delete one earlier through the API. Before
using real client material, deploy a scheduled maintenance worker to physically
purge expired rows and agree a client-specific retention policy.

Later treatment, supersession, and statutory-amendment records are human-only
review data. Reviewer/owner access is required for the currency-record API;
the model cannot create those records and normal audits remain transparent when
currency has not been reviewed.

## Modes and secrets

- `demo` is the presentation-safe default. It runs the real local FastAPI
  engine and keeps completed audits in process memory.
- `supabase` enables email/password login and durable, tenant-isolated storage.
  Put the browser publishable key in `dashboard/.env`; put the server-side
  secret only in `api/.env`. Never prefix the server key with `VITE_`.
- If the API is offline, the dashboard can open one bundled result clearly
  labelled **Saved demonstration result**. It never presents that result as a
  newly executed audit.

The Supabase schema, metadata-only seed, and pgTAP RLS tests live in
`supabase/`. The seed deliberately contains no judgment passages and no
synthetic negative-registry record. Exact source text must enter through the
hashed official refresh pipeline.

## Connected Supabase setup

For the connected mode, review and apply all migration files in order to
project zxjaccusnmunjgktzkme:

~~~powershell
npx supabase@latest link --project-ref zxjaccusnmunjgktzkme
npx supabase@latest db push
~~~

This requires the project database password and does not require Docker.
Alternatively, run every SQL file in supabase/migrations/ in timestamp order
in the Supabase SQL Editor. The migrations create corpus refresh/provenance,
immutable-content controls, coverage metadata, source-versioned audit cache
and retention fields, reviewer-only legal-currency records, explicit Data API
grants, RLS, and a service-role-only transactional snapshot activator.
Browser clients can read allowed metadata but cannot write refreshes, corpus
content, derived evidence, or verdicts.

## Verification

```powershell
cd api
uv run ruff check .
uv run pytest

cd ..\dashboard
npm run typecheck
npm test -- --run
npm run build

cd ..\api
uv run python -m app.research_catalog_cli validate --catalogue-dir data/research_catalog/v1
```

## Scope boundary

The active corpus covers only Singapore employment restraint-of-trade material
that passed the automated official-source gates. Six selected cases are
isolated as **benchmark gold fixtures only**. They are the sole pathway
to the verified fixture label; an official, AI-supported runtime paragraph can
produce only context_review.

Legacy benchmark proposition text is explicitly typed
`legal_team_summary`, not `judgment_excerpt`, and the dashboard warns that it
is not judgment text. Do not quote those summaries or present their expected
labels as legal conclusions until counsel has checked the linked official
judgments. Secondary journals and articles are metadata only; ProofMark does
not ship or reproduce their text.

SAL, SLR, and LawNet are deliberately excluded from this MVP. A future
LicensedSourceConnector may ingest private tenant material only when the
organisation's licence and terms permit it. PGMQ workers, pgvector,
organisation administration, and deployed worker/API scaling remain production
architecture targets, not silently simulated features.

The VERITAS provenance/dependency migration was hand-authored from the updated
declarative schema because the Supabase CLI was unavailable in this workspace.
It has not been applied to the remote project; review it, then run the normal
migration, RLS-test, and database-advisor workflow.
