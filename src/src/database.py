
import os
import duckdb


def connect_database(db_path):
    """Connect to the persistent CatalogIQ database."""

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return duckdb.connect(db_path)


def initialize_database(con):
    """Create CatalogIQ tables if they do not already exist."""

    con.execute("""
        CREATE TABLE IF NOT EXISTS catalogue_registry (
            catalogue_id VARCHAR PRIMARY KEY,
            catalogue_name VARCHAR,
            source_file VARCHAR,
            record_count INTEGER,
            created_at TIMESTAMP,
            status VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS catalogue_records (
            catalogue_id VARCHAR,
            source_record_id VARCHAR,
            product_title VARCHAR,
            product_description VARCHAR,
            selling_price DOUBLE,
            cost_price DOUBLE,
            inventory_quantity DOUBLE,
            source_record_json JSON,
            PRIMARY KEY (catalogue_id, source_record_id)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS catalogue_attributes (
            attribute_id VARCHAR PRIMARY KEY,
            catalogue_id VARCHAR NOT NULL,
            source_record_id VARCHAR NOT NULL,
            attribute_name VARCHAR NOT NULL,
            attribute_value VARCHAR NOT NULL,
            evidence VARCHAR NOT NULL,
            extraction_model VARCHAR,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Keep the normalized attribute view available after a fresh DB/runtime
    # initialization. Hybrid retrieval and direct attribute lookup both use it.
    con.execute("""
        CREATE OR REPLACE VIEW catalogue_attributes_live AS
        SELECT
            attribute_id,
            catalogue_id,
            source_record_id,
            trim(both '_' from regexp_replace(
                lower(attribute_name), '[^a-z0-9]+', '_', 'g'
            )) AS canonical_attribute_name,
            attribute_name,
            attribute_value,
            evidence,
            extraction_model,
            extracted_at
        FROM catalogue_attributes
    """)

    return True


def get_active_catalogues(con):
    """Return all active catalogues."""

    return con.execute("""
        SELECT *
        FROM catalogue_registry
        WHERE status = 'active'
        ORDER BY created_at DESC
    """).df()


def get_catalogue_records(con, catalogue_id):
    """Retrieve all records belonging to a catalogue."""

    return con.execute("""
        SELECT *
        FROM catalogue_records
        WHERE catalogue_id = ?
    """, [catalogue_id]).df()


def get_catalogue_attributes(con, catalogue_id, source_record_id=None):
    """Retrieve dynamic attributes for a catalogue or a specific record."""

    if source_record_id is not None:
        return con.execute("""
            SELECT *
            FROM catalogue_attributes
            WHERE catalogue_id = ?
              AND source_record_id = ?
        """, [catalogue_id, source_record_id]).df()

    return con.execute("""
        SELECT *
        FROM catalogue_attributes
        WHERE catalogue_id = ?
    """, [catalogue_id]).df()
