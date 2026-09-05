# ProofMark

ProofMark is a 24-hour hackathon MVP for evaluating citation integrity and
evidential grounding in AI-generated Singapore employment restraint-of-trade
answers. It is a pilot evaluation tool, not legal advice and not a comprehensive
case-law database.

## Working vertical slice

```text
Official snapshot -> paragraph-anchored Case Map draft -> lawyer approval
Pasted AI answer -> parsed legal claims
-> Tier 0 citation identity, pinpoint, direct-quote, source-role, modality and treatment checks
-> deterministic statuses and evidence gates -> lawyer handoff and feedback review
-> deferred VERITAS Q2-Q4 research paths remain non-gating
-> optional Supabase persistence
```

The dashboard runs locally. In `demo` mode it needs no account or cloud
credentials. In `supabase` mode the browser uses Supabase Auth and the FastAPI
service validates the signed-in user before persisting derived results.

The dashboard uses same-origin `/api` requests by default. Vite proxies those
requests to `127.0.0.1:8000` during local development, so a Cloudflare tunnel
in front of the dashboard also reaches the API as long as FastAPI is running on
the same host. For a separately hosted API, set `VITE_API_URL` before starting
or building the dashboard and add the dashboard origin to
`PROOFMARK_CORS_ORIGINS`.

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

The current release accepts **Citation only** audits. It checks deterministic
citation integrity only: neutral citation/case identity, numbered pinpoints,
direct quotes, reviewer-labelled source role, approved treatment status and
modal wording. It does not assess factual fit, ratio, legal significance,
entailment, completeness or omitted authorities.

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

Historical full-mode records remain readable and retain the VERITAS five-level
failure taxonomy, Claim Graph, and bounded landmark comparison for research
traceability. New submissions do not run that contextual mode in Tier 0: they
are citation-only, and contextual completeness, omitted-authority analysis,
and independent counter-authority retrieval remain deferred. Any historical
full-mode output is a review prompt, not proof that an answer is complete.

Scoring policy lives in api/data/assurance_policy.json; changing its version
invalidates the exact-result cache. Citation, unsupported-assertion, and
approved-currency gates run before weights. Direct contradiction remains
explicitly unassessed because lexical similarity is not Legal NLI. Exact and
whitespace-normalised quotation checks run against stored judgment text only.

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

The manual Chrome intake is recorded separately in
`api/data/research_catalog/v1/manual_retrieval_batch_01.json` and
`manual_retrieval_batch_02.json`. Together they contain 25 official eLitigation
judgment locators (549 matching SG-LegalCite citation rows) covering
restraint-of-trade, confidentiality, scope, duration, severance and injunction
issues. They store provenance and paragraph targets only; raw judgment text,
hashes and approved Case Maps remain pending legal review.

Current lexical TF-IDF ranking is narrower: it ranks paragraphs only within an
authority already resolved from the AI answer's citation. Gemini atomises
claims and proposes controlled labels; it does not create a separate fact
record or legal conclusion. Court level is displayed, but declaring an
authority controlling requires lawyer review.

## Create the presentation snapshot

Before the pitch, add GEMINI_API_KEY to api/.env and run this once while the
official SG Courts/eLitigation site is available:

~~~powershell
cd api
uv run python -m app.refresh_cli --tier0-target-pack
~~~

The Tier 0 release flag fetches exactly the six GoldFixture identities through
their official URLs. It uses a strict SG Courts allowlist,
robots guidance, 1 request/second throttling, bounded retries, and a
25-judgment ceiling. Each accepted source must have a matching neutral citation
in its heading and numbered paragraphs. Gemini may select only extracted
paragraph labels and controlled taxonomy values; ProofMark copies all displayed
passage text from the official document.

The resulting api/data/frozen_snapshot.json is the immutable local snapshot
used on normal audits. You can also launch the same process from
**Authority inventory -> AI refresh from SG Courts**. Refresh work never happens
during an audit. If network access, source terms, robots guidance, parsing, or
Gemini annotation fails, ProofMark keeps the last successful snapshot and says
that it is cached. Do not claim a live refresh succeeded when the page shows
the fallback banner.

## Certify and archive a Tier 0 snapshot

The refresh command does not certify legal review. Before using a snapshot in a
Tier 0 release, legal review must approve each authority's official URL,
neutral citation, document hash, numbered passages and source-role metadata.
After that review, validate and archive the exact bytes:

~~~powershell
cd api
uv run python -m app.snapshot_cli validate --snapshot data/frozen_snapshot.json --require-certified
uv run python -m app.snapshot_cli archive --snapshot data/frozen_snapshot.json --require-certified
~~~

The validator rejects missing hashes, non-eLitigation URLs, missing numbered
paragraphs, unreviewed evidence, or unreviewed source roles. The archive stores
the snapshot plus a content-hash manifest. It does not create approvals or
replace legal review.

Record the human legal decision separately at
`data/release_evidence/tier0_v1/legal_review.json`. It must identify the
reviewer, cover exactly six authorities, confirm URL/citation/hash/paragraph
and source-role approval, and state that the approved treatment/currency
registry was checked. The release checker does not infer this file from a
successful refresh or from benchmark fixtures.

## Tier 0 release evidence

Run the deterministic release benchmark from the six-case gold fixture pack:

~~~powershell
cd api
.venv\Scripts\python.exe -m app.benchmark_cli --runs 250
~~~

The command fails unless the fixture pack is exact, has zero benchmark errors,
and stays below the 1,500 ms P95 target. It writes
`api/data/release_evidence/tier0_v1/benchmark.json`; the adjacent
`release_status.json` records external blockers such as legal review and the
connected-user rehearsal. Gold fixtures are benchmark evidence only and do not
make an ordinary runtime snapshot `verified`.

The final release checker is fail-closed. Run it from `api` after each evidence
step:

~~~powershell
.venv\Scripts\python.exe -m app.release_cli check
~~~

It requires the certified six-authority snapshot/archive, a legal review
record, a saved local RLS result, a connected-user verification record,
and an offline rehearsal record.
It exits non-zero while any one of those gates is missing; benchmark fixtures
cannot satisfy an external gate.

After the certified archive exists, the offline rehearsal can be recorded with:

~~~powershell
.venv\Scripts\python.exe -m app.offline_rehearsal_cli
~~~

The rehearsal refuses to use the gold fixture corpus, Gemini, refresh, or
network. It loads only the certified snapshot and writes
`data/release_evidence/tier0_v1/offline_rehearsal/rehearsal.json`.

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

The Supabase schema, seed corpus, and pgTAP RLS tests live in `supabase/`.
Project `zxjaccusnmunjgktzkme` has been reconciled with the repository
migrations without resetting its existing demo data. The hosted migration
history currently includes the initial schema, refresh/currency/Case Map
migrations, and the Tier 0 integrity-provenance migration. Review the seed
passages with the legal-research team before activating any new corpus.

## Connected Supabase setup

For a fresh or otherwise approved environment, review and apply migration files
in order to project `zxjaccusnmunjgktzkme`:

~~~powershell
npx supabase@latest link --project-ref zxjaccusnmunjgktzkme
npx supabase@latest db push
~~~

Do not run `migration repair` unless a schema-only remote dump proves that a
specific migration is already present. Do not run `db reset` against the shared
project.

This requires the project database password and does not require Docker.
Alternatively, run every SQL file in supabase/migrations/ in timestamp order
in the Supabase SQL Editor. The migrations create corpus refresh/provenance,
immutable-content controls, coverage metadata, source-versioned audit cache
and retention fields, reviewer-only legal-currency records, explicit Data API
grants, RLS, and a service-role-only transactional snapshot activator.
Browser clients can read allowed metadata but cannot write refreshes, corpus
content, derived evidence, or verdicts.

### Connected audit release evidence

The connected gate is a user-journey check, not a service-key database insert.
With the API in `supabase` mode and the dashboard signed in as the confirmed
demo member, submit one citation-only audit, reload its detail page, and verify
that the report, claims, evidence, tenant scope, snapshot version and retention
metadata remain visible. Record the result locally as
`api/data/release_evidence/tier0_v1/connected_supabase.json` with this minimum
shape (do not include a password, secret key or bearer token):

~~~json
{
  "release": "tier0-v1-citation-integrity",
  "status": "passed",
  "audit_public_id": "<saved audit id>",
  "persisted_after_reload": true,
  "tenant_scoped": true,
  "claims_and_evidence_reload": true,
  "reviewer_controls_checked": true,
  "snapshot_version_rendered": "<version>",
  "retention_metadata_rendered": true
}
~~~

The release checker accepts this file only when the required fields are true.
Do not mark it passed from a service-role query; that would bypass the RLS and
browser-auth boundary the gate is intended to verify.

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
uv run python -m app.research_catalog_cli validate --catalogue-dir api/data/research_catalog/v1
```

## Scope boundary

The active corpus covers only Singapore employment restraint-of-trade material
that passed the automated official-source gates. Six selected cases are
isolated as **benchmark gold fixtures only**. They are the sole pathway
to the verified fixture label; an official, AI-supported runtime paragraph can
produce only context_review.

The two newly added Smile Inc and MoneySmart fixture extracts are explicitly
marked for legal-team verification in their passage limitations. Do not quote
their paraphrases or present their expected labels until counsel has checked
the linked official judgments. Secondary journals and articles are metadata
only; ProofMark does not ship or reproduce their text.

SAL, SLR, and LawNet are deliberately excluded from this MVP. A future
LicensedSourceConnector may ingest private tenant material only when the
organisation's licence and terms permit it. PGMQ workers, pgvector,
organisation administration, and deployed worker/API scaling remain production
architecture targets, not silently simulated features.

The VERITAS provenance/dependency migration was hand-authored from the updated
declarative schema because the Supabase CLI was unavailable in this workspace.
It has not been applied to the remote project; review it, then run the normal
migration, RLS-test, and database-advisor workflow.
