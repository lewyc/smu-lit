# ProofMark

ProofMark is a 24-hour hackathon MVP for evaluating citation integrity and
evidential grounding in AI-generated Singapore employment restraint-of-trade
answers. It is a pilot evaluation tool, not legal advice and not a comprehensive
case-law database.

## Working vertical slice

```text
Pasted AI answer -> parsed legal claims -> exact citation resolution
-> proposition-aware evidence matching -> deterministic verdicts
-> lawyer handoff -> optional Supabase persistence
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

## Create the presentation snapshot

Before the pitch, add GEMINI_API_KEY to api/.env and run this once while the
official SG Courts/eLitigation site is available:

~~~powershell
cd api
uv run python -m app.refresh_cli
~~~

It uses five taxonomy-derived search queries, a strict SG Courts allowlist,
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
Apply the migration to project `zxjaccusnmunjgktzkme` only after reviewing the
seed passages with the legal-research team.

## Connected Supabase setup

For the connected mode, review and apply both migration files in order to
project zxjaccusnmunjgktzkme:

~~~powershell
npx supabase@latest link --project-ref zxjaccusnmunjgktzkme
npx supabase@latest db push
~~~

This requires the project database password and does not require Docker.
Alternatively, run the two SQL files in supabase/migrations/ in order in the
Supabase SQL Editor. The second migration creates corpus_refresh_runs,
provenance fields, an immutable-content trigger, a coverage view, explicit
Data API grants, RLS, and a service-role-only transactional snapshot activator.
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
```

## Scope boundary

The active corpus covers only Singapore employment restraint-of-trade material
that passed the automated official-source gates. The former four selected cases
are hand-labelled **benchmark gold fixtures only**. They are the sole pathway
to the verified fixture label; an official, AI-supported runtime paragraph can
produce only context_review.

SAL, SLR, and LawNet are deliberately excluded from this MVP. A future
LicensedSourceConnector may ingest private tenant material only when the
organisation's licence and terms permit it. PGMQ workers, pgvector,
organisation administration, and deployed worker/API scaling remain production
architecture targets, not silently simulated features.
