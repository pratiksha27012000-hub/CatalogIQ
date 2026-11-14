import re
import numpy as np
import pandas as pd
import faiss
import ftfy

from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer


class SemanticSearchManager:

    def __init__(
        self,
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    ):
        self.model_name = model_name
        self.model = None

        # Separate index and records for each catalogue
        self.catalogue_indexes = {}

    # --------------------------------------------------
    # 1. MODEL LOADING
    # --------------------------------------------------

    def load_model(self):

        if self.model is None:
            self.model = SentenceTransformer(self.model_name)

        return self.model

    # --------------------------------------------------
    # 2. TEXT CLEANING
    # --------------------------------------------------

    def clean_text(self, text):

        if pd.isna(text):
            return ""

        text = ftfy.fix_text(str(text))

        soup = BeautifulSoup(text, "html.parser")

        text = soup.get_text(" ", strip=True)

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # --------------------------------------------------
    # 3. BUILD FAISS INDEX
    # --------------------------------------------------

    def build_index(self, catalogue_id, records_df):

        required_columns = {
            "source_record_id",
            "product_title",
            "product_description"
        }

        missing_columns = required_columns - set(records_df.columns)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        if records_df.empty:
            raise ValueError("Cannot build an index from empty records.")

        semantic_df = records_df[
            [
                "source_record_id",
                "product_title",
                "product_description"
            ]
        ].copy()

        semantic_df["clean_description"] = (
            semantic_df["product_description"]
            .apply(self.clean_text)
        )

        semantic_df["search_text"] = (
            semantic_df["product_title"].fillna("").astype(str)
            + " "
            + semantic_df["clean_description"]
        ).str.strip()

        # Remove records without searchable content
        semantic_df = semantic_df[
            semantic_df["search_text"] != ""
        ].reset_index(drop=True)

        if semantic_df.empty:
            raise ValueError("No searchable product content found.")

        model = self.load_model()

        embeddings = model.encode(
            semantic_df["search_text"].tolist(),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        dimension = embeddings.shape[1]

        # Inner product on normalized embeddings = cosine similarity
        index = faiss.IndexFlatIP(dimension)

        index.add(embeddings)

        self.catalogue_indexes[catalogue_id] = {
            "index": index,
            "records": semantic_df,
            "record_embeddings": embeddings
        }

        return {
            "status": "success",
            "catalogue_id": catalogue_id,
            "indexed_records": len(semantic_df),
            "embedding_dimension": dimension
        }

    # --------------------------------------------------
    # 4. SEMANTIC SEARCH
    # --------------------------------------------------

    def search(
        self,
        catalogue_id,
        query,
        top_k=5,
        retrieval_mode="standard"
    ):

        if catalogue_id not in self.catalogue_indexes:
            raise ValueError(
                "No semantic index found for this catalogue. "
                "Build the index first."
            )

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        if retrieval_mode != "standard":
            raise ValueError(
                "This version supports only standard retrieval."
            )

        catalogue_data = self.catalogue_indexes[catalogue_id]

        index = catalogue_data["index"]
        semantic_df = catalogue_data["records"]

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        search_k = min(top_k, index.ntotal)

        scores, indices = index.search(
            query_embedding,
            search_k
        )

        results = semantic_df.iloc[indices[0]].copy()

        results["similarity_score"] = scores[0]

        return results[
            [
                "source_record_id",
                "product_title",
                "clean_description",
                "similarity_score"
            ]
        ].reset_index(drop=True)

    # --------------------------------------------------
    # 5. ENRICH SEMANTIC RESULTS FROM DUCKDB
    # --------------------------------------------------

    def enrich_results(self, con, catalogue_id, results):
        """
        Retrieve authoritative catalogue fields from DuckDB.

        Preserves semantic ranking and similarity scores.
        Supports standard and diversified-style result IDs.
        """

        if results.empty:
            return results.copy()

        # Standard retrieval: one product per row
        if "source_record_id" in results.columns:

            expanded = results.copy()

        # Grouped retrieval: multiple products per row
        elif "source_record_ids" in results.columns:

            rows = []

            for _, row in results.iterrows():

                for record_id in row["source_record_ids"]:

                    rows.append({
                        "source_record_id": record_id,
                        "product_title": row.get("product_titles"),
                        "clean_description": row.get("clean_description"),
                        "similarity_score": row.get("similarity_score")
                    })

            expanded = pd.DataFrame(rows)

        else:
            raise ValueError(
                "Semantic results must contain source_record_id "
                "or source_record_ids."
            )

        if expanded.empty:
            return expanded

        record_ids = (
            expanded["source_record_id"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if not record_ids:
            return expanded

        placeholders = ", ".join(["?"] * len(record_ids))

        query = f"""
            SELECT
                source_record_id,
                product_title AS catalogue_product_title,
                product_description,
                selling_price,
                cost_price,
                inventory_quantity
            FROM catalogue_records
            WHERE catalogue_id = ?
              AND source_record_id IN ({placeholders})
        """

        catalogue_data = con.execute(
            query,
            [catalogue_id] + record_ids
        ).fetchdf()

        enriched = expanded.merge(
            catalogue_data,
            on="source_record_id",
            how="left",
            sort=False
        )

        # Prefer the authoritative title stored in DuckDB
        if "catalogue_product_title" in enriched.columns:

            enriched["product_title"] = (
                enriched["catalogue_product_title"]
                .combine_first(enriched["product_title"])
            )

            enriched = enriched.drop(
                columns=["catalogue_product_title"]
            )

        return enriched.reset_index(drop=True)

    # --------------------------------------------------
    # 6. REMOVE CATALOGUE INDEX
    # --------------------------------------------------

    def remove_index(self, catalogue_id):

        if catalogue_id in self.catalogue_indexes:

            del self.catalogue_indexes[catalogue_id]

            return True

        return False
