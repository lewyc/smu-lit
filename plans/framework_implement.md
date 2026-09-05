# ProofMark Revised Plan: Case Maps, Contextual Evaluation, and Human Review

## Summary

Treat the implemented official-judgment refresh as the completed ingestion foundation. Do not rebuild discovery, robots handling, throttling, HTML extraction, hashing, background execution, snapshot caching, coverage reporting, Supabase activation, or the benchmark/runtime trust separation already present in [refresh.py](C:/Users/yikch/Downloads/SMULIT/smu-lit/api/app/refresh.py), [engine.py](C:/Users/yikch/Downloads/SMULIT/smu-lit/api/app/engine.py), and the [refresh migration](C:/Users/yikch/Downloads/SMULIT/smu-lit/supabase/migrations/20260905094116_automated_official_judgment_refresh.sql).

The remaining work is to:

- Enrich selected immutable judgment snapshots into structured Case Maps.
- Add lawyer editing and approval without mutating source snapshots.
- Add citation-pinpoint, modality, authority-strength, contextual-distinction, currency, balance, and omission checks.
- Add practitioner feedback with controlled review rather than automatic self-learning.
- Extend the gold benchmark corpus from four to six Singapore judgments.
- Retain `verified` exclusively for the separated gold benchmark; normal audits remain `context_review` or lower even after human annotation.
- Keep local mode presentation-safe while adding optional Supabase persistence.

Current baseline: 17 backend tests and 2 frontend tests pass.

## Implementation Changes

### 1. Preserve the implemented refresh architecture

Keep unchanged:

- Bounded SG Courts topic discovery and 25-document cap.
- Robots validation, host allowlist, retry and one-second throttle.
- Citation-heading validation and numbered-paragraph extraction.
- Immutable, hashed local snapshots and last-good fallback.
- Local background refresh manager and existing refresh endpoints.
- Atomic Supabase snapshot activation and corpus immutability triggers.
- Pre-warmed TF-IDF vectors after activation.
- `officially_sourced + ai_supported` evidence producing at most `context_review`.
- Gold fixtures remaining completely separate from the active runtime snapshot.
- Provenance, disagreement and coverage displays already added to the dashboard.

The Case Map pipeline operates as an overlay keyed by:

```text
normalised citation key
+ source document hash
+ Case Map schema version
```

This allows an approved Case Map to be reused across refreshed snapshots only while the official judgment hash remains unchanged. A corrected or replaced judgment automatically makes the previous map stale.

### 2. Case Map preprocessing on top of refreshed judgments

Add a second-stage preprocessing service:

```python
class CaseMapAnnotator(Protocol):
    def annotate(
        self,
        authority: Authority,
        selected_passages: list[Passage],
    ) -> CaseMapDraft: ...

class CaseMapValidator(Protocol):
    def validate(
        self,
        authority: Authority,
        draft: CaseMapDraft,
    ) -> CaseMapValidation: ...

class CaseMapRepository(Protocol):
    def create(self, draft: CaseMapDraft) -> CaseMapDraft: ...
    def get(self, public_id: UUID) -> CaseMapDetail | None: ...
    def revise(self, public_id: UUID, change: AnnotationRevision) -> CaseMapDetail: ...
    def approve(self, public_id: UUID, reviewer_id: UUID | None) -> CaseMapDetail: ...
```

The existing refresh annotator remains a cheap first-pass paragraph selector. The new Case Map annotator receives only selected paragraphs plus nearby context, reducing Gemini cost and preventing it from rewriting the judgment.

For each case, extract:

- Issues.
- Material facts.
- Procedural stage.
- Party submissions.
- Court findings.
- Disposition.
- Candidate ratio.
- Candidate obiter.
- Legal propositions.
- Qualifications and exceptions.
- Policy considerations.
- Relevant factual distinctions.
- Authorities cited and candidate treatment.
- Modality:
  - `mandatory`
  - `qualified`
  - `permissive`
  - `descriptive`
- Authority role:
  - `ratio_candidate`
  - `holding`
  - `obiter_candidate`
  - `party_submission`
  - `factual_finding`
  - `procedural_history`
  - `disposition`

Every annotation must contain:

```ts
interface CaseMapAnnotation {
  id: string
  annotation_type: AuthorityRole
  proposition_code: string | null
  statement: string
  paragraph_labels: string[]
  supporting_quote: string
  modality: Modality
  limitations: string[]
  applicability_factors: string[]
  model_confidence: number
  validation_status: 'valid' | 'warning' | 'invalid'
  review_status: 'draft' | 'approved' | 'rejected' | 'superseded'
}
```

Gemini must select exact stored paragraphs and short exact quotations. It may not provide new judgment text, authority metadata, verdicts, currency conclusions, or binding-status conclusions.

Deterministic validation must confirm:

- Every paragraph belongs to the same source-hashed judgment.
- Every quotation is present after whitespace-only normalisation.
- Every proposition belongs to the controlled taxonomy.
- Party submissions are not silently classified as holdings.
- A ratio, obiter or treatment label has paragraph evidence.
- Referenced citations are syntactically valid.
- Duplicate chunk results are merged without losing distinct limitations.
- The source hash still matches the active judgment.
- Invalid annotations cannot reach the review or runtime layer.

Use separate model settings:

- `GEMINI_CASEMAP_MODEL=gemini-3.5-flash-lite`
- `GEMINI_CLAIM_MODEL=gemini-3.5-flash-lite`
- Keep `GEMINI_MODEL` temporarily as a backward-compatible fallback.

Record model, prompt, schema, annotator and extractor versions.

### 3. PDF intake retained as a secondary path

Add a PDF importer without changing the official refresh connector.

- Accept text-based PDFs up to 15 MB.
- Require an expected neutral citation and optional official source URL.
- Use a pinned `pypdf` dependency.
- Reject encrypted, scanned, empty and malformed PDFs.
- Preserve numbered paragraphs and compute a SHA-256 hash.
- Discard the binary after extraction.
- Never label a PDF `officially_sourced` merely because the user says it is official.
- If its official URL and identity cannot be independently validated, assign `source_provenance = user_supplied`.
- PDF-derived evidence can produce at most `context_review`.
- PDF imports create Case Map drafts; they never activate or replace the automated official snapshot.

Extend:

```python
SourceProvenance = Literal[
    "officially_sourced",
    "user_supplied",
    "gold_fixture",
    "rejected",
]
```

### 4. Legal, source, and model hierarchy

Keep three independent assessments.

**Court and precedential hierarchy**

Store:

- Jurisdiction.
- Court code.
- Court tier.
- Target forum.
- `precedential_status`: `binding`, `persuasive`, `secondary`, `unknown`.
- Legal-team reviewer and review timestamp.

Automatically derive court code and tier, but not nuanced binding conclusions. For the Singapore pilot:

- SGCA is the highest domestic case-law tier.
- Other Singapore court levels are represented separately.
- Foreign cases remain persuasive and outside the active six-case benchmark.
- `Singapore → UK → Australia → US` is a configurable research priority, not a legal-verdict rule.

Authority level affects ordering, omissions and explanations; it never turns semantic similarity into legal support.

**Source hierarchy**

1. Official Singapore judgment or legislation.
2. Verified licensed law report/database metadata.
3. Recognised journal, textbook or commentary.
4. Other secondary source.
5. User-supplied or unverified material.

Add metadata-only secondary-source records containing title, author, publication, year, URL and verification status. Do not store or reproduce journal/article text. Secondary materials can appear in the lawyer handoff but cannot independently verify a rule of law.

**Decision authority**

1. Deterministic source and citation checks.
2. Gold benchmark annotations.
3. Lawyer-approved Case Map annotations.
4. Approved registry and authority-treatment records.
5. AI-supported paragraph labels.
6. TF-IDF ranking.
7. Pending practitioner feedback.

Even a lawyer-approved runtime Case Map remains `context_review` under the selected conservative policy. Approval means “fit for evaluation assistance,” not “guaranteed legal truth.”

### 5. Complete the four evaluation modules

**Citation integrity**

Extend claim parsing to retain `CitationMention` records:

```ts
interface CitationMention {
  raw_text: string
  canonical_citation: string | null
  case_name_mention: string | null
  pinpoint: string | null
  parse_status: 'valid' | 'malformed' | 'unresolved'
}
```

Add checks for:

- Malformed neutral citations.
- Case-name/citation mismatch.
- Court-code mismatch.
- Exact authority existence.
- Exact pinpoint existence.
- Whether evidence is actually drawn from the cited pinpoint.

When a pinpoint is supplied, search that paragraph first and do not silently substitute a better paragraph elsewhere in the case. If the pinpoint exists but supports another proposition, classify it as `unsupported` or `context_review` with a wrong-pincite flag.

Preserve the current safeguard: `likely_fabricated` requires a stored negative official-registry check. Failed discovery, network errors, and corpus absence remain `unverified`.

**Propositional and contextual accuracy**

Add two audit modes:

```ts
type AuditMode = 'citation_only' | 'full'
```

`citation_only` accepts the existing answer-only submission.

`full` requires the original legal question and accepts optional facts. Gemini converts this context into a controlled profile:

- Duration.
- Geographic scope.
- Restricted activities.
- Alleged proprietary interest.
- Confidential-information access.
- Customer connection.
- Employee role.
- Procedural stage.
- Relief sought.

Compare the profile deterministically with approved Case Map limitations and applicability factors. Flag:

- Party submission presented as the court’s conclusion.
- Obiter candidate presented as binding ratio.
- “Must,” “always” or “automatically” conflicting with qualified language.
- Material factual mismatch.
- Authority supporting a different proposition.
- Lower or persuasive authority presented as controlling.
- Secondary opinion presented as law.

Gemini identifies structure and labels; deterministic rules still assign the verdict.

**Currency and relevance**

Add reviewed authority-treatment overlays:

```ts
type Treatment =
  | 'follows'
  | 'applies'
  | 'distinguishes'
  | 'limits'
  | 'criticises'
  | 'overrules'
  | 'cites'
```

AI may propose treatment edges during Case Map generation, but only approved edges affect audits. Each edge requires source and target citations, paragraph evidence, reviewer, timestamp and source-document hash.

Unknown currency must display `not verified`. Negative treatment produces a review flag, not an automatic claim that the cited case is no longer good law.

**Balance and omissions**

Run only in `full` mode.

Create approved issue checklists for:

- Legitimate proprietary interest.
- Reasonableness between the parties.
- Public-interest reasonableness.
- Activity, geographic and duration scope.
- Confidential information.
- Customer connections.
- Stable trained workforce.
- Severance.
- Interim-injunction requirements.
- Freedom-of-trade and unequal-bargaining policy concerns.

Compare expected issues with the answer’s extracted propositions and cited authorities. Return:

- `potential_omission`
- `potentially_one_sided`
- `missing_limiting_authority`
- `policy_factor_not_addressed`

These are lawyer-review prompts, not conclusive errors.

Add taxonomy entries supported by the expanded gold corpus:

- `severance_blue_pencil`
- `cascading_restraint`
- `non_solicitation_non_dealing`
- `policy_freedom_to_trade`

### 6. Scoring and “Who audits the auditor?”

Add four module scores:

- Citation integrity: 30%.
- Propositional accuracy: 35%.
- Relevance/currency: 20%.
- Balance/completeness: 15%.

Only `full` mode receives an overall score. Citation-only mode shows the first available dimensions without renormalising them into a misleading total.

Add severity:

- `critical`: recorded fabricated authority or materially false citation identity.
- `serious`: wrong proposition, wrong pinpoint, or ignored approved negative treatment.
- `review`: factual distinction, overstatement, balance or omission.
- `informational`: malformed or unavailable metadata.

Keep separate:

- Parser confidence.
- Model annotation confidence.
- Deterministic validation coverage.
- Source provenance.
- Assessment confidence: `high`, `medium`, `low`.

Do not present any value as the probability that a legal conclusion is correct.

Every verdict must expose:

- Decision-rule ID.
- Exact paragraph and official source.
- Source and assessment status.
- Case Map version and reviewer status.
- Corpus, taxonomy and engine versions.
- Model and prompt versions.
- Parser fallback.
- Currency status.
- Pending feedback status.
- Reasons a module was not assessed.

### 7. Practitioner feedback and review

Add “Flag this evaluation” to every audited claim.

Feedback categories:

- Wrong verdict.
- Wrong proposition.
- Wrong pinpoint.
- Incorrect Case Map role.
- Missing authority.
- Missing context.
- Outdated authority.
- Other.

Require an explanation and optionally accept a proposed citation, paragraph and correction.

Workflow:

```text
submitted
→ under_review
→ accepted or rejected
→ corrected Case Map revision
→ new approved Case Map version
```

All organisation members may submit feedback. Only `reviewer` and `owner` roles may resolve it or approve Case Maps.

Submitting feedback immediately marks the affected assessment `under_review`, but does not change its score, evidence or verdict. Accepted feedback creates a revision and audit event; it does not retrain Gemini.

## Public Interfaces, Persistence, and Dashboard

### API

Keep existing refresh endpoints unchanged.

Extend audit submission:

```ts
interface AuditSubmission {
  answer: string
  audit_mode: 'citation_only' | 'full'
  original_question?: string
  facts?: string
  parser_mode: ParserMode
  persist: boolean
}
```

Validation:

- Answer: 1–20,000 characters.
- Original question: maximum 5,000 characters.
- Facts: maximum 10,000 characters.
- Full mode requires the original question.
- Existing callers default to `citation_only`.

Add:

- `POST /api/v1/case-maps/generate`: generate from an authority in an immutable snapshot.
- `POST /api/v1/case-maps/import-pdf`: create a draft from a PDF.
- `GET /api/v1/case-maps`: review queue and approved maps.
- `GET /api/v1/case-maps/{public_id}`: source paragraphs, annotations and validation.
- `PATCH /api/v1/case-maps/{public_id}/annotations/{annotation_id}`: reviewer correction.
- `POST /api/v1/case-maps/{public_id}/approve`: approve the current Case Map revision.
- `POST /api/v1/feedback`: submit a practitioner flag.
- `GET /api/v1/feedback`: organisation review queue.
- `POST /api/v1/feedback/{public_id}/resolve`: accept or reject feedback.
- `GET /api/v1/hierarchies`: court, source and decision-authority definitions.

Case Map generation may use the existing local background executor pattern. Do not run it inside normal audits.

### Supabase

Do not modify immutable authority or passage rows. Add overlay tables:

- `source_imports`: PDF metadata, citation, URL, hash, extracted paragraphs and warnings.
- `case_map_runs`: organisation, citation key, document hash, model/prompt/schema versions, status and timings.
- `case_map_annotations`: structured annotations, evidence anchors, validation and review status.
- `case_map_review_events`: append-only edits, approvals, rejections and supersession.
- `authority_assessments`: court hierarchy, precedential status and currency review.
- `authority_relationships`: reviewed treatment graph.
- `practitioner_feedback`: organisation-scoped submissions and resolutions.
- `reference_sources`: metadata-only journals, commentaries and textbooks.

Add audit-mode, question, facts, module scores and evaluation provenance to `audit_runs`.

Because the repository uses declarative schemas, update the desired schema files first and generate the next migration from them.

Security requirements:

- Enable RLS on every new public table.
- Explicitly revoke anonymous access and add deliberate Data API grants.
- Keep browser access read-only for derived annotations and assessments.
- Route Case Map, hierarchy and feedback mutations through FastAPI.
- Validate Supabase token, organisation membership and reviewer/owner role server-side.
- Members may submit feedback but cannot approve maps or resolve feedback.
- Index every foreign key plus organisation/status/date, document hash, citation key, review queue and unresolved-feedback access paths.
- Any new view must use `security_invoker = true`.
- Run RLS tests and database advisors after the migration.

### Dashboard

Extend the existing Authority Inventory rather than replacing it.

Add `/case-maps` with:

- Snapshot authority selector.
- “Generate Case Map” action.
- PDF import.
- Review queue.
- Source paragraph viewer.
- Editable annotation panel.
- Validation errors.
- Accept/reject controls.
- Approval and version history.
- Practitioner feedback tab.

Update:

- `/audits/new`: citation-only/full selector and conditional context fields.
- `/audits/:id`: four module scores, authority hierarchy, modality, role, currency, exact pinpoint assessment, omissions, balance and feedback action.
- `/authorities`: Case Map status, court/source hierarchy and treatment graph alongside existing refresh provenance.
- `/benchmark`: six-case gold coverage, module accuracy, fabrication precision, false-positive count and confusion matrix.
- `/assurance`: automated refresh → Case Map → lawyer review → runtime evaluation flow, plus the three trust hierarchies.

## Test Plan and Delivery Priority

### Backend

Preserve all 17 existing tests and add:

- Generate a Case Map from an active immutable snapshot.
- Reject invented labels and non-matching quotations.
- Detect stale Case Maps after a document hash changes.
- Deduplicate overlapping chunk annotations.
- Reject scanned, encrypted and oversized PDFs.
- Assign unvalidated PDFs `user_supplied` provenance.
- Prevent PDF imports from activating official snapshots.
- Detect wrong and missing pinpoints.
- Detect case-name and court mismatch.
- Distinguish party submission, holding and obiter candidate.
- Detect modality overstatement.
- Run contextual distinctions only in full mode.
- Generate omission and balance flags from approved issue checklists.
- Ignore unapproved authority-treatment edges.
- Confirm feedback cannot change verdicts automatically.
- Confirm all normal official evidence remains at most `context_review`.
- Confirm only gold fixtures produce `verified`.

### Database and frontend

Add tests for:

- Same-organisation Case Map and feedback access.
- Cross-organisation denial.
- Member feedback submission.
- Member approval denial.
- Reviewer/owner approval and resolution.
- Append-only review history.
- Old Case Map and source snapshots remaining unchanged.
- Citation-only mode labelling contextual modules as not assessed.
- Full mode requiring the original question.
- Reviewer editing and approving paragraph-linked annotations.
- Feedback displaying `under_review` without changing the verdict.
- Gemini, Supabase and live-source failures preserving a usable local demo.

### Benchmark and corpus

Expand the gold benchmark to include legally reviewed passages from:

- *Smile Inc Dental Surgeons Pte Ltd v Lui Andrew Stewart* [2012] SGCA 39.
- *MoneySmart Singapore Pte Ltd v Artem Musienko* [2024] SGHC 94.

Fixtures must cover:

- Valid citation and proposition.
- Wrong pinpoint.
- Wrong court or case name.
- Real case supporting a different proposition.
- Party submission presented as a holding.
- Obiter candidate presented as binding.
- Qualified language presented absolutely.
- Missing limiting authority.
- Missing severance or injunction issue.
- One-sided analysis.
- Secondary commentary presented as law.
- Recorded fabricated citation.
- Unknown citation without negative evidence.
- Out-of-scope claim.

Continue the 250-run deterministic performance batch with warmed local P95 below 1.5 seconds. Measure Gemini preprocessing separately and never include network latency in the deterministic performance claim.

### Remaining delivery order

1. Case Map schemas, Gemini extraction and validation.
2. Exact pinpoint and citation-identity checks.
3. Full audit context profile and modality.
4. Case Map review dashboard.
5. Balance, omission and currency overlays.
6. Practitioner feedback.
7. PDF import.
8. Supabase persistence and RLS.
9. Six-case benchmark expansion and presentation freeze.

If time becomes constrained, PDF import is the first feature allowed to remain backend-only. Do not cut the Case Map evidence anchors, gold/runtime separation, provenance, human review or fabricated-citation safeguard.

## Assumptions

- The automated refresh implementation and its public interfaces remain backward-compatible.
- The active runtime snapshot may contain up to 25 machine-discovered judgments; only six named Singapore judgments form the gold benchmark.
- Legal teammates will verify the two added gold cases, all Case Map roles, limitations, treatment edges, hierarchy labels and benchmark expectations.
- `verified` remains benchmark-only.
- Lawyer-approved runtime evidence remains `context_review`, accompanied by stronger provenance and review metadata.
- The local dashboard and FastAPI service are the guaranteed pitch path.
- Supabase review persistence is optional for the live pitch but remains fully specified.
- PDF support is text-only and does not include OCR.
- Secondary materials remain metadata-only.
- Foreign judgment ingestion, statutory currency automation, pgvector, PGMQ workers, model training and automatic feedback-driven recalibration remain outside the MVP.
