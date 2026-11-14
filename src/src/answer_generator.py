
import json
import pandas as pd


MODEL_NAME = "gemini-3.5-flash-lite"


def prepare_evidence(results, max_records=10):

    from bs4 import BeautifulSoup
    try:
        import ftfy
        fix_text = ftfy.fix_text
    except ImportError:
        # HTML cleanup remains available even when the optional text-fixer
        # package is not installed in a minimal environment.
        fix_text = str

    if results is None:
        return []

    if not isinstance(results, pd.DataFrame):
        raise TypeError("Results must be a pandas DataFrame.")

    if results.empty:
        return []

    allowed_fields = [
        "source_record_id",
        "product_title",
        "product_description",
        "selling_price",
        "inventory_quantity",
        "similarity_score",
        "_catalogue_category",
        "category",
        "product_type",
        "Product Type",
        "source_record_json",
    ]

    available_fields = [
        field for field in allowed_fields
        if field in results.columns
    ]

    evidence = []

    for _, row in results.head(max_records).iterrows():

        record = {}

        for field in available_fields:

            value = row[field]

            if pd.isna(value):
                record[field] = None

            elif field == "product_description":

                text = fix_text(str(value))
                soup = BeautifulSoup(text, "html.parser")

                record[field] = soup.get_text(
                    " ",
                    strip=True
                )[:1000]

            elif field == "source_record_json":
                # Source metadata is used only to recover display context such
                # as category; raw source JSON is not sent to the answer model.
                continue
            elif field in {"_catalogue_category", "category", "product_type", "Product Type"}:
                if str(value).strip():
                    record["category"] = str(value).strip()
            else:
                record[field] = value

        if "category" not in record:
            try:
                from catalogue_intelligence import category_from_row
                category = category_from_row(row)
                if category:
                    record["category"] = category
            except Exception:
                pass

        evidence.append(record)

    return evidence


def generate_answer(
    client,
    question,
    retrieval_result,
    retrieval_mode="structured"
):

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty.")

    if retrieval_result.get("status") != "success":
        return {
            "status": "error",
            "answer": "I could not retrieve the requested catalogue information."
        }

    results = retrieval_result.get("results")

    evidence = prepare_evidence(results)

    matching_count = retrieval_result.get("matching_count")

    if not evidence:
        if matching_count == 0:
            empty_answer = "No matching catalogue records were found (verified total: 0)."
        elif matching_count is None:
            empty_answer = "No records were retrieved. The exact number of matching products could not be verified."
        else:
            empty_answer = f"The query has {matching_count} verified matching records, but no product details were supplied."
        return {
            "status": "success",
            "answer": empty_answer,
            "matching_count": matching_count,
            "displayed_count": 0,
            "evidence": []
        }

    if matching_count is None:
        count_context = (
            "The exact total number of matching records has NOT been verified. "
            "The supplied records are a retrieved shortlist, not a complete match set."
        )
    else:
        count_context = (
            f"Verified total matching records: {matching_count}"
        )

    prompt = f"""
You are CatalogIQ, an e-commerce catalogue intelligence assistant.

User question:
{question}

Retrieval mode:
{retrieval_mode}

{count_context}

Number of records supplied:
{len(evidence)}

Retrieved records:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Instructions:
- Answer only using the supplied evidence.
- Never invent product details or specifications.
- Do not calculate numerical values.
- Never claim that retrieved records represent all matching records
  unless a verified total count is supplied.
- If the exact total is unknown, do not invent or estimate a matching count;
  describe only the retrieved products and clearly label them as retrieved results.
- Distinguish total matches from displayed records.
- Mention missing information when relevant.
- Do not describe similarity scores as probabilities.
- Do not assume a product is in stock unless inventory evidence supports it.
- Keep the answer concise and useful.

Return only the natural-language answer.
"""

    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2
        )
    )

    return {
        "status": "success",
        "answer": response.text.strip(),
        "matching_count": matching_count,
        "displayed_count": len(evidence),
        "evidence": evidence
    }
