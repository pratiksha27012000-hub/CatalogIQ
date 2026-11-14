---
title: CatalogIQ
emoji: 🛍️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.31.0
python_version: 3.13
app_file: app.py
pinned: false
---

# CatalogIQ — E-commerce Product Intelligence Copilot

CatalogIQ lets users upload product catalogues and ask natural-language
questions about product information, pricing, inventory and extracted
product attributes.

## Demo dataset

This public demo starts with one multi-category test catalogue:
- 40 products
- 315 extracted product attributes
- Five canonical catalogue dimensions:
  product title, description, selling price, cost price and inventory.

## Features

- Catalogue upload and column mapping
- Dynamic product attribute enrichment
- Structured DuckDB queries
- Hybrid and semantic retrieval
- Catalogue-level product insights
- Three-panel Gradio interface

## Configuration

Add the following secret in Space Settings > Secrets:

`GEMINI_API_KEY`

Do not commit API keys or credentials to the repository.

## Notes

The included database is a curated demo database containing only the
40-product test catalogue.

The default Space filesystem is ephemeral. Additional catalogues uploaded
while the Space is running may not survive a restart unless persistent
storage is configured.
