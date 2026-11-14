
import json
import time
import uuid
import re
from pathlib import Path

import pandas as pd
import attribute_extractor as ae


TRANSIENT_ERRORS = (
    "503", "429", "500", "502", "504",
    "UNAVAILABLE", "RESOURCE_EXHAUSTED",
    "DEADLINE_EXCEEDED", "INTERNAL",
    "TIMEOUT", "TIMED OUT",
    "CONNECTION RESET", "TEMPORARY"
)


def _is_missing(value):
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_value(value):
    if _is_missing(value):
        return ""

    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)

    return ae.clean_html_text(str(value))


def build_product_information_text(
    title,
    description,
    source_record_json=None,
    max_chars=24000
):
    """
    Build a catalogue-independent evidence source from canonical
    product fields and additional original source fields.
    """

    sections = []

    cleaned_title = _clean_value(title)
    cleaned_description = _clean_value(description)

    if cleaned_title:
        sections.append(
            "Product title:\n" + cleaned_title
        )

    if cleaned_description:
        sections.append(
            "Product description:\n" + cleaned_description
        )

    # Read original source fields where available.
    source_data = {}

    try:
        if isinstance(source_record_json, str):
            source_data = json.loads(source_record_json)
        elif isinstance(source_record_json, dict):
            source_data = source_record_json
    except (json.JSONDecodeError, TypeError):
        source_data = {}

    if isinstance(source_data, dict):

        additional_fields = []

        excluded_keys = {
            "title",
            "producttitle",
            "bodyhtml",
            "body",
            "description",
            "productdescription"
        }

        for key, value in source_data.items():

            normalized_key = re.sub(
                r"[^a-z0-9]",
                "",
                str(key).casefold()
            )

            if normalized_key in excluded_keys:
                continue

            cleaned_value = _clean_value(value)

            if not cleaned_value:
                continue

            additional_fields.append(
                f"{key}: {cleaned_value}"
            )

        if additional_fields:
            sections.append(
                "Additional original catalogue fields:\n"
                + "\n".join(additional_fields)
            )

    text = "\n\n".join(sections).strip()

    return text[:max_chars]


def is_transient_error(error):
    error_text = str(error).upper()
    return any(
        signal in error_text
        for signal in TRANSIENT_ERRORS
    )


def process_one_product(
    con,
    client,
    catalogue_id,
    source_record_id,
    skip_existing=True
):
    """
    Extract attributes for one product and save only after
    successful evidence validation.
    """

    try:

        record = con.execute("""
            SELECT
                product_title,
                product_description,
                source_record_json
            FROM catalogue_records
            WHERE catalogue_id = ?
              AND source_record_id = ?
        """, [
            catalogue_id,
            source_record_id
        ]).fetchone()

        if record is None:
            return {
                "record_id": source_record_id,
                "status": "failed",
                "error": "Product record not found."
            }

        existing_count = con.execute("""
            SELECT COUNT(*)
            FROM catalogue_attributes
            WHERE catalogue_id = ?
              AND source_record_id = ?
        """, [
            catalogue_id,
            source_record_id
        ]).fetchone()[0]

        if skip_existing and existing_count > 0:
            return {
                "record_id": source_record_id,
                "status": "skipped_existing",
                "attribute_count": existing_count
            }

        product_text = build_product_information_text(
            title=record[0],
            description=record[1],
            source_record_json=record[2]
        )

        if not product_text:
            return {
                "record_id": source_record_id,
                "status": "no_attributes",
                "attribute_count": 0
            }

        # Dynamic Gemini extraction.
        extraction = ae.extract_attributes(
            client,
            product_text
        )

        # Validate every value against its evidence.
        validation = ae.validate_extracted_attributes(
            extraction,
            product_text
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

        model_name = getattr(
            ae,
            "MODEL_NAME",
            "unknown"
        )

        rows = []

        for item in attributes:
            rows.append((
                str(uuid.uuid4()),
                catalogue_id,
                source_record_id,
                item["attribute_name"].strip(),
                item["attribute_value"].strip(),
                item["evidence"].strip(),
                model_name
            ))

        # Commit only after complete validation.
        con.execute("BEGIN TRANSACTION")

        try:

            con.execute("""
                DELETE FROM catalogue_attributes
                WHERE catalogue_id = ?
                  AND source_record_id = ?
            """, [
                catalogue_id,
                source_record_id
            ])

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
            "attribute_count": len(rows)
        }

    except Exception as error:

        return {
            "record_id": source_record_id,
            "status": "failed",
            "error": str(error)
        }


def enrich_catalogue(
    con,
    client,
    catalogue_id,
    output_dir,
    max_attempts=5,
    pause_seconds=1.5,
    retry_no_attributes=False,
    max_products=None
):
    """
    Resumable catalogue-wide enrichment.

    Database records are the source of truth.
    CSV checkpoint preserves progress and failed attempts.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        catalogue_id
    )

    checkpoint_path = (
        output_dir /
        f"attribute_enrichment_{safe_id}.csv"
    )

    checkpoint = {}

    # Load previous progress.
    if checkpoint_path.exists():

        previous = pd.read_csv(checkpoint_path)

        for _, row in previous.iterrows():

            checkpoint[str(row["record_id"])] = {
                "record_id": str(row["record_id"]),
                "status": str(row["status"]),
                "attribute_count": row.get(
                    "attribute_count", 0
                ),
                "attempts": row.get("attempts", 0),
                "error": row.get("error", ""),
                "updated_at": row.get("updated_at", "")
            }

    # Retrieve all product IDs for this catalogue.
    all_ids = con.execute("""
        SELECT source_record_id
        FROM catalogue_records
        WHERE catalogue_id = ?
        ORDER BY source_record_id
    """, [catalogue_id]).fetchall()

    run_results = []

    def save_checkpoint():

        frame = pd.DataFrame(
            list(checkpoint.values())
        )

        if not frame.empty:
            frame = frame.sort_values("record_id")

        temp_path = checkpoint_path.with_suffix(".tmp")

        frame.to_csv(temp_path, index=False)
        temp_path.replace(checkpoint_path)

    # Process each product not already enriched.
    for row in all_ids:

        record_id = str(row[0])

        existing = con.execute("""
            SELECT COUNT(*)
            FROM catalogue_attributes
            WHERE catalogue_id = ?
              AND source_record_id = ?
        """, [
            catalogue_id,
            record_id
        ]).fetchone()[0]

        # Database is authoritative: never overwrite successes.
        if existing > 0:
            continue

        previous_status = checkpoint.get(
            record_id,
            {}
        ).get("status")

        # Do not repeatedly retry a legitimate empty result
        # unless explicitly requested.
        if (
            previous_status == "no_attributes"
            and not retry_no_attributes
        ):
            continue

        if max_products is not None:
            if len(run_results) >= max_products:
                break

        print(
            f"\n[{len(run_results) + 1}] "
            f"Processing {record_id}"
        )

        final_result = None
        attempts_used = 0

        for attempt in range(1, max_attempts + 1):

            attempts_used = attempt

            final_result = process_one_product(
                con=con,
                client=client,
                catalogue_id=catalogue_id,
                source_record_id=record_id,
                skip_existing=True
            )

            if final_result["status"] != "failed":
                break

            error = final_result.get("error", "")

            if (
                not is_transient_error(error)
                or attempt == max_attempts
            ):
                break

            wait_time = min(
                60,
                5 * (2 ** (attempt - 1))
            )

            print(
                f"Temporary API error. "
                f"Retrying in {wait_time}s."
            )

            time.sleep(wait_time)

        result_row = {
            "record_id": record_id,
            "status": final_result["status"],
            "attribute_count": final_result.get(
                "attribute_count", 0
            ),
            "attempts": attempts_used,
            "error": final_result.get("error", ""),
            "updated_at": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        checkpoint[record_id] = result_row
        run_results.append(result_row)

        # Persist after each product.
        save_checkpoint()

        print(
            result_row["status"],
            "| Attributes:",
            result_row["attribute_count"],
            "| Attempts:",
            attempts_used
        )

        if pause_seconds > 0:
            time.sleep(pause_seconds)

    # Final save.
    save_checkpoint()

    # Final database coverage report.
    enriched_count, attribute_count = con.execute("""
        SELECT
            COUNT(DISTINCT source_record_id),
            COUNT(*)
        FROM catalogue_attributes
        WHERE catalogue_id = ?
    """, [catalogue_id]).fetchone()

    total_products = len(all_ids)

    run_df = pd.DataFrame(run_results)

    if run_df.empty:
        status_counts = {}
        run_attribute_count = 0
    else:
        status_counts = (
            run_df["status"].value_counts().to_dict()
        )

        run_attribute_count = int(
            pd.to_numeric(
                run_df["attribute_count"],
                errors="coerce"
            ).fillna(0).sum()
        )

    report = {
        "catalogue_id": catalogue_id,
        "total_products": total_products,
        "processed_this_run": len(run_results),
        "run_status_counts": status_counts,
        "attributes_added_this_run": run_attribute_count,
        "enriched_products_total": enriched_count,
        "attributes_total": attribute_count,
        "attribute_coverage_percent": round(
            enriched_count / total_products * 100,
            2
        ) if total_products else 0,
        "products_without_attributes": (
            total_products - enriched_count
        ),
        "checkpoint_path": str(checkpoint_path)
    }

    return report
