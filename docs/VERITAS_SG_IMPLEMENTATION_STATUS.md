# VERITAS SG Implementation Status

**Assessment date:** 6 September 2026  
**Repository assessed:** C:\Users\yikch\Downloads\SMULIT\smu-lit  
**Proposal assessed:** # VERITAS SG.txt  
**Purpose:** Provide a traceable, judge-safe account of which parts of the VERITAS SG proposal are fully implemented, partially implemented, or not implemented in the current ProofMark codebase.

## Status definitions

| Status | Meaning in this report |
|---|---|
| **Fully implemented** | The feature is present in executable code, exposed through the API or dashboard where appropriate, and covered by tests or direct verification. It may still operate only within the declared Singapore employment-restraint pilot. |
| **Partially implemented** | A meaningful working slice exists, but one or more proposal requirements, data sources, runtime integrations, legal-review steps, or scale mechanisms are missing. The limitation is stated explicitly. |
| **Not implemented** | The proposal capability is not present in the operational evaluation path. A schema, label, screen mock-up, or roadmap statement by itself does not count as implementation. |
| **Designed only** | The architecture or database shape exists, but no production path creates and consumes the data end to end. This is treated as partially implemented or not implemented depending on how much executable support exists. |

## Executive assessment

ProofMark currently implements a credible, bounded legal-AI evaluation MVP rather than the complete VERITAS SG platform described in the proposal.

Its strongest implemented capabilities are:

- conservative citation extraction and normalisation;
- exact authority and pinpoint resolution within a controlled Singapore corpus;
- deterministic proposition matching against stored, paragraph-linked annotations;
- exact quotation anchoring and source-hash provenance;
- a five-level failure taxonomy and four-question explanation spine;
- transparent claim-level verdicts, evidence, reasons, escalation flags, and negative findings;
- a six-authority separated gold benchmark with adversarial fixtures;
- immutable official-judgment refresh snapshots and Case Map preprocessing;
- lawyer review, Case Map versioning, practitioner feedback workflow, and multi-tenant database design;
- configurable assurance gates and scoring weights;
- a local presentation path that does not depend on Gemini or Supabase availability.

The largest gaps between the proposal and the current implementation are:

- no calibrated Legal NLI or contradiction model;
- no independent retrieval path for completeness testing;
- no operational treatment-graph traversal or automatic citator;
- no automatic statute existence or statutory-currentness checking;
- approved Case Maps are not yet the primary runtime evidence source for normal audits;
- no statistical confidence calibration, reliability diagrams, or error-bound claims;
- no production-derived benchmark partition or automated benchmark lifecycle;
- no reviewer reputation or production adjudication service; the bounded Tier 3
  demo queue now enforces two independent qualified-lawyer decisions and
  records optional dissent;
- no populated reverse-dependency recomputation service;
- no true asynchronous tiered evaluation architecture for thousands of daily queries;
- no production deployment gate enforcing legal, security, performance, and calibration thresholds.

The correct presentation claim is therefore:

> ProofMark is a working vertical slice of VERITAS SG for a bounded Singapore employment-restraint corpus. It demonstrates deterministic citation checks, evidence-linked contextual review, Case Map preprocessing, conservative scoring, and auditable human oversight. The broader citator, NLI, independent completeness retrieval, calibration, and production-scale governance layers remain roadmap work.

It should not be presented as a comprehensive legal citator, an autonomous legal-accuracy oracle, or a deployed system proven at thousands of daily queries.

## Evidence used for this assessment

This report distinguishes proposal language from actual executable behaviour by inspecting the following implementation areas:

- API assurance policy and scoring: api/app/assurance.py
- Audit engine and verdict rules: api/app/engine.py
- Request, response, Case Map, feedback, and provenance models: api/app/models.py
- Case Map generation, validation, revision, approval, and PDF intake: api/app/case_maps.py
- Local and Supabase repositories: api/app/repositories.py
- Versioned targets, calibration placeholders, weights, gates, issue checklist,
  and landmark candidates: api/data/veritas_operating_config.json
- Audit explanation UI: dashboard/src/pages/AuditDetailPage.tsx
- Case Map review UI: dashboard/src/pages/CaseMapsPage.tsx
- Assurance disclosure UI: dashboard/src/pages/AssurancePage.tsx
- Benchmark UI: dashboard/src/pages/BenchmarkPage.tsx
- Declarative database schema and security: supabase/schemas/01_tables.sql and supabase/schemas/02_security.sql
- RLS tests: supabase/tests/rls.test.sql
- Latest VERITAS provenance migration: supabase/migrations/20260906021500_veritas_provenance_and_dependencies.sql

The current verified test baseline is 39 backend tests and 6 frontend tests passing, together with successful frontend lint, type checking, and production build. The fixed local benchmark reports 12 of 12 expected outcomes, 250 deterministic performance runs, no run errors, 100 percent fabricated-citation precision for the fixture set, and a measured warmed P95 of approximately 17.75 milliseconds. These are fixture and local-runtime measurements, not general legal-accuracy or production-capacity claims.

## 1. Two operating loops: Live Audit and Benchmark Audit

**Status: Partially implemented**

### What is implemented

- The live audit path accepts a pasted AI-generated answer, extracts claims and citations, resolves them against the active pilot corpus, ranks stored passages, applies deterministic verdict rules, builds a lawyer handoff, and can persist and display the result.
- The benchmark path is deliberately separated from the live runtime corpus. Gold fixtures are the only source allowed to produce the strongest verified label.
- The benchmark exposes fixture correctness, module results, a confusion matrix, fabrication precision, false-positive count, and deterministic latency measurements.
- The runtime and benchmark trust separation is explicitly disclosed in the dashboard and API metadata.

### What is only partial

- The proposal says every candidate model, prompt, retrieval system, or reranker should be continuously evaluated. The current benchmark evaluates ProofMark's fixed adversarial fixture pack; it does not accept arbitrary candidate configurations or compare multiple legal-AI systems.
- There is no continuous evaluation scheduler, release registry, or automatic production-sample evaluation loop.
- There is no production shadow traffic or per-candidate historical dashboard.

### What is not implemented and why

- Automatic benchmarking of third-party models and retrievers is not implemented because the MVP has no standard candidate-output ingestion contract, no secure execution environment for third-party systems, and no representative licensed production query set.
- Continuous evaluation is deferred to avoid implying statistical validity from a small, legally bounded fixture pack.

## 2. Five-level failure taxonomy

### Level 1: Non-existent or malformed authority

**Status: Fully implemented for the bounded corpus, with an important source limitation**

Implemented behaviour:

- Singapore neutral citations are extracted with tolerant formatting and normalised to a canonical key.
- Known authorities resolve exactly against the gold or active runtime corpus.
- Malformed or unresolved citations receive explicit non-verified states.
- A citation may be labelled likely fabricated only if a stored negative official-registry check records the checker, source, URL, and timestamp.
- Network failure, discovery failure, or absence from the pilot corpus never becomes proof of fabrication.

Limitation:

- Existence is determined from the bounded corpus and reviewed registry records, not through a comprehensive live Singapore citator.

### Level 2: Wrong metadata

**Status: Fully implemented as an MVP check**

Implemented behaviour:

- Parsed case-name mentions can be compared with canonical authority metadata.
- Neutral-citation court codes can be compared with stored court metadata.
- Exact paragraph labels are checked.
- The audit result can expose case-name mismatch, court mismatch, and pinpoint mismatch flags.

Limitations:

- Name matching is heuristic rather than a full party-name entity-resolution system.
- The system does not verify judge, panel, reporter volume, or every formal citation-style component.

### Level 3: Wrong proposition

**Status: Partially implemented**

Implemented behaviour:

- Claims are mapped to a controlled legal-proposition taxonomy.
- Evidence matching is restricted to stored passages annotated for the relevant proposition.
- TF-IDF ranks candidates but does not determine truth.
- An authority or pinpoint supporting a different proposition is flagged as unsupported or context review.
- Exact stored quotations and paragraph labels are returned with the decision rationale.

Missing proposal elements:

- There is no trained or calibrated Legal NLI layer assessing entailment, contradiction, and neutrality.
- Runtime evaluation does not yet consume approved Case Map roles and limitations as its primary source.
- There is no proposition-level expert agreement dataset large enough to validate semantic generalisation.

Reason:

The MVP deliberately uses deterministic annotated proposition matching because an uncalibrated LLM-as-judge would recreate the “Who audits the auditor?” problem.

### Level 4: Wrong reasoning role or legal force

**Status: Partially implemented**

Implemented behaviour:

- Case Map annotations support holding, ratio candidate, obiter candidate, party submission, factual finding, procedural history, and disposition roles.
- Annotations record modality, limitations, applicability factors, paragraph anchors, quotations, model confidence, validation, and review status.
- Deterministic validation prevents unanchored quotations and invalid roles from reaching review.
- The audit engine detects some overstatement terms, such as must, always, automatically, and equivalent universal language.
- Court tier, source provenance, precedential status, currency status, and reviewer metadata can be displayed.

Missing proposal elements:

- Normal audit verdicts do not yet query approved Case Maps end to end.
- There is no runtime classifier for majority versus dissent, quoted external authority versus the deciding court's view, adopted versus rejected reasoning, or procedural dictum.
- Binding and persuasive status is stored or reviewed rather than automatically derived from a complete forum-aware authority graph.

Reason:

These distinctions require legally reviewed structural annotations. The preprocessing and review foundation exists, but automatically treating model-produced role labels as law would be unsafe.

### Level 5: Material omission or one-sided analysis

**Status: Partially implemented**

Implemented behaviour:

- Full audit mode compares extracted propositions with a versioned issue checklist.
- It can emit potential omission, potentially one-sided, missing limiting authority, and policy factor not addressed review prompts.
- Negative findings identify the jurisdiction, legal domain, corpus version, checklist version, landmark-set version, search scope, and known limitations.
- A citation-coverage gate prevents a high overall score when material claims remain unsupported.

Missing proposal elements:

- There is no independent retrieval system searching authorities that are absent from the submitted answer.
- The issue graph contains only a bounded employment-restraint pilot configuration and candidate landmark authorities.
- Landmark candidates and legal roles still require legal-team sign-off.
- There is no graph-centrality or treatment-aware materiality calculation.

Reason:

Completeness cannot be proven by reusing only the authorities supplied by the answer. The current system correctly presents omissions as scoped review prompts rather than conclusive errors.

## 3. Four-question audit spine and asymmetric execution

**Status: Four-question output fully implemented; asymmetric execution only partially implemented**

### Fully implemented

Every audited claim is explained through:

1. **Q1 — Does the source exist and resolve?**
2. **Q2 — Does the cited passage support the proposition?**
3. **Q3 — Is the authority used in the correct legal context and with appropriate force?**
4. **Q4 — What material issue or authority may be missing?**

The API supplies question-specific findings, reasons, assessment status, and evidence. The dashboard renders the spine for lawyers rather than presenting a single opaque score.

### Partially implemented

- Q1 and most Q2 deterministic checks run synchronously.
- Q3 uses metadata, lexical modality checks, proposition annotations, and reviewed overlays where available.
- Q4 uses the versioned pilot checklist and landmark candidate set.
- The response separately exposes reasons when a question or module was not assessed.

### Not implemented

- Q4 does not run through an independent retrieval index.
- Q3 and Q4 are not dispatched asynchronously after an immediate Q1 result.
- The system has no service-level objectives or queue-backed fan-out across claims and checks.

The proposal's intended asymmetry is represented in architecture and disclosure, but the current engine remains a synchronous local MVP.

## 4. Core data representations

### 4.1 Case Map

**Status: Preprocessing and review fully implemented; runtime consumption partially implemented**

Fully implemented:

- Case Maps are overlays keyed by normalised citation, immutable source-document hash, and schema version.
- Gemini can generate draft annotations only from selected stored paragraphs and nearby context.
- The model must return exact paragraph labels and short quotations.
- Deterministic validation checks same-document anchors, quote presence after whitespace normalisation, controlled taxonomy values, source hash, duplicate chunks, and valid references.
- Drafts record model, prompt, schema, annotator, and extractor versions.
- Reviewers can edit, approve, reject, and supersede annotations without mutating source snapshots.
- A changed judgment hash makes the earlier Case Map stale.
- PDF-derived Case Maps are separated from official snapshots and receive user-supplied provenance unless independently validated.
- The dashboard provides generation, paragraph review, annotation editing, validation feedback, and version history.

Partially implemented:

- Annotation provenance distinguishes model drafts, deterministic validation, and reviewer status, but the proposal's exact Tier A, Tier B, and Tier C field model is not fully materialised as a queryable tier property.
- Some Tier A metadata exists, but panel composition, all cited authorities, statutes considered, and complete judgment structure are not guaranteed.
- The platform does not yet report separate benchmark error rates for human-reviewed fields versus model-generated fields.
- Most importantly, approved Case Maps are not yet the primary evidence repository used by the normal audit engine. The live engine still evaluates stored authority passages and proposition annotations.

Not implemented:

- A full judicial-decision decomposition for every active authority is not guaranteed.
- Case Map generation is not an automatic deployment prerequisite for every refreshed judgment.

### 4.2 Issue Graph

**Status: Partially implemented as a static pilot policy**

Implemented:

- A versioned assurance-policy file contains one bounded issue checklist for Singapore employment restraints.
- It includes trigger propositions, expected issues, policy issues, and a small candidate landmark-authority set.
- Full audit mode can compare extracted answer propositions against these configured expectations.

Not implemented:

- There is no general graph service with first-class nodes and edges for rules, exceptions, factors, remedies, policy concerns, determining authorities, competing lines, and treatment relations.
- There is no multi-domain coverage, graph traversal, graph centrality, or automatic graph construction.
- Issue graph changes have no dedicated legal approval workflow distinct from the policy file.

Reason:

A static, inspectable checklist was feasible and safer for the 24-hour bounded pilot. A trustworthy general issue graph requires substantial legal curation and licensed source coverage.

### 4.3 Claim Graph

**Status: Fully implemented for the MVP representation; partial for complex legal documents**

Implemented:

- Parsed claims become claim nodes with controlled proposition codes.
- Citation mentions become source references.
- Claim-to-citation and claim-to-evidence links are exposed in a structured graph.
- Unsupported assertion nodes are explicitly identified.
- Coverage and gate calculations consume the graph rather than only a document-level score.
- The dashboard exposes the claim graph and unsupported assertions.

Limitations:

- The local parser generally associates one nearest citation set with a sentence-level claim.
- It does not fully resolve footnotes, citation clusters, supra and ibid references, cross-references, quotations spanning sentences, or one citation jointly supporting multiple subclaims.
- Ambiguous edges are not represented with a dedicated ambiguity state.

### 4.4 Treatment Graph

**Status: Schema and review overlay implemented; operational graph traversal not implemented**

Implemented:

- The data model supports follows, applies, distinguishes, limits, criticises, overrules, and cites relationships.
- Treatment records require source and target authorities, paragraph evidence, source-document hash, reviewer, and timestamp.
- Only approved treatment information is permitted to affect currency review.
- Unknown currency is disclosed as not verified.
- Negative treatment creates a review flag rather than an automatic claim that an authority is no longer good law.

Not implemented:

- Normal audits do not traverse a populated treatment graph.
- AI-proposed edges are not automatically validated against later authorities.
- There is no issue-specific positive or negative treatment propagation.
- There is no automatic downstream invalidation when a treatment edge changes.

Reason:

The schema is a scalability foundation, but a citator-quality treatment graph requires broader corpus coverage and legal review.

## 5. Verification engine

### 5.1 Deterministic citation and source checks

**Status: Partially implemented**

Implemented:

- citation extraction;
- tolerant Singapore neutral-citation normalisation;
- exact corpus lookup;
- canonical citation matching;
- case-name and court-code mismatch checks;
- pinpoint existence checks;
- cited-pinpoint-first evidence handling;
- exact quotation verification after whitespace-only normalisation;
- source-document hashes and provenance;
- conservative fabricated-citation safeguards.

Not implemented:

- full Singapore citation-style grammar;
- parallel-reporter reconciliation;
- judge and panel verification;
- automated statute section existence;
- statute version and amendment currency;
- comprehensive licensed-database reconciliation;
- live citator status.

### 5.2 Resolution states

**Status: Partially implemented**

The current verdict and flag system distinguishes valid resolution, malformed citation, unresolved authority, context review, unsupported proposition, unverified source, and registry-supported likely fabrication.

It does not implement the proposal's exact resolution-state vocabulary:

- VERIFIED_EXACT;
- VERIFIED_WITH_METADATA_MISMATCH;
- AMBIGUOUS;
- UNRESOLVED;
- MALFORMED.

There is also no controlled fuzzy fallback with explainable candidate ranking. The stricter current behaviour is intentional: uncertainty remains unresolved rather than being forced into a match.

### 5.3 Constrained retrieval

**Status: Partially implemented**

Implemented:

- retrieval within the cited authority;
- pinpoint-first assessment when a pinpoint is supplied;
- proposition-annotation filtering;
- TF-IDF ranking of stored passages;
- exact paragraph evidence in the result;
- explicit rule that similarity does not determine truth.

Not implemented:

- BM25;
- dense embeddings;
- cross-encoder reranking;
- hierarchical issue, section, and paragraph retrieval;
- windows centred on a pinpoint;
- candidate comparison across full Case Maps;
- separate retrieval indices for submitted and independent completeness searches.

Reason:

The bounded corpus makes transparent lexical ranking sufficient for the demonstration. More retrieval layers would add complexity without a legally reviewed dataset proving improvement.

### 5.4 Legal NLI

**Status: Not implemented**

The proposal calls for entailment, contradiction, and neutral scores with hard contradiction gates. The current engine does not run a local NLI model or use Gemini to decide these labels.

Instead it relies on:

- controlled proposition annotations;
- exact authority and pinpoint resolution;
- exact quotation anchoring;
- stored limitations;
- deterministic overstatement and mismatch rules.

Reason:

No expert-labelled legal NLI calibration set exists in the project. Adding an off-the-shelf or prompt-only NLI model would create an unmeasured evaluator hallucination risk. The UI therefore must not imply that logical contradiction has been model-tested.

### 5.5 Context classifier

**Status: Partially implemented in preprocessing; not integrated end to end in runtime**

Implemented:

- Case Map role labels for holding, ratio candidate, obiter candidate, party submission, factual finding, procedural history, and disposition;
- paragraph-linked evidence and lawyer approval;
- modality, limitations, and applicability factors.

Missing:

- live-audit lookup of approved role labels;
- majority versus dissent classification;
- quoted external authority versus current court voice;
- adopted versus rejected argument classification;
- procedural dictum detection.

### 5.6 Authority appropriateness

**Status: Partially implemented**

Implemented:

- jurisdiction, court code, court tier, target forum, source provenance, precedential status, and review metadata;
- Singapore court hierarchy display;
- configurable foreign-jurisdiction research priority;
- safeguards preventing hierarchy alone from creating semantic support.

Missing:

- comprehensive automatic binding-status derivation;
- a complete forum-aware treatment graph;
- runtime scoring across all proposed factors;
- a dense, legally reviewed foreign-authority corpus.

### 5.7 Modal calibration

**Status: Partially implemented**

Implemented:

- extraction and display of Case Map modality labels;
- heuristic detection of universal and mandatory terms;
- flags when absolute language conflicts with known qualifications or limitations.

Not implemented:

- the proposal's explicit 1-to-4 asserted-strength and warranted-strength scales;
- signed modal-gap calculation;
- consistent underclaiming detection;
- calibrated modal thresholds.

### 5.8 Completeness and negative findings

**Status: Disclosure format fully implemented; substantive search partially implemented**

Implemented:

- full-mode issue checklist comparison;
- landmark candidate comparison;
- scoped omission and one-sidedness prompts;
- negative-finding records identifying what was searched, the versions used, and what was not assessed;
- cautious language that absence is not proof of completeness.

Not implemented:

- independent retrieval against a broader authority corpus;
- graph-aware missing-authority analysis;
- legally approved determining-authority coverage;
- full severance, remedy, policy, and competing-line reasoning across multiple domains.

## 6. Assurance layer

### 6.1 Metrics

**Status: Partially implemented**

Implemented:

- fixed-fixture verdict correctness;
- per-module benchmark presentation;
- confusion matrix;
- fabricated-citation precision;
- false-positive count;
- deterministic run count, error count, P50, and P95 latency;
- version identifiers for the engine, corpus, taxonomy, and assurance policy.

Not implemented:

- precision, recall, and F1 for every individual check;
- explicit false-negative rates;
- per-failure-level confidence intervals;
- NLI accuracy and calibration;
- abstention accuracy;
- error-direction reporting;
- inter-evaluator agreement;
- cost per query;
- separate error rates for human-reviewed and model-generated Case Map fields.

Why:

The present fixture count is too small to support robust statistical claims. The dashboard appropriately calls the result fixture correctness rather than general legal accuracy.

### 6.2 Evaluator independence

**Status: Partially implemented**

Implemented:

- ProofMark evaluates pasted outputs rather than asking the originating legal AI to self-grade.
- Deterministic citation, quote, source, and proposition checks are separated from Gemini extraction.
- Gemini cannot directly assign verdicts.
- Gold fixtures are separated from runtime machine-generated annotations.
- Model, prompt, parser, source, and reviewer provenance are exposed.

Missing:

- independent retrieval for Q4;
- multiple evaluator-model providers;
- independence scoring by component;
- controls detecting whether the same source corpus or annotations were used by both generator and evaluator.

### 6.3 Calibration

**Status: Not implemented**

The system records parser confidence and model annotation confidence, but these are not empirically calibrated probabilities of legal correctness.

Missing proposal requirements include:

- reliability diagrams;
- expected calibration error;
- Brier score;
- threshold calibration on a held-out legal set;
- calibrated abstention thresholds.

The UI should continue to state that confidence values are process metadata, not the probability that a legal conclusion is correct.

### 6.4 Benchmark design

**Status: Partially implemented**

Implemented:

- a legally bounded six-authority gold corpus;
- fixed known-good and known-bad cases;
- adversarial examples covering valid support, wrong pinpoint, wrong court or case identity, wrong proposition, party submission, obiter, qualified language, omission, one-sided analysis, secondary commentary, fabricated citation, unknown citation, and out-of-scope claims;
- separation between gold fixtures and the active runtime snapshot;
- a deterministic 250-run performance batch.

Missing:

- a production-derived benchmark partition;
- formal sampled, adversarial, and mutation-generated partitions;
- automated mutation generation;
- density controls for cases, statutes, and secondary sources;
- a representative distribution across practice areas and courts;
- benchmark refresh and retirement workflows;
- red-team release gates.

### 6.5 Error taxonomy coverage

**Status: Partially implemented**

The proposal's behaviours are broadly represented through verdicts, flags, and fixtures, including fabrication, identity mismatch, wrong pinpoint, wrong proposition, authority-role error, modal overstatement, negative treatment, omission, one-sidedness, and provenance limitations.

However, the exact codes H1, H2, H3, M1, M2, P1, P2, P3, C1, C2, C3, A1, A2, A3, O1, O2, O3, S1, S2, and S3 are not persisted as a first-class failure-code field. This limits longitudinal analytics and direct comparison with the proposal.

### 6.6 Bias and robustness

**Status: Not implemented as a statistically valid module**

Missing:

- performance stratification by court level;
- jurisdiction and practice-area slices;
- party-type and represented-versus-unrepresented slices;
- older-versus-recent decision analysis;
- short-versus-long judgment analysis;
- retrieved-versus-unretrieved authority analysis;
- intersectional robustness analysis;
- statistical uncertainty for each slice.

Reason:

The six-authority employment-restraint benchmark cannot support credible bias conclusions. Adding charts without sufficient data would create false assurance.

### 6.7 Score gates and configurable weights

**Status: Fully implemented as an MVP policy mechanism**

Implemented:

- versioned module weights stored in a policy file;
- citation-integrity, propositional-accuracy, relevance-and-currency, and balance-and-completeness scores;
- overall scoring only in full mode;
- no misleading re-normalised total for citation-only mode;
- hard gates that can cap or block scores when citation coverage or unsupported material claims fail;
- separate display of module scores and gate reasons;
- policy, checklist, landmark-set, engine, taxonomy, and corpus versions.

Partially implemented:

- the proposal describes seven sub-dimensions; the MVP consolidates them into four modules.
- currency gates depend on reviewed overlays rather than a full treatment graph.
- the proposed contradiction gate is not active because Legal NLI is absent.
- there is no history of expert refitting, threshold calibration, or weight-performance comparison.

## 7. Governance layer

### 7.1 Practitioner feedback

**Status: Partially implemented**

Implemented:

- every audited claim can be flagged;
- supported categories include wrong verdict, wrong proposition, wrong pinpoint, incorrect Case Map role, missing authority, missing context, outdated authority, and other;
- an explanation is required;
- proposed citation, paragraph, and correction information may be included;
- feedback follows submitted, under review, accepted or rejected states;
- submitting feedback marks the assessment under review without changing the verdict or score;
- only reviewer and owner roles may resolve feedback or approve Case Maps;
- accepted feedback can create an auditable revision rather than retraining Gemini.

Missing:

- direct capture of the four-question identifier;
- exact check name and proposal failure code;
- error direction, severity, and scored-unit identifier as dedicated fields;
- false-positive and false-negative recalibration reports;
- automatic threshold updates from accepted feedback.

Why:

The system correctly avoids real-time self-learning. Human flags are evidence for controlled review, not ground truth that should immediately alter legal conclusions.

### 7.2 Reviewer reputation, double review, and dissent

**Status: Not implemented**

Missing:

- reviewer expertise profiles;
- reputation weighting;
- mandatory second review for material changes;
- formal dissent records;
- adjudication workflow;
- conflict-of-interest controls.

The current role model distinguishes members, reviewers, and owners, and the event history records approvals and corrections. That is a useful foundation, but it is not the governance system proposed for production.

### 7.3 Versioned human changes

**Status: Fully implemented for Case Map review history**

Implemented:

- source snapshots remain immutable;
- reviewer changes create new annotation revisions;
- review events are append-only;
- approvals, rejections, and supersession are recorded;
- model, prompt, schema, source hash, reviewer, and timestamp provenance is retained;
- an updated source hash makes an earlier Case Map stale.

Limitations:

- the guarantee has been verified in application tests and SQL definitions, but the newest migration has not yet been confirmed as applied to the connected hosted Supabase project.

### 7.4 Reverse dependency index

**Status: Designed in schema; not operational**

Implemented:

- Supabase schema and migration structures exist to associate source or Case Map changes with downstream dependencies.

Not implemented:

- no service populates all dependency edges;
- no background job identifies affected past audits;
- no automatic recomputation or invalidation occurs;
- no practitioner notification is sent when a prior result may have changed.

This must be described as a scalability and governance foundation, not a working feature.

### 7.5 Benchmark lifecycle

**Status: Not implemented**

The proposal's lifecycle of proposed, under double review, approved, active, retired, or superseded is not implemented as a complete benchmark-governance workflow. Fixtures are version-controlled in the repository and separated from runtime data, but there is no database-backed approval lifecycle or automatic retirement process.

## 7A. Implementation update: demonstrations and tier runner

**Status: Fully implemented for the bounded local demonstration path**

The following proposal demonstrations now run from the **Demos 1–5** dashboard
route and the VERITAS API:

| Demo | Implemented detection | Authoritative basis |
|---|---|---|
| 1. Fictitious authority | Court-confirmed non-existence plus citation gate; false citation remains redacted | [2026] SGHC 49 at [10] and [24] |
| 2. Real citation, wrong case name | Canonical case-name/citation identity mismatch | Shopee [2024] SGHC 29 |
| 3. Accurate words, wrong proposition | Exact quote passes while proposition support fails | Shopee [2024] SGHC 29 at [59] |
| 4. Non-majority reasoning as holding | Source-role mismatch identifies a quoted foreign dissent | Man Financial [2007] SGCA 53 at [130] |
| 5. Later rejection of relied-on approach | Reviewed, issue-specific negative-treatment gate | Smile Inc [2012] SGCA 39 at [33] |

Demo 4 is not described as a Singapore dissent because no legally defensible
in-domain Singapore dissent was available. Demo 5 is not labelled formal
overruling: it demonstrates issue-specific later rejection and raises a
currency-review flag.

All four scalability tiers are executable in this bounded path:

- Tier 0 runs deterministic source, citation, identity, pinpoint, quotation,
  modality, court and jurisdiction checks on every demo.
- Tier 1 executes claim/evidence, proposition, role and modality checks in
  parallel across the five demonstrations. It does not require model inference.
- Tier 2 runs on every escalated item and performs an independent locked-source
  role or reviewed-treatment check. Random sampling remains disabled until a
  measured sample rate is configured.
- Tier 3 persists critical and currency-sensitive items to a local review
  queue. Two different qualified lawyers must confirm an item before it becomes
  a gold candidate. No human decision is synthesized.

The tier runner is a hackathon-scale implementation, not a claim of distributed
production capacity. Queue-backed worker fleets, cross-provider NLI ensembles,
hosted load tests and organisation-wide review operations remain future work.

Every proposal marker labelled TARGET or TO BE MEASURED is represented in
`api/data/veritas_operating_config.json`: latency targets, Tier 2 sampling,
confidence thresholds, per-band accuracy, component metrics, dashboard figure
policy, and indicative scoring weights. Null renders as unmeasured. Observed
run time is never compared with an invented target.

The source ledger refuses to load if a source hash, paragraph anchor, allowed
official host or referenced fixture is missing or changed. The old synthetic
future-dated fixture and Supabase negative-registry seed were removed.
Supabase now seeds authority metadata only; exact passage text must enter
through the official source-hashed refresh pipeline. Legacy gold proposition
paraphrases are explicitly typed as legal-team summaries and are not labelled
judgment text.

## 8. Scalability architecture

**Status: Fully implemented for demos; partially implemented for production**

### Implemented foundations

- synchronous deterministic audit processing;
- warmed TF-IDF vectors;
- bounded immutable snapshots;
- source hashing and cache reuse;
- automated official-judgment refresh with robots checking, throttling, retries, validation, and last-good fallback;
- background execution pattern for refresh and Case Map preprocessing;
- audit states that can represent queued, running, complete, and failed work;
- versioned preprocessing artefacts reusable while source hashes remain unchanged;
- a local 250-run deterministic performance measurement;
- Supabase schema designed for indexed, organisation-scoped persistence.
- deterministic Tier 0 execution for every demonstration;
- parallel Tier 1 claim/evidence execution;
- escalation-only Tier 2 source-role and reviewed-treatment checks;
- durable local Tier 3 queue with double qualified-lawyer review and dissent
  capture.

### Not implemented

- queue-backed worker fleet;
- incremental NLI scoring;
- background completeness retrieval;
- confidence-based audit assignment;
- cached global treatment graph;
- production load testing at thousands of daily queries;
- deployed observability, autoscaling, retry queues, and service-level objectives;
- pgvector or a cross-encoder retrieval service.

### Why

The MVP is intentionally synchronous and local. It proves that deterministic checks are fast after warm-up, but that measurement does not prove distributed throughput, hosted latency, concurrent-user capacity, or database performance.

The pitch may say the architecture separates reusable preprocessing from per-query checks and is designed to evolve into tiered workers. It should not say that the current deployment already processes thousands of daily queries.

## 9. “Who audits the auditor?” implementation

**Status: Partially implemented**

The proposal gives five answers. Current coverage is:

| Assurance answer | Status | Current implementation |
|---|---|---|
| Deterministic checks | **Partial** | Citation, source, pinpoint, quote, hashing, and provenance checks work. Statute currentness and a full citator do not. |
| Evaluator independence | **Partial** | The evaluator is separate from the submitted output and Gemini cannot decide verdicts. Independent retrieval and provider diversity are absent. |
| Calibration | **Not implemented** | Confidence values are uncalibrated metadata, not probabilities. |
| Structured human feedback | **Partial to strong** | Controlled flag, review, resolution, Case Map revision, two-lawyer Tier 3 confirmation and dissent capture exist. Reputation and automatic recalibration do not. |
| Provenance-aware confidence | **Partial to strong** | Model, prompt, source, corpus, taxonomy, policy, reviewer, and status metadata are exposed, but runtime Case Map consumption and conditional reliability are incomplete. |

The practical answer demonstrated by the MVP is narrower:

> The auditor is constrained by exact sources, deterministic rules, immutable provenance, separated gold fixtures, transparent abstention, and reviewable human corrections. It is not assumed to be infallible.

## 10. Result presentation and audit trail

**Status: Mostly fully implemented**

Implemented at claim level:

- verdict label;
- severity and escalation requirement;
- four-question findings;
- source existence and citation identity;
- canonical citation and pinpoint;
- exact stored passage and source URL;
- proposition match;
- decision rationale and decision-rule identifier;
- source provenance and source status;
- parser and fallback information;
- engine, corpus, taxonomy, policy, model, prompt, and Case Map versions where available;
- court and source hierarchy;
- currency status;
- unsupported-claim graph;
- negative findings;
- practitioner-feedback state;
- lawyer handoff for non-verified claims.

Partially implemented or missing:

- NLI entailment, contradiction, and neutral scores;
- asserted-strength, warranted-strength, and signed modal gap;
- a reliable live Case Map role and approval field consumed by every audit;
- conditional reliability derived from a calibrated metric;
- exact proposal failure codes;
- formal dissent state.

The dashboard is therefore strong as an evidence-linked review interface, but it should not imply that every displayed dimension has been independently model-tested.

## 11. MVP checklist from the proposal

| Proposed MVP item | Status | What currently exists | Remaining limitation |
|---|---|---|---|
| 1. Curate a small, legally reviewed corpus | **Partially implemented** | Six named Singapore judgments form the separated gold benchmark; the official refresh can build a bounded runtime snapshot of up to 25 judgments. | Legal sign-off is still required for all annotations, including the added Smile Inc and MoneySmart material. The currently active runtime snapshot may be empty until a successful refresh and activation. |
| 2. Build deterministic citation, metadata, pinpoint, quote, statute, and treatment checks | **Partially implemented** | Citation, metadata, pinpoint, quote, source hash, and negative-registry safeguards work. | Automated statute validation and a real citator or treatment graph do not. |
| 3. Build a claim graph | **Fully implemented for the MVP** | Claims, citation relationships, evidence links, unsupported assertions, coverage, and gates are exposed. | Complex footnotes and many-to-many legal-document citation structures remain limited. |
| 4. Add constrained proposition support checking | **Partially implemented** | Retrieval stays inside the resolved authority, prioritises the cited pinpoint, filters by proposition tags, and returns exact evidence. | No Legal NLI, cross-encoder, or approved Case Map runtime reasoning. |
| 5. Add one independent completeness retrieval path | **Not implemented** | A static issue checklist and landmark candidate set generate scoped prompts. | There is no independent search over a broader corpus. |
| 6. Add narrow context classification | **Partially implemented** | Case Map preprocessing identifies roles, modality, limitations, and applicability factors with evidence anchors and human review. | Normal audits do not yet consume those approved annotations end to end. |
| 7. Add abstention and hard gates | **Partially to fully implemented** | Unknown sources stay unverified, non-verified claims escalate, overall scoring is gated, and citation-only mode avoids a false total. | No calibrated abstention threshold or NLI contradiction gate. |
| 8. Build a fixed benchmark with adversarial cases | **Partially implemented** | Fixed adversarial fixtures and six gold authorities run deterministically with a performance batch. | The benchmark is small, not production-derived, and lacks automated mutation and lifecycle governance. |
| 9. Expose provenance and conditional reliability | **Partially implemented** | Rich engine, source, model, prompt, reviewer, corpus, policy, taxonomy, and fallback provenance is shown. | Conditional reliability is not statistically calibrated. |
| 10. Add structured practitioner feedback and recalibration | **Partially implemented** | Controlled feedback, under-review state, role-based resolution, Case Map revision, and a separate two-lawyer Tier 3 queue with dissent capture exist. | No automated recalibration or reviewer reputation. |

## 12. Demonstration scenarios

**Status: Fully implemented for the bounded, source-locked demo suite**

The current five scenarios and their exact source anchors are documented in
section 7A. Each run returns its expected and actual detection code, verdict,
gate state, official evidence, checked hash, and a four-tier trace.

The suite deliberately preserves three boundaries:

- an arbitrary unknown citation remains unverified unless an approved official
  non-existence record exists;
- an exact quotation is not treated as support for a different proposition;
- issue-specific negative treatment is not relabelled as formal overruling.

The ordinary full-audit path retains additional omission and one-sidedness
prompts. Those are bounded checklist prompts, not proof that an independent
search found every omitted authority.

## 13. Source and model hierarchy

### Court and precedential hierarchy

**Status: Partially implemented**

Implemented:

- jurisdiction and court code;
- court tier and target forum;
- reviewed precedential-status field;
- separate treatment of domestic and foreign authorities;
- configurable Singapore, UK, Australia, and US research priority;
- dashboard explanation that research priority is not a legal verdict rule.

Not implemented:

- automatic nuanced stare decisis conclusions;
- comprehensive forum-aware binding analysis;
- foreign judgment corpus and treatment graph.

### Source hierarchy

**Status: Partially implemented**

Implemented:

- officially sourced judgments;
- separated gold fixtures;
- user-supplied PDF provenance;
- rejected or unverified source states;
- metadata-only secondary-source records;
- safeguards preventing unverified PDFs or secondary commentary from independently verifying a rule of law.

Not implemented:

- licensed law-report or journal-content ingestion;
- full-text journal, textbook, or commentary search;
- automatic secondary-source quality ranking.

The application does not contain a pre-existing comprehensive collection of journals and articles. It stores only metadata for secondary sources. This is deliberate for copyright, licensing, provenance, and time constraints.

### Decision-authority hierarchy

**Status: Fully implemented as a policy and disclosure**

The design distinguishes:

1. deterministic source and citation checks;
2. gold benchmark annotations;
3. lawyer-approved Case Map annotations;
4. approved registry and treatment records;
5. AI-supported paragraph labels;
6. TF-IDF ranking;
7. pending practitioner feedback.

The strongest current implementation safeguard is that neither Gemini output, lexical similarity, nor pending feedback can independently create a verified legal conclusion.

Runtime limitation:

Lawyer-approved Case Maps sit in the hierarchy but are not yet consistently consumed by the normal audit engine.

## 14. PDF intake

**Status: Fully implemented for the scoped text-PDF path**

Implemented:

- text-based PDF intake;
- 15 MB size limit;
- expected neutral citation;
- optional official source URL;
- pinned PDF extraction dependency;
- rejection of encrypted, scanned, empty, and malformed PDFs;
- numbered-paragraph preservation where available;
- SHA-256 content hashing;
- extracted-text processing without retaining the binary as an official source;
- user-supplied provenance unless official identity is independently validated;
- creation of a Case Map draft without activating or replacing the official snapshot.

Limitations:

- no OCR;
- no layout-aware reconstruction for complex PDFs;
- no automatic proof that a supplied URL is an official copy;
- PDF evidence can produce at most context review.

## 15. Official-judgment refresh foundation

**Status: Fully implemented as a bounded MVP connector**

Implemented:

- bounded Singapore Courts topic discovery;
- maximum document cap;
- robots validation;
- source-host allowlist;
- throttling, retry handling, and citation-heading validation;
- numbered-paragraph extraction;
- content hashing;
- immutable local snapshots;
- last-good fallback;
- optional Gemini paragraph labelling;
- activation without rewriting past snapshots;
- local background execution;
- refresh API endpoints;
- provenance and coverage reporting;
- pre-warmed lexical search after activation;
- a database function and schema path for atomic snapshot activation.

Important operational qualification:

The refresh code existing in the repository does not prove that a non-empty snapshot is currently active or that every discovered judgment is legally relevant. The presentation environment should run and inspect the documented snapshot command before the demo. Automated source ingestion remains at most context review until legal annotation is approved.

## 16. Supabase persistence and security

**Status: Implemented in code and schema; hosted deployment verification incomplete**

Implemented in the repository:

- organisation and membership model;
- role-aware review permissions;
- organisation-scoped audits, Case Maps, feedback, and overlays;
- RLS on exposed application tables;
- explicit anonymous revocation and deliberate grants;
- browser read-only rules for derived assessments;
- service-side mutation path through FastAPI;
- indexed foreign keys and review-queue access paths;
- security-invoker view requirements;
- declarative schema files;
- generated migrations;
- RLS tests for same-organisation access, cross-organisation denial, member feedback, and reviewer or owner actions;
- provenance and reverse-dependency additions in the latest migration.

Partially verified:

- application and SQL tests cover the intended model locally;
- the newest migration has not been confirmed as applied to the connected project at zxjaccusnmunjgktzkme.supabase.co;
- database advisors and the complete pgTAP suite have not been confirmed against that hosted project.

Consequently, the accurate status is “Supabase persistence and RLS are implemented in the codebase, with hosted migration and security verification still required,” not “the production database is fully deployed.”

## 17. Public API and dashboard

### API

**Status: Mostly fully implemented for the MVP**

Implemented:

- health, corpus, audit, retrieval, benchmark, assurance, hierarchy, refresh, Case Map, PDF import, feedback, review, and approval interfaces;
- citation-only and full audit modes;
- answer, question, facts, parser, and persistence validation;
- parser fallback;
- local and Supabase repository paths;
- complete audit responses with provenance, evidence, scores, gates, questions, and handoff information.

Limitations:

- background Case Map and refresh patterns do not constitute a distributed job system;
- no public API for arbitrary candidate-system benchmarking;
- no streaming or asynchronous audit completion contract;
- Supabase-backed mutation depends on local secret and account configuration.

### Dashboard

**Status: Mostly fully implemented for the MVP**

Implemented:

- audit worklist and new-audit flow;
- citation-only and full-mode input;
- evidence-linked claim detail;
- four module scores and four-question findings;
- claim graph and unsupported assertions;
- hierarchy, modality, currency, pinpoint, omission, and balance displays;
- negative-findings disclosure;
- authority inventory and refresh provenance;
- Case Map generation, source review, annotation editing, validation, approval, and history;
- practitioner feedback;
- benchmark correctness and performance reporting;
- Assurance page explaining boundaries, trust hierarchy, current architecture, and roadmap;
- local demo fallback labelled as a saved demonstration result.

Limitations:

- some screens show architectural fields whose data may be absent until Case Maps, overlays, or the hosted migration are populated;
- visual presence does not mean the corresponding runtime evaluator check is complete;
- the dashboard is not evidence of production concurrency or hosted availability.

## 18. Explicit non-claims from the VERITAS SG proposal

**Status: Mostly respected**

The current product should explicitly retain the following non-claims:

- It does not replace lawyers.
- It does not prove truth outside the bounded corpus and validated checks.
- It does not treat lexical similarity as legal correctness.
- It does not infer citation absence from a failed network request.
- It does not treat secondary commentary as binding law.
- It does not make automatic adverse treatment conclusive.
- It does not silently convert model confidence into legal confidence.
- It does not allow practitioner feedback to change verdicts automatically.
- It does not allow runtime machine annotations to produce the benchmark-only verified label.

One slogan should be used cautiously:

> Every claim. Verified against authority. Explained with evidence.

Because not every claim can be verified, a safer and more technically accurate formulation is:

> Every claim checked; every finding traceable.

## 19. Roadmap requirements that remain unimplemented

### Phase 2

- graph-aware completeness retrieval;
- operational treatment graph;
- approved Case Map runtime consumption;
- statute validation and versioned statutory currentness;
- calibrated narrow context and contradiction models;
- benchmark mutation generation;
- richer reviewer analytics.

### Phase 3

- broader practice-area corpus;
- foreign authority and secondary-material metadata at useful scale;
- bias and robustness dashboards with adequate samples;
- active-learning proposals under controlled legal review;
- reviewer reputation, double review, dissent, and adjudication;
- benchmark lifecycle automation;
- reverse-dependency recomputation and notifications.

### Phase 4

- licensed source connectors;
- queue-backed worker deployment;
- asynchronous tiered evaluation;
- production concurrency and failure testing;
- enterprise tenant administration;
- external security review;
- drift detection and observability;
- formal release and rollback controls.

## 20. Production deployment gate

**Status: Not implemented as an enforced gate**

The proposal says production deployment should require benchmark, calibration, provenance, security, throughput, and legal-review thresholds. The current project has useful tests and disclosures, but no automated deployment policy prevents release when a threshold fails.

Missing controls:

- minimum per-check accuracy and false-negative thresholds;
- calibration and abstention thresholds;
- benchmark density and slice requirements;
- required legal sign-off for all active Case Maps and landmark sets;
- verified hosted RLS and database-advisor clearance;
- concurrency, endurance, and failure-recovery tests;
- provenance completeness threshold;
- rollback rehearsal;
- production monitoring and alerting;
- named release approvers.

This is appropriate for a hackathon MVP, but it must be completed before a subscriber-facing legal database could rely on the system.

## 21. Highest-priority next implementation steps

The following order converts the largest proposal gaps into a stronger post-hackathon product:

1. **Connect approved Case Maps to runtime audits.** This activates the role, modality, limitation, and applicability work already present.
2. **Build an independent Q4 retrieval path.** Use a separate index and disclose its bounded search space.
3. **Populate and review the authority-treatment graph.** Start with the six-case domain before attempting an automated citator.
4. **Add statute validation.** Separate existence, version, amendment, repeal, and temporal applicability.
5. **Create an expert-labelled calibration set.** Only then add a narrow Legal NLI or contradiction model.
6. **Persist exact failure codes and scored units.** This enables per-check analytics and feedback-driven evaluation.
7. **Implement reverse-dependency recomputation.** Re-evaluate affected audits when approved sources or maps change.
8. **Expand benchmark governance.** Add partitions, mutations, reviewer agreement, retirement, and versioned release gates.
9. **Verify the hosted Supabase project.** Apply the latest migration, run RLS tests and advisors, and record the result.
10. **Add real scale infrastructure only after evaluator quality is measurable.** Introduce queues, tiered workers, and load tests after correctness and calibration baselines exist.

## 22. Judge-safe summary matrix

| Capability | Honest status | Safe pitch wording |
|---|---|---|
| Citation hallucination detection | **Working within bounded sources and negative registry checks** | “We distinguish verified non-existence from simple corpus absence, preventing false fabrication claims.” |
| Wrong citation metadata and pinpoint | **Working MVP** | “We resolve citations, compare identity metadata, and assess the paragraph actually cited.” |
| Propositional accuracy | **Working deterministic slice** | “We compare claims with lawyer-annotated propositions and exact passages; semantic NLI is future work.” |
| Context and legal force | **Preprocessing and review working; runtime partial** | “Case Maps capture role, modality, limitations, and facts with exact anchors and human approval. Runtime integration is the next step.” |
| Currency | **Reviewed overlay only** | “We expose known treatment and clearly label unknown currency; we do not pretend to have a complete citator.” |
| Completeness and bias | **Bounded review prompts** | “A versioned checklist flags possible omissions, with explicit negative-finding limits. Independent retrieval is planned.” |
| Human feedback | **Working controlled workflow** | “Feedback triggers review and versioned correction; it never silently retrains or changes a verdict.” |
| Benchmark | **Working fixed fixture benchmark** | “The fixture pack passes its expected classifications; this is not a claim of general legal accuracy.” |
| Scalability | **Architecture foundation and fast local engine** | “Immutable preprocessing and deterministic per-query checks are designed for tiered workers; production throughput is not yet claimed.” |
| Supabase | **Code and schema implemented; hosted verification pending** | “The multi-tenant RLS design is implemented, with final hosted migration and advisor checks remaining.” |

## Final conclusion

ProofMark has implemented the central demonstration thesis of VERITAS SG:

- legal-AI output is decomposed into auditable claims;
- citations are resolved conservatively;
- exact source passages and provenance are exposed;
- deterministic rules, not an unconstrained LLM judge, assign verdicts;
- unverifiable claims are withheld or escalated;
- benchmark gold is separated from runtime machine annotations;
- Case Maps and human review create a credible path toward contextual evaluation;
- limitations and negative findings are visible rather than hidden behind one score.

It has not implemented the complete research and production infrastructure needed for a general legal-database quality auditor. In particular, no claim should be made that ProofMark has a comprehensive citator, a calibrated semantic truth model, independent completeness retrieval, statistical bias assurance, or proven production scale.

That boundary does not weaken the hackathon submission. It makes the system's core innovation clearer: ProofMark is an evidence-linked, provenance-aware evaluation framework that knows when it has enough evidence to make a bounded finding and when it must defer to a lawyer.
