# CatalogIQ: System Architecture and Technical Decisions

*Version 2.0 · Owner: Pratiksha (Product) · Last updated 15 Nov 2026 · Companion to PRD v2.0*

> **Evidence tags.** **\[As built\]** describes the current prototype. **\[Observed\]** was measured in testing. **\[Planned\]** is a committed next step. **\[Hypothesis\]** is believed but untested. Nothing here is a production claim.

## 1. Purpose and how to read this document

This document explains *why* CatalogIQ is built the way it is. Each major design choice is tied back to a product guarantee in the PRD, so a reader can see which component protects which promise to the user.

**The one-line architecture thesis:** *the database computes numbers, the LLM interprets and explains, and the interface always says which one produced the answer.*

## 2. Architecture at a glance

### 2.1 Design goals (mapped to PRD principles)

| Product principle (PRD) | Architectural consequence |
| --- | --- |
| Trust over fluency | Exact numbers come only from deterministic DuckDB execution; the LLM never calculates a count |
| Show your evidence | Every product and attribute row keeps a link to its source record and supporting evidence |
| Say what kind of answer it is | Retrieval mode (structured, hybrid, semantic) is carried through to the response so it can be labelled |
| Catalogues are walls | `catalogue_id` is required on every query and every vector lookup; one FAISS index per catalogue |
| ₹0 budget | CPU-only FAISS and PyTorch; no GPU, no fine-tuning |

### 2.2 Key decisions in brief

| Decision | Choice | Main trade-off |
| --- | --- | --- |
| Source of truth for numbers | DuckDB | Requires reliable question interpretation before SQL can run |
| Search scope for general queries | Cross-field virtual `product_text` | Slightly heavier queries; avoids the 2-vs-8 cotton undercount |
| Semantic layer | Sentence Transformer embeddings with FAISS, one index per catalogue | More indexes to build; strong isolation and simple rebuilds |
| Enrichment | Gemini attribute extraction with evidence | API dependency and cost; evidence validation needed |
| Interface | Three-panel Gradio dashboard | Fast to build and demo; not a production front end |

## 3. System diagram

The diagram below shows the five layers and how a question flows from the assistant panel to a grounded answer.

&#91;embedded content: CatalogIQ architecture · 4 layers, 3 retrieval paths\]

Questions flow down from the dashboard and answers flow back up. The structured path reads DuckDB only, the semantic path reads FAISS only, and the hybrid path reads both. Ingestion writes records, attributes and embeddings, never answers.

## 4. Components

| Component | Responsibility | Technology | Protects (PRD) |
| --- | --- | --- | --- |
| Gradio dashboard | Upload, mapping, catalogue selection, dimension overview, chat | Gradio | FR-01, FR-02, FR-14 |
| Ingestion and mapping | Reads CSV, XLSX or JSON, validates rows, maps source columns to canonical fields | Python, pandas | FR-01 to FR-04 |
| Attribute extractor | Finds catalogue-specific attributes with supporting evidence | Gemini | FR-05 |
| DuckDB store | Catalogue registry, canonical records, attribute records | DuckDB | FR-03, FR-06, FR-11 |
| Embedding and index manager | Builds and queries one FAISS index per catalogue | Sentence Transformers, FAISS (CPU) | FR-09, FR-11 |
| Query router | Chooses structured, hybrid or semantic mode | Application logic | FR-06 to FR-09 |
| Query interpreter | Turns a question into a structured query specification | Gemini | FR-06, FR-08 |
| Structured executor | Validates and runs deterministic SQL | DuckDB | FR-06 |
| Hybrid retriever | Applies explicit filters together with retrieval | DuckDB plus FAISS | FR-07, FR-08 |
| Semantic retriever | Returns relevance-ranked candidates | FAISS | FR-09 |
| Grounded answer generator | Writes the reply strictly from retrieved evidence | Gemini | FR-10 |

## 5. The trust model

This is the part of the architecture that matters most to the product. Each answer type has a different guarantee, and a different component is responsible for the number.

| Answer type | Who produces the numbers | Guarantee | Shown to user as |
| --- | --- | --- | --- |
| **Exact** | DuckDB over the complete matching set | The count is correct for the interpreted question | Exact |
| **Hybrid-verified** | Filters verified in DuckDB; retrieval used for ranking and evidence | Exact when filter semantics cover the full record set | Hybrid-verified |
| **Candidates** | FAISS similarity ranking | Relevant-looking, not proven to match | Candidates |

**Rules enforced by design**

1. A candidate count is never exposed as a catalogue-wide total unless a separate deterministic check supports it. \[As built\]
2. The answer generator receives retrieved evidence only and is not asked to compute figures. \[As built\]
3. The response carries an explicit `answer_type` field (Exact, Hybrid-verified, Candidates) so the interface can label it. \[Planned, supports FR-15\]
4. A question the system cannot interpret safely returns a clear refusal, not a best guess. \[Planned, supports FR-16\]

**Response contract today \[As built\]:** status, records, matching record count, displayed record count, retrieval mode, answer text and errors. **Planned additions:** `answer_type`, `verified` flag and the interpreted query specification, so the user and the evaluation suite can see what the system understood.

## 6. Query lifecycle

| Step | What happens | What can go wrong | Fallback |
| --- | --- | --- | --- |
| 1. Receive | Question and selected `catalogue_id` arrive | Empty question or no catalogue selected | Prompt the user; never default to another catalogue |
| 2. Route | Pick structured, hybrid or semantic mode | Wrong mode chosen | Router evaluation set; refuse when unsure \[Planned\] |
| 3. Interpret | Convert the question into a query specification | API failure, malformed or empty response | Bounded retries, then a readable error |
| 4. Validate | Check intent, fields, operators and filters | Unsupported field or operator | Reject with a suggested rephrasing |
| 5. Execute | Run SQL in DuckDB and/or search the catalogue's FAISS index | Slow query, empty result | Distinguish "no matches" from "could not evaluate" |
| 6. Verify | Apply post-retrieval conditions; separate verified matches from candidates | Candidate wrongly treated as verified | Candidate label; verified counting only through DuckDB |
| 7. Generate | Write an answer from retrieved evidence | Unsupported claim in the text | Ground strictly in retrieved rows |
| 8. Return | Answer, counts where supported, display count and product evidence | Mismatch between text and cards | Counts come from the executor, not the text |

## 7. Data model

### 7.1 Persisted structures \[As built\]

| Structure | Contents |
| --- | --- |
| Catalogue registry | Catalogue ID, name and status |
| Canonical product record | `product_title`, `product_description`, `selling_price`, `cost_price`, `inventory_quantity`, plus `source_record_json` for original source fields |
| Attribute record | Source record association, canonical and source attribute names, value, evidence, extraction model, timestamp where available |

All rows carry a `catalogue_id` and a source record association.

### 7.2 The virtual search scope

`product_text` is a *virtual* scope, not a sixth stored column. It searches title, description, source metadata and extracted attribute information. This is why a general search for "cotton" now finds products whose title never mentions it. \[Observed: 2 title-only results versus 8 cross-field results\]

### 7.3 Data quality rules

Missing values stay distinct from zero. Numbers are validated before aggregation. Extracted values must be supported by source evidence. Original source data stays available for audit.

## 8. Technology choices and trade-offs

The rationale below is my reading of the design and should be confirmed against the original decision notes.

| Choice | Why it fits | Alternatives considered | Cost of the choice |
| --- | --- | --- | --- |
| **DuckDB** | Embedded, fast analytical SQL, no server to run on a ₹0 budget | A hosted SQL database; spreadsheet-style filtering in memory | Needs a persistence plan before any shared deployment |
| **One FAISS index per catalogue** | Isolation by construction; simple rebuild and delete | One shared index with catalogue metadata filtering | More indexes to manage as catalogues grow |
| **Sentence Transformers on CPU** | Free, local, no per-call cost | Hosted embedding API; larger GPU-based models | Slower indexing on large catalogues |
| **Gemini for extraction and interpretation** | Strong language understanding without training | Rule-based parsing; fine-tuned small model | API dependency, latency, cost and availability risk |
| **Gradio** | Quick to build a three-panel demo | A custom web front end | Limited control over layout and session handling |

## 9. Catalogue isolation

**Design \[As built\].** Every product and attribute row links to a catalogue ID. Query execution and vector lookup both receive the selected ID. Each catalogue has its own FAISS index.

**Evidence \[Observed\].** The 40-product catalogue returned a count of 40 and the separate 200-product catalogue returned 200. FlexFit Sports Bra returned one record in the 40-product catalogue and zero in the 200-product one.

**Honest limit.** This is representative test evidence, not a security certification. Before any shared deployment, isolation needs an automated suite that runs on every change and covers structured, hybrid and semantic paths separately. \[Planned\]

## 10. Reliability, limitations and technical debt

### 10.1 Resilience \[As built\]

- Gemini calls use bounded retries for transient API errors and retryable malformed or empty responses.
- Counts and filters run in DuckDB, not in the LLM.
- Semantic similarity is never treated as proof of an exact match.

### 10.2 The most important limitation

**Deterministic queries still depend on LLM interpretation.** The numbers are exact, but the question is first interpreted by a model. If the API is down or the interpretation is wrong, an "exact" query can fail or answer a slightly different question.

| Aspect | Detail |
| --- | --- |
| Product impact | Reliability and the Verified Answer Rate depend on API availability; a wrong interpretation gives a correct number for the wrong question |
| Mitigation today | Bounded retries; validation of fields and operators before execution |
| Planned fix | A deterministic parser for common patterns (counts, numeric thresholds, missing values), with the LLM only as fallback |
| Why it matters for the roadmap | It would raise reliability, cut cost per query and reduce latency for the most common question types |

### 10.3 Technical debt register

| Item | Impact | Priority |
| --- | --- | --- |
| Deterministic parser for common query patterns | Reliability, cost, latency | High |
| `answer_type` and `verified` fields in the response contract | Enables trust labels (FR-15) | High |
| Automated isolation and regression suite (including the cotton 2-vs-8 case) | Protects the core guarantees | High |
| Persistent storage and backup policy | Required before any non-demo catalogue | Medium |
| Router evaluation set | Measures mode-selection accuracy | Medium |
| Interpreted-query display in the UI | Lets users spot misinterpretation | Medium |

## 11. Non-functional characteristics

| Area | Current position | Target or plan |
| --- | --- | --- |
| Accuracy | Exact calculations in DuckDB \[As built\] | Exact count accuracy of at least 95% on the golden set \[Target\] |
| Isolation | Per-catalogue IDs and indexes; representative tests passed \[Observed\] | 100% on an automated suite \[Target\] |
| Performance | Responsive on the 40-product demo catalogue \[Observed, informal\] | Baseline latency per mode before setting targets |
| Cost | CPU only; Gemini API calls are the main variable cost \[As built\] | Measure cost per successful query first, then set a target |
| Security | Credentials via environment variables or secrets \[As built\] | Secret management and access controls before any shared URL \[Planned\] |
| Privacy | Demo uses a curated dataset without customer data \[As built\] | Retention and deletion policy before non-demo data \[Planned\] |
| Maintainability | Routing, retrieval, execution and answer generation are separate components \[As built\] | Keep component contracts stable as the response schema grows |

## 12. Scalability outlook

Nothing below has been tested beyond 200 products.

| Dimension | What is likely to change as catalogues grow | Status |
| --- | --- | --- |
| Embedding build time | Grows with product count; may need batching and background builds on CPU | \[Hypothesis\] |
| FAISS index type | A simple exact index is fine for small catalogues; larger ones may need an approximate index | \[Hypothesis\] |
| Attribute extraction cost | Scales with products and API pricing; needs batching and caching | \[Hypothesis\] |
| DuckDB analytical queries | Expected to stay responsive on moderate data | \[Hypothesis\] |
| Index count | One index per catalogue multiplies storage and rebuild work | \[Hypothesis\] |

The next evaluation phase should measure build time, query latency and extraction cost at several catalogue sizes before any scaling claim is made.

## 13. Observability and evaluation hooks

The PRD defines the metrics; the architecture must be able to produce them. Per query, the system should log the catalogue ID, route chosen, interpreted query specification, answer type, latency, retry count, estimated cost and user feedback. \[Planned\] These records feed the Verified Answer Rate, the router evaluation and the cost-per-query baseline.

## 14. Deployment and operations

- The prototype runs on CPU; no dedicated GPU is required. \[As built\]
- Embeddings and FAISS indexes are rebuildable runtime artifacts in the current workflow. \[As built\]
- A shared deployment needs explicit persistence, backup and retention before accepting non-demo catalogues. \[Planned\]
- Public deployment stays out of scope until the isolation suite, secrets handling and the evaluation set are in place.

## 15. Requirement traceability

| PRD requirement | Primary component |
| --- | --- |
| FR-01 to FR-04 Upload, mapping, normalisation, source retention | Ingestion and mapping, DuckDB |
| FR-05 Evidence-backed attributes | Attribute extractor, DuckDB |
| FR-06 Exact counts and numeric filters | Query interpreter, structured executor, DuckDB |
| FR-07 Cross-field search | Virtual `product_text` scope |
| FR-08 Hybrid retrieval | Hybrid retriever |
| FR-09 Semantic discovery | Semantic retriever, FAISS |
| FR-10 Product evidence | Answer generator, response records |
| FR-11 Catalogue isolation | Catalogue ID scoping, per-catalogue indexes |
| FR-12 Error handling | Bounded retry logic, UI error states |
| FR-15 Answer-type label | `answer_type` response field \[Planned\] |
| FR-16 Honest refusals | Validation step and router fallback \[Planned\] |

## 16. Open technical questions

| Question | Needed by |
| --- | --- |
| Which common query patterns should the deterministic parser cover first? | Start of the next phase |
| What is the acceptable latency for exact queries versus semantic discovery? | After usability sessions |
| Should the interpreted query be shown to users by default? | Phase 2 planning |
| What persistence and retention model fits uploaded catalogues? | Before a controlled demo |
| How should attribute corrections by users be stored and re-indexed? | Phase 2 planning |
