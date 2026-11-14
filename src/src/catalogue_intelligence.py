"""Deterministic catalogue lookups used by the CatalogIQ engine.

The module deliberately keeps the five canonical product fields unchanged.
Category and source attributes are read from source_record_json and the
catalogue's extracted-attribute view when those are available.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import pandas as pd


PRODUCT_GROUPS = {
    "earbuds": {
        "terms": [
            "earbud", "earbuds", "ear bud", "ear buds",
            "earphone", "earphones", "earpod", "earpods",
            "ear pod", "ear pods", "tws earbuds",
        ],
        "label": "earbuds / earphones",
    }
}

CATEGORY_ALIASES = {
    "beauty": ("beauty", "skincare", "skin care", "cosmetics", "cosmetic", "personal care"),
    "electronics": ("electronics", "electronic"),
    "home": ("home", "home decor", "homeware", "household"),
    "apparel": ("apparel", "clothing", "clothes", "fashion", "garments", "wear"),
}

STOP_ATTRIBUTE_TERMS = {
    "product", "products", "find", "show", "list", "display", "all",
    "the", "me", "some", "with", "having", "that", "are", "is",
}


def normalize_text(value: Any) -> str:
    """Normalize text for safe, case-insensitive phrase matching."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).casefold().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_source_record(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _normalized_key_map(mapping: dict) -> dict:
    return {
        re.sub(r"[^a-z0-9]", "", str(key).casefold()): value
        for key, value in mapping.items()
    }


def category_from_row(row: Any) -> Optional[str]:
    """Get category from a result column or preserved source metadata."""
    for key in (
        "_catalogue_category", "category", "product_type", "Product Type",
        "product_category", "Product Category",
    ):
        try:
            value = row.get(key)
        except AttributeError:
            value = None
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value).strip()

    metadata = parse_source_record(row.get("source_record_json"))
    keys = _normalized_key_map(metadata)
    for key in ("producttype", "productcategory", "category", "categoryname", "type"):
        value = keys.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def add_category_column(records: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if records is None or not isinstance(records, pd.DataFrame):
        return records
    out = records.copy()
    if "_catalogue_category" not in out.columns:
        out["_catalogue_category"] = out.apply(category_from_row, axis=1)
    else:
        missing = out["_catalogue_category"].isna() | out["_catalogue_category"].astype(str).str.strip().eq("")
        if missing.any():
            out.loc[missing, "_catalogue_category"] = out.loc[missing].apply(category_from_row, axis=1)
    return out


def result_records(records: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    """Convert records into JSON-friendly output while retaining category."""
    if records is None or records.empty:
        return []
    frame = add_category_column(records)
    if limit is not None:
        frame = frame.head(limit)
    fields = (
        "source_record_id", "product_title", "product_description",
        "selling_price", "cost_price", "inventory_quantity",
    )
    output = []
    for _, row in frame.iterrows():
        item = {}
        for field in fields:
            if field not in frame.columns:
                continue
            value = row[field]
            if pd.isna(value):
                value = None
            elif hasattr(value, "item"):
                try:
                    value = value.item()
                except Exception:
                    pass
            item[field] = value
        category = row.get("_catalogue_category")
        if category is not None and not pd.isna(category) and str(category).strip():
            item["category"] = str(category).strip()
        output.append(item)
    return output


def fetch_catalogue(con: Any, catalogue_id: str) -> pd.DataFrame:
    return con.execute(
        "SELECT * FROM catalogue_records WHERE catalogue_id = ?",
        [catalogue_id],
    ).df()


def _product_group(question: str):
    q = normalize_text(question)
    for group_key, config in PRODUCT_GROUPS.items():
        if any(normalize_text(term) in q for term in config["terms"]):
            return group_key, config
    return None, None


def _product_rows(records: pd.DataFrame, config: dict) -> pd.DataFrame:
    terms = [normalize_text(term) for term in config.get("terms", [])]
    if records.empty:
        return records.copy()

    def matches(row):
        haystack = " ".join((
            normalize_text(row.get("product_title", "")),
            normalize_text(row.get("product_description", "")),
        ))
        return any(term and term in haystack for term in terms)

    return add_category_column(records[records.apply(matches, axis=1)].copy())


def _is_stock_question(question: str) -> bool:
    q = normalize_text(question)
    return bool(re.search(
        r"\b(stock|inventory|quantity|units?|available|availability|kitna|kitne|bacha|remaining)\b",
        q,
    ))


def _is_zero_stock_question(question: str) -> bool:
    q = normalize_text(question)
    if re.search(r"\bnot (?:out of stock|sold out)\b", q):
        return False
    return bool(re.search(
        r"\b(zero stock|zero inventory|out of stock|sold out|no stock|unavailable)\b",
        q,
    ))


def direct_product_answer(con: Any, catalogue_id: str, question: str, top_k: int = 5):
    """Answer recognised product-family counts and stock totals exactly."""
    group_key, config = _product_group(question)
    if group_key is None:
        return None

    q = normalize_text(question)
    query_signal = bool(re.search(
        r"\b(total|count|how many|number|stock|inventory|quantity|units?|kitna|kitne|find|show|list|which|available)\b",
        q,
    ))
    if not query_signal:
        return None

    rows = _product_rows(fetch_catalogue(con, catalogue_id), config)
    count = int(len(rows))

    if _is_zero_stock_question(question):
        if not rows.empty:
            stock = pd.to_numeric(rows["inventory_quantity"], errors="coerce")
            rows = rows[stock == 0].copy()
        rows, _ = filter_by_category(rows, question)
        count = int(len(rows))
        if count == 0:
            answer = "There are no zero-stock earbuds or earphones products in this catalogue."
        else:
            names = ", ".join(rows["product_title"].astype(str).tolist())
            answer = f"There are {count} zero-stock earbuds or earphones products: {names}."
        metric = "count"
        target_field = "inventory_quantity"
        extra = {}

    elif _is_stock_question(question):
        if rows.empty:
            total = 0
            answer = "No matching earbuds or earphones products were found in this catalogue, so there is no stock to report."
        else:
            inventory = pd.to_numeric(rows["inventory_quantity"], errors="coerce")
            if inventory.notna().sum() == 0:
                total = None
                answer = "I found matching products, but their inventory quantities are missing."
            else:
                total = float(inventory.fillna(0).sum())
                total_text = str(int(total)) if total.is_integer() else str(round(total, 2))
                names = ", ".join(rows["product_title"].astype(str).tolist())
                answer = f"Total available stock for {names}: {total_text} units."
        metric = "sum"
        target_field = "inventory_quantity"
        extra = {"inventory_total": total}

    else:
        if count == 0:
            answer = "No matching earbuds or earphones products were found in this catalogue."
        elif count == 1:
            answer = f"There is 1 matching product: {rows.iloc[0]['product_title']}."
        else:
            names = ", ".join(rows["product_title"].astype(str).tolist())
            answer = f"There are {count} matching products: {names}."
        metric = "count"
        target_field = "product_title"
        extra = {}

    return {
        "status": "success",
        "retrieval_mode": "structured",
        "question": question,
        "answer": answer,
        "matching_records": count,
        "displayed_records": min(count, top_k),
        "records": result_records(rows, top_k),
        "metric": metric,
        "target_field": target_field,
        **extra,
    }


def direct_zero_stock_answer(con: Any, catalogue_id: str, question: str, top_k: int = 5):
    if not _is_zero_stock_question(question):
        return None
    records = fetch_catalogue(con, catalogue_id)
    if records.empty:
        rows = records.copy()
    else:
        inventory = pd.to_numeric(records["inventory_quantity"], errors="coerce")
        rows = records[inventory == 0].copy()
    rows = add_category_column(rows)
    rows, _ = filter_by_category(rows, question)
    count = int(len(rows))
    if count == 0:
        answer = "There are no zero-stock products in this catalogue."
    else:
        names = ", ".join(rows["product_title"].astype(str).head(top_k).tolist())
        answer = f"There are {count} zero-stock products. Examples: {names}."
    return {
        "status": "success",
        "retrieval_mode": "structured",
        "question": question,
        "answer": answer,
        "matching_records": count,
        "displayed_records": min(count, top_k),
        "records": result_records(rows, top_k),
        "metric": "count",
        "target_field": "inventory_quantity",
    }


def _source_tags(row: Any) -> list[str]:
    metadata = _normalized_key_map(parse_source_record(row.get("source_record_json")))
    raw = metadata.get("tags", "")
    if isinstance(raw, list):
        values = raw
    else:
        values = re.split(r"[,;|]", str(raw or ""))
    return [str(value).strip() for value in values if str(value).strip()]


def _contains_phrase(text: str, phrase: str) -> bool:
    norm_text = normalize_text(text)
    norm_phrase = normalize_text(phrase)
    if not norm_text or not norm_phrase:
        return False
    return bool(re.search(
        r"(?<![a-z0-9])" + re.escape(norm_phrase) + r"(?![a-z0-9])",
        norm_text,
    ))


def direct_attribute_answer(con: Any, catalogue_id: str, question: str, top_k: int = 5):
    """Resolve an explicitly named catalogue attribute/tag against exact records."""
    q = normalize_text(question)
    if not q:
        return None

    # Do not short-circuit compound price/stock questions; those must flow
    # through the structured hybrid filters so every condition is applied.
    if re.search(r"\b(below|under|above|over|less than|more than|greater than|price|stock|inventory|quantity|units?)\b|₹|\b\d+\b", q):
        return None

    records = fetch_catalogue(con, catalogue_id)
    if records.empty:
        return None

    candidates: dict[str, str] = {}

    # Original source tags are retained during ingestion and work even when
    # an attribute has not yet been extracted by the enrichment model.
    for _, product in records.iterrows():
        for tag in _source_tags(product):
            tag_norm = normalize_text(tag)
            if len(tag_norm) >= 4 and _contains_phrase(q, tag_norm):
                candidates[tag_norm] = tag

    # Also use dynamic extracted attributes, when the live view exists.
    try:
        values = con.execute(
            """
            SELECT DISTINCT attribute_value
            FROM catalogue_attributes_live
            WHERE catalogue_id = ?
            """,
            [catalogue_id],
        ).df()
        for value in values.get("attribute_value", pd.Series(dtype=object)).dropna().tolist():
            value_text = str(value).strip()
            value_norm = normalize_text(value_text)
            if len(value_norm) >= 4 and _contains_phrase(q, value_norm):
                candidates[value_norm] = value_text
    except Exception:
        # The source metadata path remains available if attribute enrichment
        # or the convenience view is absent.
        pass

    if not candidates:
        return None

    target_norm = max(candidates, key=len)
    target_value = candidates[target_norm]
    matched_ids = []

    # Use exact source tags, exact extracted attribute values, or the matching
    # phrase in product descriptions. No semantic shortlist is counted here.
    attribute_ids = set()
    try:
        ids = con.execute(
            """
            SELECT DISTINCT source_record_id
            FROM catalogue_attributes_live
            WHERE catalogue_id = ?
              AND LOWER(TRIM(attribute_value)) = LOWER(TRIM(?))
            """,
            [catalogue_id, target_value],
        ).df()
        if not ids.empty:
            attribute_ids = set(ids["source_record_id"].astype(str))
    except Exception:
        pass

    for _, product in records.iterrows():
        record_id = str(product.get("source_record_id", ""))
        tag_match = any(normalize_text(tag) == target_norm for tag in _source_tags(product))
        description_match = _contains_phrase(product.get("product_description", ""), target_norm)
        if tag_match or description_match or record_id in attribute_ids:
            matched_ids.append(record_id)

    rows = add_category_column(
        records[records["source_record_id"].astype(str).isin(set(matched_ids))].copy()
    )
    rows, _ = filter_by_category(rows, question)
    count = int(len(rows))
    if count == 0:
        return None

    label = target_value.replace("_", " ")
    lines = []
    for index, (_, row) in enumerate(rows.head(top_k).iterrows(), start=1):
        category = row.get("_catalogue_category") or "Category not specified"
        price = row.get("selling_price")
        lines.append(f"{index}. {row['product_title']} — {category} — ₹{price}")
    answer = f"Found {count} matching products for '{label}':\n" + "\n".join(lines)

    return {
        "status": "success",
        "retrieval_mode": "hybrid",
        "question": question,
        "answer": answer,
        "matching_records": count,
        "displayed_records": min(count, top_k),
        "records": result_records(rows, top_k),
        "matched_attribute": label,
    }


def category_target(question: str) -> Optional[str]:
    q = normalize_text(question)
    for category, aliases in CATEGORY_ALIASES.items():
        if any(_contains_phrase(q, alias) for alias in aliases):
            return category
    return None


def filter_by_category(records: pd.DataFrame, question: str):
    """Apply a known category alias and return (records, resolved_category)."""
    target = category_target(question)
    records = add_category_column(records)
    if target is None or records is None or records.empty:
        return records, target

    aliases = CATEGORY_ALIASES[target]

    def keep(row):
        category = normalize_text(row.get("_catalogue_category"))
        if not category:
            return False
        if target == "beauty":
            return any(term in category for term in ("beauty", "skincare", "skin care", "cosmetic", "personal care"))
        if target == "electronics":
            return "electronic" in category
        if target == "home":
            return "home" in category or "household" in category
        if target == "apparel":
            return any(term in category for term in ("apparel", "clothing", "fashion", "garment", "wear"))
        return any(normalize_text(alias) in category for alias in aliases)

    return records[records.apply(keep, axis=1)].copy(), target


def has_explicit_match_condition(filters: list, question: str, category_resolved: bool = False) -> bool:
    """Return True only when all query constraints are represented structurally.

    A semantic descriptor such as "wireless" must not be silently ignored just
    because a category or stock filter was also extracted.
    """
    if not isinstance(filters, list):
        filters = []

    has_structured_condition = category_resolved
    for item in filters:
        if not isinstance(item, dict):
            continue
        filter_type = item.get("type")
        field = item.get("field")
        if filter_type == "attribute" or (
            filter_type in (None, "record") and field in {
                "product_title", "product_description", "selling_price",
                "cost_price", "inventory_quantity"
            }
        ):
            has_structured_condition = True
            break

    if not has_structured_condition:
        return False

    residual = normalize_text(question)
    removable_phrases = [
        *[alias for aliases in CATEGORY_ALIASES.values() for alias in aliases],
        "find", "show", "list", "display", "give", "tell", "me", "all",
        "the", "some", "any", "products", "product", "items", "item",
        "priced", "price", "selling price", "cost price", "inventory",
        "stock", "quantity", "units", "unit", "in", "with", "that",
        "have", "has", "more than", "greater than", "less than", "below",
        "under", "above", "over", "at least", "at most", "and", "for",
        "from", "catalogue", "catalog", "available", "currently",
        "in stock", "out of stock", "zero stock", "total", "count",
    ]
    for phrase in sorted(removable_phrases, key=len, reverse=True):
        normalized = normalize_text(phrase)
        if normalized:
            residual = re.sub(
                r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])",
                " ", residual
            )

    # Remove numeric values/currency tokens and the values that the extractor
    # explicitly converted into structured filters.
    residual = re.sub(r"\b\d+(?:\.\d+)?\b", " ", residual)
    for item in filters:
        if isinstance(item, dict) and item.get("value") is not None:
            value_text = normalize_text(item.get("value"))
            if value_text:
                residual = re.sub(
                    r"(?<![a-z0-9])" + re.escape(value_text) + r"(?![a-z0-9])",
                    " ", residual
                )
    residual_tokens = [
        token for token in residual.split()
        if token not in STOP_ATTRIBUTE_TERMS
    ]
    return len(residual_tokens) == 0
