# CatalogIQ — Product and Architecture Decision Log

This document records important decisions made while shaping the prototype. Dates refer to the November 2026 development work.

## D-01 — Use five canonical catalogue fields

**Decision:** Normalize every catalogue to five stable fields: `product_title`, `product_description`, `selling_price`, `cost_price` and `inventory_quantity`.

**Rationale:** These fields provide a consistent base for product discovery and commercial analysis across categories.

**Trade-off:** Category-specific information cannot be represented entirely in the canonical schema.

**Follow-through:** Preserve source-specific metadata and store extracted attributes separately rather than expanding the canonical schema for every category.

## D-02 — Preserve original source metadata

**Decision:** Retain source information separately (for example, in `source_record_json`).

**Rationale:** A mapped canonical record may omit tags, variant details, material fields or other source-specific information needed for discovery.

**Trade-off:** Search and query logic must handle a more heterogeneous source payload.

## D-03 — Extract dynamic attributes with evidence

**Decision:** Use an LLM-assisted extraction pipeline to discover product-specific attributes and retain supporting evidence.

**Rationale:** A fixed attribute vocabulary would make the product brittle across apparel, beauty, electronics, home and future categories.

**Trade-off:** Model output requires validation, retry/error handling and evaluation; extraction coverage does not imply every possible attribute is captured.

## D-04 — Use DuckDB for deterministic calculations

**Decision:** Route supported counts, numeric comparisons and aggregations to DuckDB.

**Rationale:** Exact calculations should use the catalogue source of truth, not LLM estimates.

**Trade-off:** Natural-language interpretation must map questions to validated operations; an incorrect interpretation can still create an incorrect query.

## D-05 — Add a virtual cross-field search scope

**Decision:** Use a virtual `product_text` field for general product/attribute text search.

**Rationale:** A cotton query mapped to `product_title` returned two records, while source-level inspection found eight products with cotton evidence across the catalogue. Search therefore needed to cover title, description, original metadata and extracted attributes.

**Trade-off:** Broader search can return products with partial or blended mentions. Results need evidence display and appropriate matching semantics.

**Important:** `product_text` is a query abstraction, not a sixth persisted canonical column.

## D-06 — Use hybrid and semantic retrieval for discovery

**Decision:** Retain structured, hybrid and semantic retrieval paths.

**Rationale:** Exact filters, evidence-backed attribute conditions and conceptual discovery are different query types and should not be forced into one retrieval strategy.

**Trade-off:** The application must clearly distinguish verified matches from relevance-ranked candidates and must not label a semantic shortlist as an exact count.

## D-07 — Enforce catalogue-scoped retrieval

**Decision:** Every record, attribute and vector retrieval operation receives a catalogue ID; semantic indexes are maintained per catalogue.

**Rationale:** One user's selected catalogue should not return records from another catalogue.

**Evidence:** Tested 40-product and 200-product catalogues returned their own counts; FlexFit Sports Bra was found only in the 40-product catalogue.

## D-08 — CPU-first prototype

**Decision:** Use CPU-based FAISS and CPU PyTorch for the current prototype.

**Rationale:** The current 40-product demo does not require dedicated GPU hosting. A paid GPU deployment would add cost without a demonstrated product need.

**Trade-off:** Larger catalogues and higher concurrency may require performance optimization or a different compute profile.

## D-09 — Keep the implementation private; publish the case study separately

**Decision:** Keep executable source code and development data in a private repository. Publish a documentation-only case-study repository if public portfolio visibility is desired.

**Rationale:** The goal is to showcase product thinking, system design and test evidence without offering the implementation for public use.

**Trade-off:** A documentation-only public repository still exposes the published narrative and assets; screenshots and video must be reviewed for sensitive information.
