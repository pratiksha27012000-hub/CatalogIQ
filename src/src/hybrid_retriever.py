
import json
import re
import numpy as np
import pandas as pd

from google.genai import types


MODEL_NAME = "gemini-3.5-flash-lite"

ALLOWED_FIELDS = {
    "product_title",
    "product_description",
    "selling_price",
    "cost_price",
    "inventory_quantity"
}

TEXT_FIELDS = {
    "product_title",
    "product_description"
}

NUMERIC_FIELDS = {
    "selling_price",
    "cost_price",
    "inventory_quantity"
}

ALLOWED_OPERATORS = {
    "greater_than",
    "less_than",
    "equals",
    "contains"
}

ATTRIBUTE_OPERATORS = {"equals", "contains"}


HYBRID_FILTER_PROMPT = """
You are the query filter extraction engine for CatalogIQ,
a generic e-commerce catalogue intelligence system.

Extract only explicit structured conditions from the user's query.

Return JSON in this format:

{
  "filters": [
    {
      "type": "record",
      "field": "selling_price",
      "operator": "less_than",
      "value": 5000
    },
    {
      "type": "attribute",
      "attribute_name": "fabric",
      "operator": "contains",
      "value": "cotton"
    }
  ]
}

RECORD FIELDS:
- product_title
- product_description
- selling_price
- cost_price
- inventory_quantity

RECORD OPERATORS:
- greater_than
- less_than
- equals
- contains

ATTRIBUTE FIELDS:
Only use the canonical attribute names supplied for this catalogue.

ATTRIBUTE OPERATORS:
- equals
- contains

RULES:

1. Price conditions map to selling_price unless the user
   explicitly mentions cost price.

2. Stock or quantity conditions map to inventory_quantity.

3. Map an explicitly stated product attribute or attribute value
   to an available catalogue attribute.

4. For example, if "fabric" is an available attribute and the user
   asks for cotton products, use attribute_name="fabric" and
   operator="contains".

5. Do not invent attribute names that are not in the supplied list.

6. Do not convert subjective semantic intent into structured filters.
   For example, "comfortable for everyday use" remains semantic intent
   unless the user explicitly specifies a supported attribute.

7. Only extract conditions explicitly stated by the user.

8. Multiple filters are combined with AND logic.

9. Return an empty filters list if there are no explicit
   structured conditions.


10. If the customer explicitly asks for in-stock or available-now
    products, extract inventory_quantity greater_than 0.

11. If the customer explicitly asks for out-of-stock, sold-out,
    or unavailable products, extract inventory_quantity equals 0.

12. Do not infer inventory availability from product descriptions.
    Use the inventory_quantity field only.

13. Return valid JSON only.


AVAILABLE CATALOGUE ATTRIBUTES:
"""


def canonicalize_attribute_name(name):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(name).strip().lower()
    ).strip("_")


def get_available_attributes(con, catalogue_id):
    """Get attributes actually present in the selected catalogue."""

    rows = con.execute("""
        SELECT DISTINCT canonical_attribute_name
        FROM catalogue_attributes_live
        WHERE catalogue_id = ?
        ORDER BY canonical_attribute_name
    """, [catalogue_id]).fetchall()

    return {
        row[0]
        for row in rows
    }


def normalize_filter_item(item):
    """Support both new filter structure and legacy record filters."""

    if not isinstance(item, dict):
        return item

    result = dict(item)

    filter_type = result.get("type")

    if filter_type is None:
        if result.get("field") in ALLOWED_FIELDS:
            result["type"] = "record"
        else:
            result["type"] = "attribute"
            result["attribute_name"] = (
                result.get("attribute_name")
                or result.get("field")
            )

    if result.get("type") == "attribute":
        result["attribute_name"] = canonicalize_attribute_name(
            result.get("attribute_name", "")
        )

    return result


def validate_extracted_filters(
    filters,
    con=None,
    catalogue_id=None,
    available_attributes=None
):
    """Validate record filters and catalogue-specific attribute filters."""

    if not isinstance(filters, list):
        return {
            "valid": False,
            "errors": ["Filters must be a list."]
        }

    if available_attributes is None and con is not None:
        if catalogue_id is None:
            return {
                "valid": False,
                "errors": ["Catalogue ID is required for attribute validation."]
            }

        available_attributes = get_available_attributes(
            con,
            catalogue_id
        )

    available_attributes = available_attributes or set()

    errors = []

    for index, raw_item in enumerate(filters):

        item = normalize_filter_item(raw_item)

        if not isinstance(item, dict):
            errors.append(
                f"Filter {index}: Invalid filter structure."
            )
            continue

        filter_type = item.get("type")
        operator = item.get("operator")
        value = item.get("value")

        if operator not in ALLOWED_OPERATORS:
            errors.append(
                f"Filter {index}: Unsupported operator."
            )
            continue

        if filter_type == "record":

            field = item.get("field")

            if field not in ALLOWED_FIELDS:
                errors.append(
                    f"Filter {index}: Unsupported record field."
                )
                continue

            if operator == "contains":

                if field not in TEXT_FIELDS:
                    errors.append(
                        f"Filter {index}: Contains requires a text field."
                    )

                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"Filter {index}: Contains requires non-empty text."
                    )

            elif operator in {"greater_than", "less_than"}:

                if field not in NUMERIC_FIELDS:
                    errors.append(
                        f"Filter {index}: Numeric operator requires numeric field."
                    )

                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                ):
                    errors.append(
                        f"Filter {index}: Numeric value required."
                    )

            elif operator == "equals":

                if field in NUMERIC_FIELDS:
                    if (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                    ):
                        errors.append(
                            f"Filter {index}: Numeric equality requires a number."
                        )

                elif field in TEXT_FIELDS:
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"Filter {index}: Text equality requires non-empty text."
                        )

        elif filter_type == "attribute":

            attribute_name = canonicalize_attribute_name(
                item.get("attribute_name", "")
            )

            if not attribute_name:
                errors.append(
                    f"Filter {index}: Missing attribute name."
                )
                continue

            if attribute_name not in available_attributes:
                errors.append(
                    f"Filter {index}: Attribute is not available "
                    f"in this catalogue: {attribute_name}"
                )

            if operator not in ATTRIBUTE_OPERATORS:
                errors.append(
                    f"Filter {index}: Attribute filters only support "
                    "equals and contains."
                )

            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"Filter {index}: Attribute value must be non-empty text."
                )

        else:
            errors.append(
                f"Filter {index}: Unsupported filter type."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }



def detect_availability_intent(question):
    """
    Detect explicit stock availability requests.

    Returns:
        in_stock
        out_of_stock
        None
    """

    if not isinstance(question, str):
        return None

    q = re.sub(r"\s+", " ", question.casefold()).strip()

    # Negated out-of-stock requests mean available products.
    if re.search(
        r"\bnot\s+(?:out\s+of\s+stock|sold\s+out)\b",
        q
    ):
        return "in_stock"

    out_of_stock_patterns = [
        r"\bout[\s-]+of[\s-]+stock\b",
        r"\bsold[\s-]+out\b",
        r"\bunavailable\b",
        r"\bnot[\s-]+available\b",
        r"\bno[\s-]+stock\b",
        r"\bzero[\s-]+stock\b"
    ]

    if any(re.search(pattern, q) for pattern in out_of_stock_patterns):
        return "out_of_stock"

    in_stock_patterns = [
        r"\bin[\s-]+stock\b",
        r"\bavailable[\s-]+now\b",
        r"\bcurrently[\s-]+available\b",
        r"\bready[\s-]+to[\s-]+ship\b",
        r"\bavailable[\s-]+for[\s-]+purchase\b",
        r"\bavailable[\s-]+products?\b",
        r"\bproducts?\s+available\b"
    ]

    if any(re.search(pattern, q) for pattern in in_stock_patterns):
        return "in_stock"

    return None


def extract_hybrid_filters(
    client,
    question,
    con=None,
    catalogue_id=None
):
    """Extract structured and dynamic attribute filters."""

    if not isinstance(question, str) or not question.strip():
        return {
            "status": "error",
            "errors": ["Question cannot be empty."]
        }

    if con is not None and catalogue_id is not None:
        available_attributes = get_available_attributes(
            con,
            catalogue_id
        )
    else:
        available_attributes = set()

    attribute_list = "\n".join(
        f"- {name}"
        for name in sorted(available_attributes)
    )

    prompt = (
        HYBRID_FILTER_PROMPT
        + "\n"
        + (attribute_list or "- No extracted attributes available")
        + "\n\nUSER QUESTION:\n"
        + question
    )

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0
            )
        )

        result = json.loads(response.text)

    except (json.JSONDecodeError, TypeError, AttributeError):
        return {
            "status": "error",
            "errors": ["Invalid filter extraction response."]
        }

    except Exception as e:
        return {
            "status": "error",
            "errors": [str(e)]
        }

    if not isinstance(result, dict):
        return {
            "status": "error",
            "errors": ["Invalid filter response structure."]
        }

    raw_filters = result.get("filters")

    if not isinstance(raw_filters, list):
        return {
            "status": "error",
            "errors": ["Filters must be a list."]
        }

    filters = [
        normalize_filter_item(item)
        for item in raw_filters
    ]

    validation = validate_extracted_filters(
        filters,
        available_attributes=available_attributes
    )

    if not validation["valid"]:
        return {
            "status": "error",
            "errors": validation["errors"]
        }

    return {
        "status": "success",
        "filters": filters
    }


def execute_hybrid_search(
    con,
    semantic_manager,
    catalogue_id,
    semantic_query,
    filters,
    top_k=None
):
    """
    Apply structured record filters and dynamic attribute filters
    before semantic ranking.
    """

    if not isinstance(semantic_query, str) or not semantic_query.strip():
        return {
            "status": "error",
            "errors": ["Semantic query cannot be empty."]
        }

    if top_k is not None:
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            return {
                "status": "error",
                "errors": [
                    "top_k must be a positive integer or None."
                ]
            }

    available_attributes = get_available_attributes(
        con,
        catalogue_id
    )

    normalized_filters = [
        normalize_filter_item(item)
        for item in filters
    ] if isinstance(filters, list) else filters

    validation = validate_extracted_filters(
        normalized_filters,
        available_attributes=available_attributes
    )

    if not validation["valid"]:
        return {
            "status": "error",
            "errors": validation["errors"]
        }

    # ----------------------------------------------
    # 1. Build parameterized structured candidate SQL
    # ----------------------------------------------

    sql = """
        SELECT r.*
        FROM catalogue_records r
        WHERE r.catalogue_id = ?
    """

    params = [catalogue_id]

    for item in normalized_filters:

        filter_type = item["type"]
        operator = item["operator"]
        value = item["value"]

        if filter_type == "record":

            field = item["field"]

            if operator == "greater_than":
                sql += f" AND r.{field} > ?"

            elif operator == "less_than":
                sql += f" AND r.{field} < ?"

            elif operator == "equals":
                if field in NUMERIC_FIELDS:
                    sql += f" AND r.{field} = ?"
                else:
                    sql += (
                        f" AND LOWER(TRIM(r.{field})) = LOWER(TRIM(?))"
                    )

            elif operator == "contains":
                sql += (
                    f" AND STRPOS("
                    f"LOWER(COALESCE(r.{field}, '')), "
                    f"LOWER(?)"
                    f") > 0"
                )

            params.append(value)

        elif filter_type == "attribute":

            attribute_name = item["attribute_name"]

            if operator == "contains":
                comparison = (
                    "STRPOS(LOWER(a.attribute_value), LOWER(?)) > 0"
                )
            else:
                comparison = (
                    "LOWER(TRIM(a.attribute_value)) = LOWER(TRIM(?))"
                )

            sql += f"""
                AND EXISTS (
                    SELECT 1
                    FROM catalogue_attributes_live a
                    WHERE a.catalogue_id = r.catalogue_id
                      AND a.source_record_id = r.source_record_id
                      AND a.canonical_attribute_name = ?
                      AND {comparison}
                )
            """

            params.extend([
                attribute_name,
                value
            ])

    # ----------------------------------------------
    # 2. Retrieve structured + attribute candidates
    # ----------------------------------------------

    structured_results = con.execute(
        sql,
        params
    ).df()

    structured_count = len(structured_results)

    if structured_results.empty:
        return {
            "status": "success",
            "structured_candidates": 0,
            "indexed_candidates": 0,
            "matching_count": 0,
            "displayed_count": 0,
            "attribute_filters_applied": sum(
                item["type"] == "attribute"
                for item in normalized_filters
            ),
            "results": structured_results
        }

    # ----------------------------------------------
    # 3. Get semantic index and stored embeddings
    # ----------------------------------------------

    index_data = semantic_manager.catalogue_indexes.get(
        catalogue_id
    )

    if index_data is None:
        return {
            "status": "error",
            "errors": [
                "Semantic index not found for this catalogue."
            ]
        }

    indexed_records = index_data["records"]
    record_embeddings = index_data.get("record_embeddings")

    if record_embeddings is None:
        return {
            "status": "error",
            "errors": [
                "Record embeddings are missing. Rebuild the semantic index."
            ]
        }

    if len(record_embeddings) != len(indexed_records):
        return {
            "status": "error",
            "errors": [
                "Semantic record and embedding counts do not match."
            ]
        }

    # ----------------------------------------------
    # 4. Match eligible product records to embeddings
    # ----------------------------------------------

    semantic_id_to_position = {
        record_id: position
        for position, record_id in enumerate(
            indexed_records["source_record_id"]
        )
    }

    structured_results = structured_results.copy()

    structured_results["_embedding_position"] = (
        structured_results["source_record_id"].map(
            semantic_id_to_position
        )
    )

    indexed_results = structured_results.dropna(
        subset=["_embedding_position"]
    ).copy()

    if indexed_results.empty:
        return {
            "status": "success",
            "structured_candidates": structured_count,
            "indexed_candidates": 0,
            "matching_count": 0,
            "displayed_count": 0,
            "attribute_filters_applied": sum(
                item["type"] == "attribute"
                for item in normalized_filters
            ),
            "results": indexed_results.drop(
                columns=["_embedding_position"],
                errors="ignore"
            )
        }

    positions = indexed_results[
        "_embedding_position"
    ].astype(int).to_numpy()

    # ----------------------------------------------
    # 5. Semantic ranking of eligible candidates
    # ----------------------------------------------

    query_embedding = semantic_manager.model.encode(
        [semantic_query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    ).astype("float32")[0]

    eligible_embeddings = record_embeddings[positions]

    similarity_scores = (
        eligible_embeddings @ query_embedding
    )

    indexed_results["similarity_score"] = similarity_scores

    indexed_results = indexed_results.sort_values(
        "similarity_score",
        ascending=False
    ).reset_index(drop=True)

    matching_count = len(indexed_results)

    if top_k is not None:
        displayed_results = indexed_results.head(top_k).copy()
    else:
        displayed_results = indexed_results.copy()

    displayed_results = displayed_results.drop(
        columns=["_embedding_position"],
        errors="ignore"
    )

    return {
        "status": "success",
        "structured_candidates": structured_count,
        "indexed_candidates": matching_count,
        "matching_count": matching_count,
        "displayed_count": len(displayed_results),
        "attribute_filters_applied": sum(
            item["type"] == "attribute"
            for item in normalized_filters
        ),
        "results": displayed_results.reset_index(drop=True)
    }



def route_query(client, question):
    """
    Deterministically route catalogue questions.

    structured: exact counts, sums, averages and missing-value queries
    hybrid: explicit price, stock, category or attribute conditions
    semantic: descriptive and conceptual product discovery
    """

    import re

    if not isinstance(question, str) or not question.strip():
        return {
            "status": "error",
            "errors": ["Question cannot be empty."]
        }

    q = re.sub(r"\s+", " ", question.casefold()).strip()

    # Aggregation and structured-data questions
    structured_patterns = [
        r"\baverage\b",
        r"\bavg\b",
        r"\bmean\b",
        r"\bhow many\b",
        r"\bnumber of\b",
        r"\bcount\b",
        r"\bsum\b",
        r"\btotal\s+(products|items|records|inventory|stock|quantity)\b",
        r"\bmissing\b",
        r"\bnull\b",
        r"\bblank values?\b"
    ]

    # Explicit comparison and catalogue filtering conditions
    hybrid_patterns = [
        r"\bbelow\b",
        r"\bunder\b",
        r"\bless than\b",
        r"\bgreater than\b",
        r"\bmore than\b",
        r"\babove\b",
        r"\bover\b",
        r"\bat least\b",
        r"\bat most\b",
        r"\bbetween\b",
        r"\bin stock\b",
        r"\bout of stock\b",
        r"\bsold out\b",
        r"\bavailable now\b",
        r"\bzero stock\b",
        r"\bfragrance[- ]free\b",
        r"\bwaterproof\b",
        r"\bwireless\b",
        r"\bcotton\b",
        r"\bsilk\b",
        r"\bleather\b",
        r"\blinen\b",
        r"\bwool\b",
        r"\bmaterial\b",
        r"\bfabric\b",
        r"\bcolour\b",
        r"\bcolor\b",
        r"\bcategory\b",
        r"\bbrand\b"
    ]

    if any(re.search(p, q) for p in structured_patterns):
        mode = "structured"

    elif any(re.search(p, q) for p in hybrid_patterns):
        mode = "hybrid"

    else:
        mode = "semantic"

    return {
        "status": "success",
        "retrieval_mode": mode,
        "semantic_query": question.strip()
    }
