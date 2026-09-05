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

The pilot corpus covers four selected Singapore decisions and a controlled
restraint-of-trade proposition taxonomy. Production queue workers, pgvector,
automatic judgment ingestion, organisation administration, and a deployed API
are architecture targets shown in the Assurance page; they are not silently
simulated by this MVP.
