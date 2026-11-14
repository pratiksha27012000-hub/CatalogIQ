# CatalogIQ: Product Requirements Document

*Version 2.0 · Owner: Pratiksha (Product) · Last updated 15 Nov 2026 · Status: Portfolio prototype, requirements baseline*

> **How to read this PRD.** Claims are tagged **\[Observed\]** (measured in the prototype), **\[Hypothesis\]** (believed, not yet validated) or **\[Target\]** (a goal, not a result). Nothing here is presented as production data.

## 1. TL;DR

|  |  |
| --- | --- |
| **Problem** | Catalogue teams lose time and trust answering simple questions ("how many products contain cotton?") because product evidence is scattered across titles, descriptions, source metadata and attributes. |
| **Solution** | A conversational copilot that routes each question to the right engine (exact SQL, hybrid filter + retrieval, or semantic search) and always tells the user which kind of answer they are getting. |
| **Why now** | LLMs make natural-language access cheap, but they also make confident wrong answers cheap. The opportunity is a *trustworthy* catalogue copilot, not just a chat box. |
| **Core insight \[Observed\]** | A title-only search found 2 cotton products; a cross-field audit found 8. Naive search understates by 4x. |
| **North Star** | Verified Answer Rate: share of questions answered with an exact, evidence-backed result the user accepts. |
| **Scope today** | One curated 40-product, multi-category catalogue, 315 extracted attributes. Private repo, no public deployment. |
| **Decision requested** | Approve Phase 2: expand evaluation to 3 labelled catalogues and add answer-type labelling and user attribute correction. |

## 2. Problem and opportunity

### 2.1 The problem

Catalogue information is fragmented across product titles, descriptions, commercial fields, source-specific metadata and attributes. Answering one business question often means filtering several columns by hand, or asking an analyst to write a query.

**Problem statement.** Catalogue, category and operations teams need to discover and analyse products in natural language *without losing the distinction between an exact result and a relevance-ranked guess*.

### 2.2 Evidence so far

| Evidence | Status | Implication |
| --- | --- | --- |
| Title-only "cotton" search returned 2 records; cross-field audit found 8 | \[Observed\] | Single-column search silently produces wrong counts. This is the product's reason to exist. |
| 40/40 products had at least one extracted attribute (315 total) | \[Observed\] | Attribute enrichment is feasible on a multi-category catalogue. |
| Catalogue users spend meaningful time on manual multi-field filtering | \[Hypothesis\] | Needs validation through 5 to 8 user interviews (see section 13). |
| Users prefer an answer labelled "candidates" over a confident but unverified number | \[Hypothesis\] | Test in usability sessions; informs UI labelling. |

### 2.3 Opportunity sizing (directional)

I am not claiming a market size from prototype data. The sizing approach for Phase 2 is bottom-up: number of catalogue-owning teams in the target segment, questions asked per week per team, and minutes saved per question. These inputs come from interviews, so the figure is left as an open item rather than invented.

## 3. Target users and jobs to be done

### 3.1 Personas

| Persona | Context and trigger | Pain today | What success looks like |
| --- | --- | --- | --- |
| **Catalogue / Content Manager** | Preparing listings, audits or a new marketplace feed | Cannot find every product with a given material or feature; incomplete data hides products | Finds all matching products, sees the evidence, spots gaps |
| **Category / Merchandising Manager** | Assortment review, promotion planning | Slow price and availability comparisons across groups | A defensible answer in seconds, with the supporting products |
| **E-commerce Operations Manager** | Weekly stock and quality checks | Ad-hoc spreadsheet work that is not repeatable | Repeatable answers for stock exceptions and data quality |

**Primary persona for MVP:** Catalogue / Content Manager. Their questions depend most on cross-field evidence, which is where the product differs from a spreadsheet filter.

### 3.2 Jobs to be done

- When I need an **exact count**, I want it calculated from the full catalogue so I can put it in a report without re-checking.
- When an attribute lives in a description or source metadata, I want search to find it even if the title is silent.
- When I explore a concept ("everyday-wear cotton"), I want a ranked shortlist and a clear statement that it is a shortlist.
- When I select a catalogue, I want certainty that nothing from another catalogue leaks in.

## 4. Alternatives and positioning

| Alternative | Strength | Gap CatalogIQ addresses |
| --- | --- | --- |
| Spreadsheet filters and pivot tables | Familiar, exact | Manual, column-by-column, misses text buried in descriptions or metadata |
| Platform admin search and filters | Built into the store | Usually limited to title and fixed fields; no natural-language questions |
| BI dashboards / SQL analyst | Powerful and exact | Needs an analyst or SQL skills; slow turnaround for ad-hoc questions |
| Generic LLM chat over an uploaded file | Flexible, fast | Can state wrong numbers confidently; no exact-vs-estimate distinction; no evidence trail |

**Positioning.** For catalogue teams who need quick, trustworthy answers, CatalogIQ is a conversational copilot that guarantees exact numbers for supported questions and labels everything else as candidates. Unlike a generic chatbot, it never presents a similarity score as a count.

## 5. Product principles

1. **Trust over fluency.** A correct, labelled answer beats a smooth, uncertain one.
2. **Exact where possible.** Counts, sums and numeric filters are done by the database, never estimated by the LLM.
3. **Show your evidence.** Every product and attribute traces back to a source field.
4. **Say what kind of answer it is.** Exact, Hybrid-verified or Candidate shortlist, always visible.
5. **Catalogues are walls.** Isolation by catalogue ID is non-negotiable.

## 6. Scope and prioritisation

### 6.1 Prioritisation (ICE scoring)

Scores are my estimates (1 to 10) and will be recalibrated after user interviews. Score = Impact × Confidence × Ease.

| Rank | Capability | Impact | Confidence | Ease | Score | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Exact structured counts and numeric filters | 9 | 9 | 7 | 567 | MVP |
| 2 | Cross-field text search | 9 | 9 | 6 | 486 | MVP |
| 3 | Catalogue upload and column mapping | 8 | 8 | 5 | 320 | MVP |
| 4 | Evidence-backed attribute extraction | 8 | 7 | 5 | 280 | MVP |
| 5 | Conversation continuity | 4 | 8 | 8 | 256 | MVP (P1) |
| 6 | Semantic discovery (candidates) | 6 | 7 | 6 | 252 | MVP (P1) |
| 7 | Export filtered result sets | 6 | 5 | 8 | 240 | Phase 2 |
| 8 | Catalogue quality / missing-data report | 7 | 6 | 5 | 210 | Phase 2 |
| 9 | User correction of extracted attributes | 7 | 5 | 4 | 140 | Phase 2 (needs research) |

### 6.2 In scope for MVP

- CSV, XLSX/XLS and JSON upload with preview, mapping and registration.
- Five canonical fields plus preserved source metadata.
- Attribute extraction with source evidence.
- Structured, hybrid and semantic query paths.
- Three-panel Gradio dashboard; per-catalogue isolation.

### 6.3 Deliberately not building (and why)

| Not building | Reason |
| --- | --- |
| Write-back to e-commerce platforms or autonomous price/stock changes | High blast radius; trust in answers must be proven before any action is automated |
| Public deployment, accounts, billing | Would add security and persistence obligations before value is validated |
| Model fine-tuning or GPU inference | Conflicts with the ₹0 budget and does not address the main risk (answer trust) |
| Guaranteed interpretation of every free-form question | Unsupported questions should fail clearly, not guess |

## 7. User stories and requirements

Acceptance criteria are written so each can be tested independently.

### Epic A: Get a catalogue in

| ID | User story | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-01 | As a content manager, I upload CSV, Excel or JSON so I can start without data prep. | P0 | Supported formats load; empty or invalid files are rejected with a plain-language reason. |
| FR-02 | As a content manager, I review proposed column mappings so the canonical fields are right. | P0 | Mappings proposed for the five canonical fields; user can edit before registration. |
| FR-03 | As an analyst, I want fields normalised so queries behave consistently. | P0 | Title, description, selling price, cost price and inventory stored consistently; missing is distinguishable from zero. |
| FR-04 | As an auditor, I want original source data preserved. | P0 | Unmapped source fields retained and searchable. |

### Epic B: Understand the products

| ID | User story | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-05 | As a content manager, I want attributes extracted with evidence so I can trust them. | P0 | Each attribute stores name, value, source field evidence and extraction timestamp where available; unsupported values are not stored. |
| FR-14 | As a manager, I want a catalogue overview so I can judge completeness. | P1 | Completeness shown for each of the five canonical dimensions. |

### Epic C: Ask questions

| ID | User story | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-06 | As an ops manager, I want exact counts and numeric filters so I can report numbers. | P0 | Computed by database execution over the full matching set. |
| FR-07 | As a content manager, I want search across all evidence so nothing is missed. | P0 | General term search covers title, description, source metadata and extracted attributes; narrower scope only when explicitly requested. |
| FR-08 | As a category manager, I want attribute plus filter questions answered together. | P0 | Hybrid path combines filters and retrieval; counts only when semantics support exactness. |
| FR-09 | As a user exploring ideas, I want relevant candidates. | P1 | Semantic results are labelled as a shortlist; shortlist size is never shown as a total. |
| FR-10 | As a user, I want to see product evidence. | P0 | Title plus available price, category, description and stock shown for product results. |
| FR-13 | As a user, I want recent conversation kept. | P1 | Recent Q&A history persists within a session. |

### Epic D: Trust and safety

| ID | User story | Pri | Acceptance criteria |
| --- | --- | --- | --- |
| FR-11 | As a user, I want results confined to my catalogue. | P0 | Every record, attribute and vector lookup scoped by catalogue ID; cross-catalogue test suite passes 100%. |
| FR-12 | As a user, I want clear errors. | P0 | Transient model/API failures retried within a bounded policy; failures shown in plain language. |
| FR-15 (new) | As a user, I want to know what kind of answer I got. | P0 | Every answer carries a visible label: **Exact**, **Hybrid-verified** or **Candidates**. |
| FR-16 (new) | As a user, I want honest refusals. | P0 | Unsupported questions return a clear "cannot answer exactly" message with a suggested rephrasing. |

## 8. Experience and key flows

### 8.1 Primary flow

1. Upload a catalogue file.
2. Review and confirm proposed column mappings.
3. Register the catalogue; attribute enrichment runs.
4. Select the catalogue and ask a question.
5. Router chooses structured, hybrid or semantic retrieval.
6. Answer appears with an answer-type label and product evidence cards.

### 8.2 Answer-type labels (key UX decision)

| Label | Meaning | Example |
| --- | --- | --- |
| **Exact** | Computed by the database over the complete matching set | "25 products have inventory greater than 30" |
| **Hybrid-verified** | Filters verified the match set; retrieval used for ranking or evidence | "5 cotton products have inventory greater than 30" |
| **Candidates** | Ranked by similarity; not a verified total | "Top 5 products that feel suited to everyday wear" |

### 8.3 Failure states to design for

- Mapping is ambiguous: ask the user to confirm instead of guessing.
- Question outside supported types: say so and offer the nearest supported question.
- Model or API failure after retries: show a readable error and keep the conversation intact.
- Zero results: distinguish "no matches" from "could not evaluate".

## 9. AI product requirements

### 9.1 Query routing

| Question type | Path | Guarantee |
| --- | --- | --- |
| Counts, sums, averages, missing values, numeric filters | Structured (DuckDB) | Exact |
| Attribute or text condition with optional filters | Hybrid | Exact when filter semantics cover the full record set |
| Descriptive or conceptual discovery | Semantic (embeddings + FAISS) | Candidates only |

### 9.2 Known failure modes

| Failure mode | User impact | Mitigation |
| --- | --- | --- |
| Title-only interpretation | Understated counts | Cross-field scope; regression tests with attributes that exist only in descriptions or metadata |
| Semantic false positive | Relevant-looking but wrong product | Candidate label; verify with deterministic filter before counting |
| Attribute hallucination | Misleading attribute shown | Evidence validation; audit sample; user correction (Phase 2) |
| Wrong catalogue results | Data leakage | Catalogue ID scoping; isolation test suite |
| Router mis-classification | Exact question treated as semantic | Router evaluation set; fall back to refusal rather than guess |

### 9.3 Evaluation plan

- **Golden set:** at least 100 labelled questions across 3 catalogues, covering count, filter, hybrid, semantic and unsupported types.
- **Method:** exact answers verified independently in DuckDB; Precision@5 judged by two reviewers on semantic queries.
- **Regression:** the cotton 2 vs 8 case and the isolation cases run on every change.
- **Honesty about limits:** current results come from one 40-product catalogue and are not an audited benchmark.

## 10. Data requirements

| Field | Logical type | Notes |
| --- | --- | --- |
| `product_title` | Text | Shown to users |
| `product_description` | Text | Descriptive information |
| `selling_price` | Numeric | Validated before aggregation |
| `cost_price` | Numeric | Validated before aggregation |
| `inventory_quantity` | Numeric | Missing is not zero |
| `source_record_json` | JSON | Preserves unmapped source fields |

Extracted attribute records keep canonical name, source name, value, evidence, extraction model and timestamp. All records and attributes carry `catalogue_id` and `source_record_id`.

**Data quality rules:** missing is distinguishable from zero; numbers validated before use; extracted values must be supported by evidence; originals remain available for traceability.

## 11. Success metrics

### 11.1 North Star

**Verified Answer Rate** = questions answered with an Exact or Hybrid-verified result that the user accepts / questions asked. \[Target: baseline first, then improve.\]

### 11.2 Metric tree

| Layer | Metric | Formula | Target |
| --- | --- | --- | --- |
| Quality (input) | Exact count accuracy | Correct exact counts / labelled count questions | ≥ 95% |
| Quality (input) | Filter precision | Relevant returned / all returned | ≥ 95% |
| Quality (input) | Retrieval Precision@5 | Relevant in top 5 / 5 | ≥ 80% |
| Quality (input) | Attribute evidence validity | Valid-evidence attributes / audited | ≥ 98% |
| Reliability | Supported query success rate | Successful / attempted | ≥ 95% |
| Efficiency | Time to answer vs manual | Median minutes for same task in usability study | Establish baseline |
| Efficiency | Cost per successful query | LLM and infra cost / successes | Establish baseline |
| **Guardrail** | Catalogue isolation | Tests passed / executed | 100% (no tolerance) |
| **Guardrail** | Mislabelled answers | Candidate results presented as exact / total | 0 |

All figures in this table are **\[Target\]**, not results.

### 11.3 Instrumentation

Log per query: catalogue ID, question type, route chosen, answer-type label, latency, retries, cost estimate and a thumbs up/down signal. No customer or private merchant data enters the demo dataset.

## 12. Results to date (prototype)

Observed on the curated 40-product multi-category dataset **\[Observed\]**:

| Check | Result |
| --- | --- |
| Products with at least one extracted attribute | 40 / 40 |
| Attribute records stored | 315 |
| "How many products contain cotton?" (after cross-field fix) | 8 (was 2 with title-only) |
| "How many products have inventory greater than 30?" | 25 |
| "How many cotton products have inventory greater than 30?" | 5 |
| "How many products contain recycled polyester?" | 1 (FlexFit Sports Bra) |
| "How many fragrance-free products are there?" | 3 |
| Isolation test: 200-product dev catalogue vs 40-product catalogue | Counts 200 and 40; FlexFit Sports Bra returned 1 record in the 40-product catalogue and 0 in the 200-product one |

**Limitations.** Small, curated, single-category-mix dataset; not independently audited; not evidence of production accuracy.

## 13. Assumptions, risks and dependencies

### 13.1 Assumptions to validate

| Assumption | Validation method | Pass signal |
| --- | --- | --- |
| Catalogue teams regularly ask multi-field questions they cannot answer quickly | 5 to 8 interviews with catalogue, category or ops practitioners | Most describe a recent painful instance |
| Users value answer-type labels | Moderated usability test with 5 users | Majority can explain the difference and prefer labelled answers |
| Cross-field search materially improves recall on other catalogues | Run the cotton-style audit on 2 more catalogues | Recall gain on attributes absent from titles |
| Extraction quality holds beyond the demo catalogue | Evidence audit on 100 attributes from a new catalogue | ≥ 98% valid evidence |

### 13.2 Risks

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| Model/API availability | Failed answers | Medium | Bounded retries, clear errors, deterministic path first |
| Semantic false positives | Misleading shortlist | Medium | Candidate label; verified counting only |
| Attribute extraction error | Wrong evidence | Medium | Evidence validation; audit sample |
| Catalogue leakage | Trust loss | Low, high impact | ID scoping; isolation suite on every change |
| Prototype data does not generalise | Overstated claims | High | Expand evaluation; keep claims tagged as observed on one catalogue |
| Ephemeral hosting loses uploads | Lost work | Medium | Defer public deployment; define persistence before launch |

### 13.3 Constraints and dependencies

₹0 hosting budget; LLM and embedding API availability and terms; API keys held only in environment secrets; repository stays private.

## 14. Roadmap and exit criteria

| Phase | Focus | Exit criteria |
| --- | --- | --- |
| **Now: Portfolio MVP** | Upload and mapping, attribute evidence, three query paths, three-panel dashboard, isolation | Acceptance checklist (section 17) fully met |
| **Next: Validated prototype** | 3 labelled catalogues, 100-question golden set, answer-type labels, 5 to 8 interviews, usability test | Quality targets in 11.2 measured; assumptions in 13.1 resolved |
| **Later: Controlled demo** | Low-cost host, secrets management, persistence policy, resource limits, budget safeguards | Full evaluation suite passes before any live URL is shared |
| **Later: Production (not planned)** | Authentication, tenant isolation guarantees, monitoring, audit logs, backups, security and scale tests | Separate business case required |

## 15. Decision log

| Decision | Options considered | Choice and rationale |
| --- | --- | --- |
| Keep exact calculation out of the LLM | LLM-computed vs database-computed | Database-computed; LLM numbers cannot be trusted for reporting |
| Search scope for general queries | Title-only vs cross-field | Cross-field; title-only understated cotton 4x |
| Separate candidates from verified counts | Show similarity-ranked list as a total vs label it | Label it; protects the trust principle |
| Public deployment | Deploy now vs defer | Defer until persistence, secrets and evaluation are in place |
| Primary persona | All three vs one | Catalogue / Content Manager; strongest dependence on cross-field evidence |

## 16. Open questions

| Question | Owner | Needed by |
| --- | --- | --- |
| Which categories and catalogue sizes go in the next evaluation set? | Product | Start of Next phase |
| Acceptable latency for exact queries versus semantic discovery? | Product + user testing | After usability sessions |
| Should filtered result sets be exportable? | Product | Phase 2 planning |
| Which extraction errors need user correction versus automatic retry? | Product + engineering | After evidence audit |
| What persistence and retention model fits uploaded catalogues? | Product + engineering | Before controlled demo |
| Which hosting approach meets a strict ₹0 budget without hurting privacy or reliability? | Product | Before controlled demo |

## 17. Acceptance checklist for the portfolio MVP

- [ ] Five canonical fields explained and demonstrated.
- [ ] Upload and mapping workflow shown with a safe demo dataset.
- [ ] Attribute enrichment retains evidence.
- [ ] Exact count queries independently checked against DuckDB.
- [ ] Hybrid and semantic results labelled Exact, Hybrid-verified or Candidates.
- [ ] Multi-catalogue isolation has representative passing tests.
- [ ] README includes product walkthrough, architecture, measured evaluation and limitations.
- [ ] Repository contains no secrets or unapproved private data.

## Appendix: Glossary

**Canonical fields:** the five normalised product dimensions. **Structured path:** deterministic SQL execution. **Hybrid path:** explicit filters combined with retrieval. **Semantic path:** embedding similarity search via FAISS. **Candidates:** similarity-ranked results not verified as an exact match set.
