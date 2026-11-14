
import re
import json
import uuid
import html

import ftfy
import pandas as pd
from bs4 import BeautifulSoup
from google.genai import types


MODEL_NAME = "gemini-3.5-flash-lite"


ATTRIBUTE_EXTRACTION_PROMPT = """
You are the dynamic attribute extraction engine for CatalogIQ,
a generic e-commerce catalogue intelligence system.

Extract structured attributes from the supplied product information text.

Rules:
1. Discover attribute names dynamically.
2. Extract only explicitly stated attributes and values.
3. Never infer or invent missing information.
4. Preserve the original meaning and value.
5. Exclude marketing descriptions and general notes.
6. Do not create duplicate attributes.
7. Provide exact supporting evidence for every attribute.

Return valid JSON in this format:

{
  "attributes": [
    {
      "attribute_name": "attribute name",
      "attribute_value": "attribute value",
      "evidence": "exact supporting text"
    }
  ]
}

If no attributes are found, return an empty attributes array.
"""


def clean_html_text(html_text):
    """Convert HTML content into clean, readable text."""

    if pd.isna(html_text):
        return ""

    cleaned_html = ftfy.fix_text(html.unescape(str(html_text)))
    soup = BeautifulSoup(cleaned_html, "html.parser")

    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def extract_specification_text(html_text):
    """Extract the specification section without subsequent notes."""

    if pd.isna(html_text):
        return ""

    soup = BeautifulSoup(
        ftfy.fix_text(html.unescape(str(html_text))),
        "html.parser"
    )

    paragraphs = soup.find_all("p")
    collecting = False
    specification_parts = []

    for paragraph in paragraphs:

        paragraph_text = paragraph.get_text(" ", strip=True)

        if re.search(
            r"Specification\s*:-?",
            paragraph_text,
            re.IGNORECASE
        ):
            collecting = True
            continue

        if not collecting:
            continue

        specification_parts.append(paragraph_text)

    combined_text = " ".join(specification_parts)

    combined_text = re.split(
        r"\bNotes\b",
        combined_text,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    return combined_text.strip()


def extract_attributes(client, specification_text):
    """Use Gemini to discover attributes dynamically."""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=(
            ATTRIBUTE_EXTRACTION_PROMPT
            + "\n\nProduct information text:\n"
            + specification_text
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0
        )
    )

    extraction = json.loads(response.text)

    if not isinstance(extraction, dict):
        raise ValueError("Invalid extraction response.")

    if not isinstance(extraction.get("attributes"), list):
        raise ValueError("Missing or invalid attributes array.")

    return extraction


def validate_extracted_attributes(extraction, source_text):
    """Validate extracted values and their supporting evidence."""

    errors = []
    attributes = extraction.get("attributes", [])

    for i, attribute in enumerate(attributes):

        if not isinstance(attribute, dict):
            errors.append(f"Attribute {i}: Invalid structure.")
            continue

        name = attribute.get("attribute_name")
        value = attribute.get("attribute_value")
        evidence = attribute.get("evidence")

        if not all(isinstance(x, str) for x in [name, value, evidence]):
            errors.append(f"Attribute {i}: Fields must be strings.")
            continue

        name = name.strip()
        value = value.strip()
        evidence = evidence.strip()

        if not name:
            errors.append(f"Attribute {i}: Missing name.")

        if not value:
            errors.append(f"Attribute {i}: Missing value.")

        if not evidence:
            errors.append(f"Attribute {i}: Missing evidence.")
            continue

        if evidence.casefold() not in source_text.casefold():
            errors.append(f"Attribute {i}: Evidence not found in source.")

        if value.casefold() not in evidence.casefold():
            errors.append(f"Attribute {i}: Value not supported by evidence.")

    return {
        "valid": len(errors) == 0,
        "attribute_count": len(attributes),
        "errors": errors
    }


def process_one_record(con, client, catalogue_id, source_record_id):
    """Extract, validate and store attributes for one catalogue record."""

    try:

        record = con.execute("""
            SELECT product_description
            FROM catalogue_records
            WHERE catalogue_id = ?
              AND source_record_id = ?
        """, [catalogue_id, source_record_id]).fetchone()

        if record is None:
            return {
                "record_id": source_record_id,
                "status": "failed",
                "error": "Record not found."
            }

        specification = clean_html_text(record[0])

        if not specification:
            return {
                "record_id": source_record_id,
                "status": "no_attributes",
                "attribute_count": 0
            }

        extraction = extract_attributes(client, specification)

        validation = validate_extracted_attributes(
            extraction,
            specification
        )

        if not validation["valid"]:
            return {
                "record_id": source_record_id,
                "status": "failed",
                "error": validation["errors"]
            }

        attributes = extraction["attributes"]

        if not attributes:
            return {
                "record_id": source_record_id,
                "status": "no_attributes",
                "attribute_count": 0
            }

        rows = [
            (
                str(uuid.uuid4()),
                catalogue_id,
                source_record_id,
                item["attribute_name"].strip(),
                item["attribute_value"].strip(),
                item["evidence"].strip(),
                MODEL_NAME
            )
            for item in attributes
        ]

        # Replace previous extraction only after successful validation.
        con.execute("BEGIN TRANSACTION")

        try:
            con.execute("""
                DELETE FROM catalogue_attributes
                WHERE catalogue_id = ?
                  AND source_record_id = ?
            """, [catalogue_id, source_record_id])

            con.executemany("""
                INSERT INTO catalogue_attributes (
                    attribute_id,
                    catalogue_id,
                    source_record_id,
                    attribute_name,
                    attribute_value,
                    evidence,
                    extraction_model
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, rows)

            con.execute("COMMIT")

        except Exception:
            con.execute("ROLLBACK")
            raise

        return {
            "record_id": source_record_id,
            "status": "success",
            "attribute_count": len(attributes)
        }

    except Exception as e:

        return {
            "record_id": source_record_id,
            "status": "failed",
            "error": str(e)
        }




# CATALOGIQ EVIDENCE VALIDATION RETRY UPDATE

import unicodedata
import time


def _normalise_evidence_text(value):
    """Normalize punctuation and spacing without changing word content."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def validate_extracted_attributes(extraction, source_text):
    """Validate that each extracted value is supported by source evidence."""

    errors = []
    attributes = extraction.get("attributes", [])

    if not isinstance(attributes, list):
        return {
            "valid": False,
            "attribute_count": 0,
            "errors": ["Attributes must be a list."]
        }

    normalized_source = _normalise_evidence_text(source_text)

    for i, attribute in enumerate(attributes):

        if not isinstance(attribute, dict):
            errors.append(f"Attribute {i}: Invalid structure.")
            continue

        name = attribute.get("attribute_name")
        value = attribute.get("attribute_value")
        evidence = attribute.get("evidence")

        if not all(isinstance(x, str) for x in [name, value, evidence]):
            errors.append(f"Attribute {i}: Fields must be strings.")
            continue

        name = name.strip()
        value = value.strip()
        evidence = evidence.strip()

        if not name or not value or not evidence:
            errors.append(f"Attribute {i}: Name, value and evidence are required.")
            continue

        normalized_evidence = _normalise_evidence_text(evidence)
        normalized_value = _normalise_evidence_text(value)

        if not normalized_evidence:
            errors.append(f"Attribute {i}: Empty evidence.")
            continue

        if f" {normalized_evidence} " not in f" {normalized_source} ":
            errors.append(f"Attribute {i}: Evidence not found in source.")

        if f" {normalized_value} " not in f" {normalized_evidence} ":
            errors.append(
                f"Attribute {i}: Value not supported by evidence."
            )

    return {
        "valid": len(errors) == 0,
        "attribute_count": len(attributes),
        "errors": errors
    }


# Strengthen extraction instructions without imposing a fixed schema.
ATTRIBUTE_EXTRACTION_PROMPT = ATTRIBUTE_EXTRACTION_PROMPT + """

ADDITIONAL STRICT EVIDENCE RULES:
- Copy every attribute value from the supplied product information.
- Do not convert, infer, paraphrase or calculate attribute values.
- The evidence must be a verbatim excerpt from the supplied text.
- The attribute value must appear within its evidence excerpt.
- Preserve measurements, ranges, materials and product specifications.
- If an attribute cannot be supported exactly, omit it.
- Return a valid JSON object only, with double-quoted keys and strings.
"""


def extract_attributes(client, specification_text):
    """Extract attributes with up to three validation-aware attempts."""

    last_error = None

    for attempt in range(1, 4):

        retry_context = ""

        if last_error:
            retry_context = (
                "\n\nYour previous response failed validation:\n"
                + str(last_error)
                + "\nRegenerate the complete JSON. Copy values and evidence "
                  "verbatim from the supplied product information."
            )

        prompt = (
            ATTRIBUTE_EXTRACTION_PROMPT
            + "\n\nProduct information text:\n"
            + specification_text
            + retry_context
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

            raw = (response.text or "").strip()

            if not raw:
                raise ValueError("Gemini returned an empty response.")

            extraction = json.loads(raw)

            if not isinstance(extraction, dict):
                raise ValueError("Response must be a JSON object.")

            if not isinstance(extraction.get("attributes"), list):
                raise ValueError("Missing or invalid attributes array.")

            validation = validate_extracted_attributes(
                extraction,
                specification_text
            )

            if validation["valid"]:
                return extraction

            last_error = validation["errors"]

        except Exception as error:
            last_error = str(error)

        if attempt < 3:
            print(
                f"Extraction attempt {attempt} failed validation. "
                f"Retrying..."
            )
            time.sleep(2 * attempt)

    raise ValueError(
        f"Extraction failed after 3 attempts: {last_error}"
    )
