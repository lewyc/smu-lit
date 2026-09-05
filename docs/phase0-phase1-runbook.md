# Phase 0-1 readiness runbook

Use this checklist to turn the implemented local workflow into a repeatable
demo, then prepare a separate research-only catalogue. Do not mark a legal or
external-service gate complete without the named owner.

## Phase 0

1. Install Python 3.12 with `uv`, Node 20+ and npm. Copy each `.env.example`
   file to its local `.env`; never commit those files.
2. Run the README verification commands and record date, operator, tool
   versions and pass/fail result below.
3. With an authorised Gemini key and SG Courts availability, run
   `uv run python -m app.refresh_cli` from `api/`. Preserve the resulting
   `api/data/frozen_snapshot.json` with the refresh output and its SHA-256.
4. In demo mode, start the API/dashboard with refresh disabled
   (`PROOFMARK_REFRESH_INTERVAL_HOURS=0`), run a seeded audit and confirm the
   frozen/cached provenance is visible.
5. For connected mode, obtain project-owner and legal-review approval before
   applying the migrations in timestamp order. Create a demo Auth user and an
   organisation membership, then run the RLS suite and one persisted audit.

| Date | Operator | Python/uv | Node/npm | API tests | Dashboard checks | RLS | Snapshot SHA-256 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Credentials and legal review required |

## Phase 1

The raw SG-LegalCite source remains outside this repository. The local source
file observed for this project is `COMBINED_ALL_CASES_FINAL_V2.csv`, SHA-256
`22994a94441fe8d7ea3d3ad19a43c25d908b23127cef6c3dd2a49bd3e33aad5e`.

Generate a local-only, metadata-only shortlist:

```powershell
cd api
uv run python -m app.research_catalog_cli shortlist `
  --dataset "..\..\SG-LegalCite\COMBINED_ALL_CASES_FINAL_V2.csv" `
  --output "$env:TEMP\proofmark-research-shortlist.json" `
  --limit 100
```

The shortlist makes two streaming passes: it first indexes Singapore Supreme
Court case titles and neutral citations from the dataset, then keeps only
restraint candidates that match that index. It still needs legal review because
a dataset reference is not proof of the official source, paragraph support or
treatment.

For each selected authority, a legal reviewer must validate the official
judgment, numbered paragraphs, exact quote, controlled proposition,
limitations, role and treatment status. Only then add the reviewer-approved
record to `api/data/research_catalog/v1/approved_authorities.json`, update the
manifest hash/count, and validate it:

```powershell
uv run python -m app.research_catalog_cli validate `
  --catalogue-dir api/data/research_catalog/v1
```

Use `--require-ready` only once all 25 entries are counsel-approved. A ready
catalogue must contain exactly 25 entries. The catalogue is not runtime audit
evidence and must remain separate from `frozen_snapshot.json`.
