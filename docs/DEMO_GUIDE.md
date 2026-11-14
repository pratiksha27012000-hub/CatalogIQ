# CatalogIQ — Demo Walkthrough Guide

## Intended audience

Recruiters, Product Managers, AI Product Managers, e-commerce leaders and technical reviewers.

## Suggested Loom walkthrough (4–6 minutes)

### 1. The problem (30–45 seconds)

Explain that product information is distributed across titles, descriptions, source metadata and extracted attributes. Teams often resort to manual spreadsheet filtering to answer questions.

### 2. The product experience (60–90 seconds)

Show the original three-panel dashboard:
- Left: upload and map a catalogue.
- Centre: five canonical data dimensions and catalogue completeness.
- Right: ask the AI assistant questions.

### 3. Demonstrate exact and attribute questions (60–90 seconds)

Use the curated 40-product demo catalogue:
- “How many products are in the catalogue?” → 40.
- “How many products contain cotton?” → 8.
- “How many products have inventory greater than 30?” → 25.

Explain that exact counts are executed against DuckDB.

### 4. Demonstrate hybrid product discovery (45–60 seconds)

Ask: “Find products containing recycled polyester.”

Expected observed result: FlexFit Sports Bra, Apparel, ₹1,199.

Explain that hybrid retrieval combines product evidence with explicit conditions.

### 5. Explain a product decision (45–60 seconds)

Describe the cotton-count bug: title-only search returned two; full source evidence showed eight. The fix introduced a virtual cross-field search scope without changing the five canonical fields.

### 6. Close with evaluation and roadmap (30–45 seconds)

Mention 40/40 products enriched, 315 extracted attribute records, representative isolation tests and known evaluation gaps. Make clear that the prototype is not yet a production deployment.

## Screenshot checklist

- [ ] Full three-panel dashboard, no API keys or private catalogue information visible.
- [ ] Catalogue upload and mapping view using demo data.
- [ ] Five canonical dimension cards.
- [ ] Assistant response for cotton count (8).
- [ ] Assistant product card for recycled polyester (FlexFit Sports Bra).
- [ ] GitHub case-study repository overview.

## Loom publishing checklist

- [ ] Use synthetic/demo data only.
- [ ] Hide browser tabs or account details if not relevant.
- [ ] Do not expose `.env`, API keys, secret settings or local private files.
- [ ] Set Loom sharing to the intended audience (for example, anyone with the link) only after reviewing the recording.
- [ ] Add the Loom URL to the root README and replace the placeholder.
