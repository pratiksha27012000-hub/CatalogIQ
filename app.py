import os
import sys
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
DB_PATH = BASE_DIR / "catalogiq.duckdb"

CATALOGUE_ID = "cat_6bba60c7"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Initialize the Gemini client from Space Secrets
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Add it under "
        "Hugging Face Space Settings > Secrets."
    )

from google import genai
client = genai.Client(api_key=API_KEY)

# Connect to the isolated deployment database
from database import (
    connect_database,
    initialize_database,
    get_catalogue_records
)

con = connect_database(str(DB_PATH))
initialize_database(con)

catalogue = con.execute("""
    SELECT catalogue_name, record_count
    FROM catalogue_registry
    WHERE catalogue_id = ?
      AND status = 'active'
""", [CATALOGUE_ID]).fetchone()

if catalogue is None:
    raise RuntimeError("The deployment catalogue is missing or inactive.")

actual_products = con.execute("""
    SELECT COUNT(*)
    FROM catalogue_records
    WHERE catalogue_id = ?
""", [CATALOGUE_ID]).fetchone()[0]

actual_attributes = con.execute("""
    SELECT COUNT(*)
    FROM catalogue_attributes
    WHERE catalogue_id = ?
""", [CATALOGUE_ID]).fetchone()[0]

if actual_products != 40 or actual_attributes != 315:
    raise RuntimeError(
        f"Deployment data verification failed: "
        f"{actual_products} products, {actual_attributes} attributes."
    )

print(
    f"Loaded {catalogue[0]}: "
    f"{actual_products} products, {actual_attributes} attributes."
)

# Load semantic model and build the catalogue index
from semantic_search import SemanticSearchManager

semantic_manager = SemanticSearchManager()
semantic_manager.load_model()

records_df = get_catalogue_records(con, CATALOGUE_ID)

index_result = semantic_manager.build_index(
    catalogue_id=CATALOGUE_ID,
    records_df=records_df
)

if index_result["status"] != "success":
    raise RuntimeError(f"FAISS index build failed: {index_result}")

print("Semantic index:", index_result)

# Initialize the latest CatalogIQ engine
from catalogiq_engine import CatalogIQ

catalogiq_app = CatalogIQ(
    con=con,
    client=client,
    semantic_manager=semantic_manager
)

src_path = SRC_DIR
CATALOGIQ_DASHBOARD_DEFAULT_ID = CATALOGUE_ID

# Execute the original three-panel dashboard
dashboard_file = BASE_DIR / "catalogiq_simple_dashboard.py"

dashboard_source = dashboard_file.read_text(encoding="utf-8")

exec(
    compile(
        dashboard_source,
        str(dashboard_file),
        "exec"
    ),
    globals()
)
