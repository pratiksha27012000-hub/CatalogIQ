
import json

from google.genai import types

from query_executor import (
    validate_query,
    safe_execute_query
)

MODEL_NAME = "gemini-3.5-flash-lite"


QUERY_INTERPRETER_PROMPT = """
You are the query interpretation engine for CatalogIQ,
a generic e-commerce catalogue intelligence system.

Convert the user's natural-language question into a JSON query specification.

SUPPORTED INTENTS:
- count: count matching catalogue records
- average: calculate the average of a numeric field
- sum: calculate the sum of a numeric field
- filter: retrieve matching records
- missing: find records where a field is NULL

ALLOWED FIELDS:
- product_title
- product_description
- selling_price
- cost_price
- inventory_quantity

ALLOWED FILTER OPERATORS:
- greater_than
- less_than
- equals
- contains

OUTPUT STRUCTURE:
{
  "intent": "filter",
  "target_field": null,
  "metric": null,
  "filters": [],
  "sort_by": null,
  "sort_order": null,
  "limit": null,
  "return_all": false
}

RULES:

1. Use only the supported intents, fields and operators.
2. Never generate SQL.
3. Never invent catalogue values.
4. Use canonical field names.
5. For average and sum, set both metric and target_field
   to the same numeric field.
6. For missing queries, set target_field to the field
   whose missing values are requested.
7. Put all filtering conditions inside filters.
8. Use contains only for text fields.
9. Use greater_than and less_than only for numeric fields.
10. Use numeric values for numeric comparisons.
11. For cheapest or lowest-price requests, sort selling_price
    ascending.
12. For most expensive or highest-price requests, sort
    selling_price descending.
13. For top N requests, set limit to N.
14. If the user explicitly asks for all matching records,
    set return_all to true and limit to null.
15. If no limit is requested, set limit to null
    and return_all to false.
16. Always include every output key.
17. Return valid JSON only. Do not include Markdown.

SORTING RULES:
- sort_order must be exactly "asc" or "desc".
- Use "asc" for ascending order.
- Use "desc" for descending order.
- Never use "ascending" or "descending" as values.


ADDITIONAL AGGREGATION AND PRODUCT-TERM RULES:
- "How many [product type]?", "count [product type]" and "total [product type]?" ask for COUNT of matching product records.
- "How much stock", "stock quantity", "inventory total", "units available" and equivalent Hindi/Hinglish stock questions ask for SUM of inventory_quantity, not COUNT of products.
- For stock totals, use intent="sum", metric="inventory_quantity", target_field="inventory_quantity".
- For product totals/counts, use intent="count".
- Resolve common product synonyms using product_title and product_description evidence, not literal wording alone.
- A verified count must represent records satisfying all stated conditions, not merely the semantic candidate pool.

"""



FOLLOWUP_QUERY_PROMPT = """
You are the follow-up query interpretation engine for CatalogIQ,
a generic e-commerce catalogue intelligence system.

You will receive:
1. The previous user question.
2. The previous structured query specification.
3. The latest user message.

Your task is to update the previous query specification
based on the latest message.

SUPPORTED INTENTS:
- count
- average
- sum
- filter
- missing

ALLOWED FIELDS:
- product_title
- product_description
- selling_price
- cost_price
- inventory_quantity

ALLOWED OPERATORS:
- greater_than
- less_than
- equals
- contains

OUTPUT STRUCTURE:
{
  "intent": "filter",
  "target_field": null,
  "metric": null,
  "filters": [],
  "sort_by": null,
  "sort_order": null,
  "limit": null,
  "return_all": false
}

RULES:

1. Preserve previous filters unless the user changes or removes them.
2. Add new filters when the user adds conditions.
3. Replace only the condition explicitly changed by the user.
4. Remove only the condition explicitly removed by the user.
5. Preserve existing filters when the user asks to sort or limit results.
6. Preserve previous sorting unless the user changes or removes it.
7. For cheapest or lowest-price requests, sort selling_price ascending.
8. For highest or most expensive requests, sort selling_price descending.
9. For top N requests, set limit to N.
10. If the user explicitly asks to show all matching records,
    set return_all to true and limit to null.
11. If the user asks to remove the result limit,
    set return_all to true and limit to null.
12. Preserve filters and sorting when removing a limit.
13. For average and sum, set metric and target_field
    to the same numeric field.
14. For missing-value requests, use the missing intent
    and specify target_field.
15. Never invent catalogue values.
16. Never generate SQL.
17. Use only the allowed fields and operators.
18. Always include every output key.
19. Return valid JSON only. Do not include Markdown.

SORTING RULES:
- sort_order must be exactly "asc" or "desc".
- Use "asc" for ascending order.
- Use "desc" for descending order.
- Never use "ascending" or "descending" as values.


ADDITIONAL AGGREGATION AND PRODUCT-TERM RULES:
- "How many [product type]?", "count [product type]" and "total [product type]?" ask for COUNT of matching product records.
- "How much stock", "stock quantity", "inventory total", "units available" and equivalent Hindi/Hinglish stock questions ask for SUM of inventory_quantity, not COUNT of products.
- For stock totals, use intent="sum", metric="inventory_quantity", target_field="inventory_quantity".
- For product totals/counts, use intent="count".
- Resolve common product synonyms using product_title and product_description evidence, not literal wording alone.
- A verified count must represent records satisfying all stated conditions, not merely the semantic candidate pool.

"""






def _generate_query_spec(client, prompt):
    import json
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0
        )
    )

    raw = (response.text or "").strip()

    if not raw:
        raise ValueError("The model returned an empty response.")

    query_spec = json.loads(raw)

    # Safely unwrap a single-object array.
    if isinstance(query_spec, list):
        if len(query_spec) == 1 and isinstance(query_spec[0], dict):
            query_spec = query_spec[0]
        else:
            raise ValueError(
                "The model returned multiple query specifications. "
                "This operation requires multi-metric summary handling."
            )

    if not isinstance(query_spec, dict):
        raise ValueError("Expected a JSON query specification object.")

    return normalize_query_spec(query_spec)


def normalize_query_spec(query_spec):

    sort_order = query_spec.get("sort_order")

    sort_order_mapping = {
        "ascending": "asc",
        "descending": "desc",
        "asc": "asc",
        "desc": "desc"
    }

    if isinstance(sort_order, str):
        query_spec["sort_order"] = sort_order_mapping.get(
            sort_order.lower(),
            sort_order
        )

    return query_spec


def interpret_query(client, question):

    prompt = f"""
{QUERY_INTERPRETER_PROMPT}

USER QUESTION:
{question}
"""

    return _generate_query_spec(client, prompt)


def interpret_followup(client, previous_question, previous_query_spec, latest_question):

    prompt = f"""
{FOLLOWUP_QUERY_PROMPT}

PREVIOUS USER QUESTION:
{previous_question}

PREVIOUS QUERY SPECIFICATION:
{json.dumps(previous_query_spec)}

LATEST USER MESSAGE:
{latest_question}
"""

    return _generate_query_spec(client, prompt)


def ask_catalogiq(con, client, catalogue_id, question):

    try:
        query_spec = interpret_query(client, question)

        validation = validate_query(query_spec)

        if not validation["valid"]:
            return {
                "status": "error",
                "stage": "validation",
                "errors": validation["errors"],
                "query_spec": query_spec
            }

        result = safe_execute_query(
            con,
            query_spec,
            catalogue_id
        )

        return {
            "status": result["status"],
            "question": question,
            "query_spec": query_spec,
            "result": result,
            "conversation_state": {
                "previous_question": question,
                "previous_query_spec": query_spec
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "stage": "interpretation_or_execution",
            "errors": [str(e)]
        }


def ask_catalogiq_followup(
    con,
    client,
    catalogue_id,
    question,
    conversation_state
):

    if not conversation_state:
        return ask_catalogiq(
            con,
            client,
            catalogue_id,
            question
        )

    try:
        previous_question = conversation_state.get("previous_question")
        previous_query_spec = conversation_state.get("previous_query_spec")

        if not previous_question or not previous_query_spec:
            return ask_catalogiq(
                con,
                client,
                catalogue_id,
                question
            )

        query_spec = interpret_followup(
            client,
            previous_question,
            previous_query_spec,
            question
        )

        validation = validate_query(query_spec)

        if not validation["valid"]:
            return {
                "status": "error",
                "stage": "validation",
                "errors": validation["errors"],
                "query_spec": query_spec,
                "conversation_state": conversation_state
            }

        result = safe_execute_query(
            con,
            query_spec,
            catalogue_id
        )

        return {
            "status": result["status"],
            "question": question,
            "query_spec": query_spec,
            "result": result,
            "conversation_state": {
                "previous_question": question,
                "previous_query_spec": query_spec
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "stage": "followup_interpretation_or_execution",
            "errors": [str(e)],
            "conversation_state": conversation_state
        }



# CATALOGIQ GENERAL CROSS-FIELD INTERPRETER
import re as _catalogiq_re

_catalogiq_original_interpret_query = interpret_query


def _catalogiq_apply_search_scope(query_spec, question):
    """
    Generic text searches use the complete product information.
    Explicit title/description searches retain their requested scope.
    """

    q = str(question or "").casefold()

    explicit_title = bool(_catalogiq_re.search(
        r"\b(?:in|within)\s+(?:(?:the|their)\s+)?"
        r"(?:product\s+)?titles?\b|"
        r"\b(?:product\s+)?titles?\s+"
        r"(?:contains?|containing|includes?|including|has)\b|"
        r"\btitle\s+field\b",
        q
    ))

    explicit_description = bool(_catalogiq_re.search(
        r"\b(?:in|within)\s+(?:(?:the|their)\s+)?"
        r"(?:product\s+)?descriptions?\b|"
        r"\b(?:product\s+)?descriptions?\s+"
        r"(?:contains?|containing|includes?|including|has)\b|"
        r"\bdescription\s+field\b",
        q
    ))

    if explicit_title:
        search_field = "product_title"
    elif explicit_description:
        search_field = "product_description"
    else:
        search_field = "product_text"

    for item in query_spec.get("filters", []):
        if (
            isinstance(item, dict)
            and item.get("operator") == "contains"
            and item.get("field") in {
                "product_title",
                "product_description",
                "product_text"
            }
        ):
            item["field"] = search_field

    return query_spec


def interpret_query(client, question):
    query_spec = _catalogiq_original_interpret_query(
        client, question
    )
    return _catalogiq_apply_search_scope(
        query_spec, question
    )




# CATALOGIQ GEMINI RETRY HANDLING

import time as _catalogiq_time
import json as _catalogiq_json


class _CatalogIQRetryableResponseError(Exception):
    pass


def _catalogiq_is_transient_error(error):

    transient_codes = {408, 429, 500, 502, 503, 504}

    candidates = [
        getattr(error, "code", None),
        getattr(error, "status_code", None),
        getattr(getattr(error, "response", None),
                "status_code", None)
    ]

    for candidate in candidates:
        try:
            if int(candidate) in transient_codes:
                return True
        except (TypeError, ValueError):
            pass

    message = (
        type(error).__name__ + " " + str(error)
    ).upper()

    transient_markers = [
        "503",
        "UNAVAILABLE",
        "RESOURCE_EXHAUSTED",
        "TOO_MANY_REQUESTS",
        "500 INTERNAL",
        "502",
        "504",
        "DEADLINE_EXCEEDED",
        "SERVICE_UNAVAILABLE",
        "TIMED OUT",
        "TIMEOUT",
        "CONNECTION RESET",
        "CONNECTION REFUSED",
        "TEMPORARILY UNAVAILABLE"
    ]

    return any(marker in message for marker in transient_markers)


def _generate_query_spec(client, prompt):

    from google.genai import types

    max_attempts = 3
    last_error = None

    for attempt in range(max_attempts):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0
                )
            )

            raw = (response.text or "").strip()

            if not raw:
                raise _CatalogIQRetryableResponseError(
                    "The model returned an empty response."
                )

            try:
                query_spec = _catalogiq_json.loads(raw)
            except _catalogiq_json.JSONDecodeError as error:
                raise _CatalogIQRetryableResponseError(
                    "The model returned malformed JSON."
                ) from error

            if isinstance(query_spec, list):

                if (
                    len(query_spec) == 1
                    and isinstance(query_spec[0], dict)
                ):
                    query_spec = query_spec[0]

                else:
                    raise ValueError(
                        "The model returned multiple query specifications. "
                        "Multi-metric summary handling is not supported."
                    )

            if not isinstance(query_spec, dict):
                raise ValueError(
                    "Expected a JSON query specification object."
                )

            return normalize_query_spec(query_spec)

        except Exception as error:

            last_error = error

            retryable = (
                isinstance(error, _CatalogIQRetryableResponseError)
                or _catalogiq_is_transient_error(error)
            )

            if not retryable or attempt == max_attempts - 1:
                raise RuntimeError(
                    "Query interpretation failed after "
                    f"{attempt + 1} attempt(s): {error}"
                ) from error

            delay = 2 ** (attempt + 1)

            print(
                f"Temporary Gemini error. "
                f"Retrying in {delay} seconds "
                f"(attempt {attempt + 2}/{max_attempts})."
            )

            _catalogiq_time.sleep(delay)

    raise RuntimeError(
        f"Query interpretation failed: {last_error}"
    )

