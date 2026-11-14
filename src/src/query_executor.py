# CATALOGIQ PRODUCT_TEXT CROSS-FIELD SEARCH\n
import pandas as pd

ALLOWED_INTENTS = {
    "count", "average", "sum", "filter", "missing"
}

PHYSICAL_FIELDS = {
    "product_title",
    "product_description",
    "selling_price",
    "cost_price",
    "inventory_quantity"
}

# Virtual field: search the full product information.
ALLOWED_FIELDS = PHYSICAL_FIELDS | {"product_text"}

ALLOWED_OPERATORS = {
    "greater_than", "less_than", "equals", "contains"
}

NUMERIC_FIELDS = {
    "selling_price",
    "cost_price",
    "inventory_quantity"
}

TEXT_FIELDS = {
    "product_title",
    "product_description",
    "product_text"
}


def validate_query(query_spec):

    errors = []

    if not isinstance(query_spec, dict):
        return {
            "valid": False,
            "errors": ["Query specification must be a dictionary."]
        }

    intent = query_spec.get("intent")
    metric = query_spec.get("metric")
    target_field = query_spec.get("target_field")
    filters = query_spec.get("filters", [])
    sort_by = query_spec.get("sort_by")
    sort_order = query_spec.get("sort_order")
    limit = query_spec.get("limit")
    return_all = query_spec.get("return_all", False)

    # Validate intent
    if intent not in ALLOWED_INTENTS:
        errors.append("Unsupported or missing intent.")

    # Validate target field
    if target_field is not None and target_field not in ALLOWED_FIELDS:
        errors.append("Invalid target field.")

    if intent == "missing" and target_field not in PHYSICAL_FIELDS:
        errors.append("Missing queries require a valid target field.")

    # Validate aggregation metric
    if intent in {"average", "sum"}:
        if metric not in NUMERIC_FIELDS:
            errors.append("Invalid or missing numeric metric.")

        if target_field != metric:
            errors.append("Target field must match the aggregation metric.")

    # Validate filters
    if not isinstance(filters, list):
        errors.append("Filters must be provided as a list.")
        filters = []

    for i, item in enumerate(filters):

        if not isinstance(item, dict):
            errors.append(f"Filter {i}: Must be a dictionary.")
            continue

        field = item.get("field")
        operator = item.get("operator")
        value = item.get("value")

        if field not in ALLOWED_FIELDS:
            errors.append(f"Filter {i}: Invalid field.")
            continue

        if operator not in ALLOWED_OPERATORS:
            errors.append(f"Filter {i}: Invalid operator.")
            continue

        if value is None:
            errors.append(f"Filter {i}: Missing value.")
            continue

        if operator == "contains":
            if field not in TEXT_FIELDS or not isinstance(value, str):
                errors.append(
                    f"Filter {i}: Contains requires a text field and string value."
                )

        elif operator in {"greater_than", "less_than"}:
            if field not in NUMERIC_FIELDS:
                errors.append(
                    f"Filter {i}: Numeric comparison requires a numeric field."
                )
            elif (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                errors.append(
                    f"Filter {i}: Numeric comparison requires a number."
                )

        elif operator == "equals":

            if field in NUMERIC_FIELDS:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                ):
                    errors.append(
                        f"Filter {i}: Numeric equality requires a number."
                    )

            elif not isinstance(value, str):
                errors.append(
                    f"Filter {i}: Text equality requires a string."
                )

    # Validate sorting
    if (sort_by is None) != (sort_order is None):
        errors.append("sort_by and sort_order must be supplied together.")

    if sort_by is not None:
        if sort_by not in PHYSICAL_FIELDS:
            errors.append("Invalid sorting field.")

        if sort_order not in {"asc", "desc"}:
            errors.append("Invalid sorting order.")

        if intent not in {"filter", "missing"}:
            errors.append("Sorting is only supported for filter and missing queries.")

    # Validate result limit
    if limit is not None:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            errors.append("Limit must be an integer between 1 and 100.")

    if not isinstance(return_all, bool):
        errors.append("return_all must be a boolean.")

    if return_all is True and limit is not None:
        errors.append("When return_all is true, limit must be None.")

    if return_all is True and intent not in {"filter", "missing"}:
        errors.append("return_all is only supported for filter and missing queries.")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def safe_execute_query(con, query_spec, catalogue_id, default_limit=50):

    # 1. Validate query specification
    validation = validate_query(query_spec)

    if not validation["valid"]:
        return {
            "status": "error",
            "errors": validation["errors"]
        }

    # 2. Confirm catalogue is active
    catalogue = con.execute("""
        SELECT catalogue_id
        FROM catalogue_registry
        WHERE catalogue_id = ?
          AND status = 'active'
    """, [catalogue_id]).fetchone()

    if catalogue is None:
        return {
            "status": "error",
            "errors": ["Catalogue not found or inactive."]
        }

    # 3. Read query specification
    intent = query_spec["intent"]
    metric = query_spec.get("metric")
    target_field = query_spec.get("target_field")
    filters = query_spec.get("filters", [])

    sort_by = query_spec.get("sort_by")
    sort_order = query_spec.get("sort_order")
    requested_limit = query_spec.get("limit")
    return_all = query_spec.get("return_all", False)

    # 4. Build parameterised SQL conditions
    conditions = ["catalogue_id = ?"]
    parameters = [catalogue_id]

    for item in filters:

        field = item["field"]
        operator = item["operator"]
        value = item["value"]

        if operator == "greater_than":
            conditions.append(f"{field} > ?")
            parameters.append(value)

        elif operator == "less_than":
            conditions.append(f"{field} < ?")
            parameters.append(value)

        elif operator == "equals":
            conditions.append(f"{field} = ?")
            parameters.append(value)

        elif operator == "contains":
            pattern = f"%{value}%"

            if field == "product_text":
                conditions.append(
                    "("
                    "product_title ILIKE ? "
                    "OR product_description ILIKE ? "
                    "OR CAST(source_record_json AS VARCHAR) ILIKE ? "
                    "OR EXISTS ("
                    "SELECT 1 FROM catalogue_attributes_live AS attr "
                    "WHERE attr.catalogue_id = catalogue_records.catalogue_id "
                    "AND attr.source_record_id = catalogue_records.source_record_id "
                    "AND (attr.attribute_value ILIKE ? "
                    "OR attr.attribute_name ILIKE ? "
                    "OR attr.evidence ILIKE ?)"
                    ")"
                    ")"
                )
                parameters.extend([pattern] * 6)

            else:
                conditions.append(f"{field} ILIKE ?")
                parameters.append(pattern)

    # 5. Handle missing-value queries
    if intent == "missing":
        conditions.append(f"{target_field} IS NULL")

    where_clause = " AND ".join(conditions)

    # 6. Count records
    if intent == "count":

        result = con.execute(
            f"""
            SELECT COUNT(*)
            FROM catalogue_records
            WHERE {where_clause}
            """,
            parameters
        ).fetchone()[0]

        return {
            "status": "success",
            "answer": int(result),
            "matching_records": int(result)
        }

    # 7. Aggregation queries
    if intent in {"average", "sum"}:

        sql_function = {
            "average": "AVG",
            "sum": "SUM"
        }[intent]

        result = con.execute(
            f"""
            SELECT {sql_function}({metric})
            FROM catalogue_records
            WHERE {where_clause}
            """,
            parameters
        ).fetchone()[0]

        if result is not None:
            result = round(float(result), 2)

        return {
            "status": "success",
            "answer": result,
            "metric": metric,
            "target_field": target_field
        }

    # 8. Filter and missing-value queries
    total = con.execute(
        f"""
        SELECT COUNT(*)
        FROM catalogue_records
        WHERE {where_clause}
        """,
        parameters
    ).fetchone()[0]

    # Sorting
    order_clause = ""

    if sort_by is not None:
        order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"

    # Result limit
    if return_all:
        limit_clause = ""
        records_parameters = parameters

    else:
        result_limit = (
            requested_limit
            if requested_limit is not None
            else default_limit
        )

        limit_clause = "LIMIT ?"
        records_parameters = parameters + [result_limit]

    # Fetch matching records
    records = con.execute(
        f"""
        SELECT
            source_record_id,
            product_title,
            product_description,
            selling_price,
            cost_price,
            inventory_quantity,
            source_record_json
        FROM catalogue_records
        WHERE {where_clause}
        {order_clause}
        {limit_clause}
        """,
        records_parameters
    ).df()

    return {
        "status": "success",
        "answer": f"{total} matching records found.",
        "matching_records": int(total),
        "displayed_records": len(records),
        "sort_by": sort_by,
        "sort_order": sort_order,
        "limit": None if return_all else (
            requested_limit if requested_limit is not None else default_limit
        ),
        "return_all": return_all,
        "records": records
    }
