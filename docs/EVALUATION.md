# CatalogIQ — Evaluation Plan and Test Evidence

## 1. Test environment

- Dataset under evaluation: curated multi-category catalogue.
- Product records: 40.
- Successfully enriched products: 40.
- Extracted attribute records: 315.
- Retrieval: DuckDB structured execution, hybrid retrieval and FAISS semantic search.
- Interface: original three-panel Gradio dashboard.

The test catalogue contains products from multiple categories (including apparel, beauty, electronics and home). Test results below are observations from the prototype session, not an independent third-party benchmark.

## 2. Functional test cases

| ID | User question / action | Expected outcome | Observed outcome | Status |
|---|---|---|---|---|
| TC-01 | How many products are in the catalogue? | Exact count of 40. | 40 returned using structured retrieval. | Pass |
| TC-02 | Find all fragrance-free products. | Return source-supported fragrance-free products. | Three products returned: Daily Dew Hydrating Face Moisturizer, ClearBalance Gentle Cleanser and CalmNight Body Lotion. | Pass in prototype |
| TC-03 | Find products containing recycled polyester. | Find product whose evidence includes recycled polyester. | FlexFit Sports Bra returned; one matching product. | Pass |
| TC-04 | Find products priced below 700 with inventory more than 30. | Apply both numeric conditions. | 13 matching records reported; five displayed in the retrieval shortlist. | Pass for observed filter execution; complete list not displayed |
| TC-05 | Which products have removable pads? | Find products with supporting feature evidence. | FlexFit Sports Bra returned. | Pass |
| TC-06 | Find waterproof products. | Return only products with explicit supporting evidence. | No matching catalogue records returned. | Observed; absence not independently audited |
| TC-07 | Find products with adjustable features. | Retrieve products with adjustable-feature evidence. | Five products retrieved across electronics, home and apparel. | Pass for retrieval; total completeness not independently audited |
| TC-08 | How many products contain cotton? | Exact cross-field count, including descriptions/source metadata. | Initially title-only interpretation returned 2; after cross-field fix the final app returned 8. | Pass after fix |
| TC-09 | How many products have inventory greater than 30? | Exact numeric count. | 25 returned. | Pass |
| TC-10 | How many cotton products have inventory greater than 30? | Apply text and inventory conditions together. | 5 returned. | Pass |
| TC-11 | How many products contain recycled polyester? | Exact count. | One matching product returned by hybrid/direct attribute path. | Pass in prototype |
| TC-12 | Dashboard query: How many products contain cotton? | Show answer in chat. | Assistant displayed 8. Count query did not produce product cards, as expected for an aggregate response. | Pass |
| TC-13 | Dashboard query: Find products containing recycled polyester. | Show assistant answer and product card. | FlexFit Sports Bra card displayed with price and inventory details. | Pass |

## 3. Data-enrichment validation

| Measure | Observed result |
|---|---:|
| Products in curated catalogue | 40 |
| Products with at least one extracted attribute | 40 |
| Extracted attribute records | 315 |
| Product-level enrichment coverage | 100% |

**Coverage definition:** 100% means each of the 40 products has at least one extracted attribute. It does not mean every possible attribute for every product was captured.

## 4. Cross-field cotton investigation

This was a key product-quality defect discovered during testing.

- Initial interpretation mapped “contains cotton” to `product_title` only.
- That title-only query returned 2.
- A source-level catalogue audit found 8 products with cotton evidence in title, description or source metadata.
- Seven distinct products had a cotton-related extracted attribute in the attribute table; the eighth was still discoverable from source text.
- A virtual `product_text` search field was introduced to cover title, description, original metadata and extracted attributes.
- The direct executor returned 8, the interpreter was updated to select `product_text` for general product searches, and the complete CatalogIQ application returned 8.

This test demonstrates why attribute extraction should complement—not replace—the original source evidence.

## 5. Multi-catalogue isolation tests

| Test | Catalogue | Expected | Observed | Status |
|---|---|---:|---:|---|
| ISO-01 | Curated multi-category catalogue | 40 products | 40 | Pass |
| ISO-02 | Separate development catalogue | 200 products | 200 | Pass |
| ISO-03 | Search FlexFit Sports Bra in 40-product catalogue | 1 | 1 | Pass |
| ISO-04 | Search FlexFit Sports Bra in 200-product catalogue | 0 | 0 | Pass |

These tests provide evidence that the tested application paths respect the selected catalogue ID. A broader isolation suite is still required before production use.

## 6. Reliability observation

During the regression suite, a Gemini 503 transient error occurred. The retry mechanism waited two seconds, retried the request and the query completed successfully with the expected answer of 8.

The prototype uses bounded retries for transient failures. Persistent provider outage, quota exhaustion and other error classes still need dedicated tests.

## 7. Known test gaps

1. Build a labelled test set across more catalogues, categories and attribute types.
2. Independently verify complete matching sets for all hybrid queries.
3. Measure Precision@5, Recall@5 and nDCG for semantic discovery.
4. Test missing/null data, duplicate products and malformed uploads.
5. Test source metadata with nested structures and unusual encodings.
6. Test catalogue isolation under concurrent requests and adversarial catalogue IDs.
7. Test Gemini rate limits, prolonged outage, malformed JSON and authentication failures.
8. Measure latency, RAM and embedding-index build time on larger catalogues.
9. Test upload persistence, restart recovery and backup/restore.

## 8. Proposed evaluation metrics and initial targets

| Metric | Definition | Proposed target |
|---|---|---:|
| Exact count accuracy | Correct counts / labelled count tests | ≥95% |
| Filter precision | Relevant returned records / all returned records | ≥95% |
| Retrieval Precision@5 | Relevant results among top five / five | ≥80% |
| Attribute evidence validity | Valid evidence / audited extracted attributes | ≥98% |
| Catalogue isolation | Passed isolation checks / executed checks | 100% |
| Supported-query success rate | Successful supported questions / attempted supported questions | ≥95% |

Targets are proposed; they have not yet been achieved or measured over a statistically meaningful test set.
