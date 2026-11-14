

from query_interpreter import ask_catalogiq

from hybrid_retriever import (
    route_query,
    extract_hybrid_filters,
    validate_extracted_filters,
    execute_hybrid_search
)

from answer_generator import generate_answer
from catalogue_intelligence import (
    direct_product_answer,
    direct_zero_stock_answer,
    direct_attribute_answer,
    filter_by_category,
    has_explicit_match_condition,
    add_category_column,
)


class CatalogIQ:

    def __init__(self, con, client, semantic_manager):

        self.con = con
        self.client = client
        self.semantic_manager = semantic_manager


    def ask(self, catalogue_id, question, top_k=5):

        try:

            if not isinstance(question, str) or not question.strip():
                return {"status": "error", "errors": ["Question cannot be empty."]}

            # Deterministic catalogue lookups run before LLM routing. These
            # answer exact product-family and explicit attribute questions
            # using source-of-truth DuckDB records.
            for resolver in (
                direct_product_answer,
                direct_zero_stock_answer,
                direct_attribute_answer,
            ):
                direct_result = resolver(
                    self.con, catalogue_id, question, top_k
                )
                if direct_result is not None:
                    return direct_result

            # STEP 1: UNDERSTAND THE USER QUERY

            routing = route_query(
                self.client,
                question
            )

            if routing["status"] != "success":
                return routing

            retrieval_mode = routing["retrieval_mode"]

            filters = []
            semantic_query = routing.get("semantic_query")


            # STEP 2: STRUCTURED RETRIEVAL

            if retrieval_mode == "structured":

                output = ask_catalogiq(
                    self.con,
                    self.client,
                    catalogue_id,
                    question
                )

                if output["status"] != "success":
                    return output

                result = output["result"]

                if result["status"] != "success":
                    return result

                # Return numerical answers directly

                if "records" not in result:

                    return {
                        "status": "success",
                        "retrieval_mode": "structured",
                        "question": question,
                        "answer": result["answer"],
                        "matching_records": result.get(
                            "matching_records"
                        ),
                        "metric": result.get("metric"),
                        "target_field": result.get("target_field")
                    }

                retrieval_result = {
                    "status": "success",
                    "results": result["records"],
                    "matching_count": result["matching_records"]
                }


            # STEP 3: SEMANTIC RETRIEVAL


            elif retrieval_mode == "semantic":

                from hybrid_retriever import detect_availability_intent
                import pandas as pd

                availability_intent = detect_availability_intent(
                    question
                )

                # Search the complete semantic candidate set.
                index_data = self.semantic_manager.catalogue_indexes.get(
                    catalogue_id
                )

                if index_data is None:
                    return {
                        "status": "error",
                        "errors": [
                            "Semantic index not found for this catalogue."
                        ]
                    }

                search_k = index_data["index"].ntotal

                if search_k == 0:
                    return {
                        "status": "success",
                        "retrieval_mode": "semantic",
                        "question": question,
                        "answer": "No catalogue products were indexed.",
                        "matching_records": 0,
                        "displayed_records": 0,
                        "records": []
                    }

                results = self.semantic_manager.search(
                    catalogue_id=catalogue_id,
                    query=semantic_query,
                    top_k=search_k,
                    retrieval_mode="standard"
                )

                if results is None or results.empty:
                    return {
                        "status": "success",
                        "retrieval_mode": "semantic",
                        "question": question,
                        "answer": "No relevant records were retrieved. The exact total number of matching products could not be verified.",
                        "matching_records": None,
                        "displayed_records": 0,
                        "records": []
                    }

                # Enrich with authoritative DuckDB product information.
                results = self.semantic_manager.enrich_results(
                    con=self.con,
                    catalogue_id=catalogue_id,
                    results=results
                )

                if "inventory_quantity" not in results.columns:
                    return {
                        "status": "error",
                        "stage": "availability_filter",
                        "errors": [
                            "Inventory information is missing from semantic results."
                        ]
                    }

                inventory = pd.to_numeric(
                    results["inventory_quantity"],
                    errors="coerce"
                )

                if availability_intent == "out_of_stock":

                    results = results[inventory == 0].copy()

                    filters = [{
                        "type": "record",
                        "field": "inventory_quantity",
                        "operator": "equals",
                        "value": 0
                    }]

                    empty_message = (
                        "No out-of-stock products matched your query."
                    )

                else:

                    # Default policy: unknown and zero inventory
                    # are not treated as available.
                    results = results[inventory > 0].copy()

                    filters = [{
                        "type": "record",
                        "field": "inventory_quantity",
                        "operator": "greater_than",
                        "value": 0
                    }]

                    empty_message = (
                        "No in-stock products matched your query."
                    )

                results = results.sort_values(
                    "similarity_score",
                    ascending=False
                ).reset_index(drop=True)

                # Semantic similarity alone does not prove an exact match.
                # Keep the displayed shortlist, but do not report its size as
                # the total number of catalogue matches.
                matching_count = None

                # Apply top_k after availability filtering.
                results = results.head(top_k).copy()

                if results.empty:
                    return {
                        "status": "success",
                        "retrieval_mode": "semantic",
                        "question": question,
                        "answer": empty_message + " The exact total number of matching products could not be verified from semantic retrieval alone.",
                        "matching_records": None,
                        "displayed_records": 0,
                        "records": [],
                        "filters": filters
                    }

                retrieval_result = {
                    "status": "success",
                    "results": results,
                    "matching_count": matching_count
                }


            elif retrieval_mode == "hybrid":

                filter_output = extract_hybrid_filters(
                    self.client,
                    question,
                    con=self.con,
                    catalogue_id=catalogue_id
                )

                if filter_output["status"] != "success":
                    return filter_output

                filters = filter_output["filters"]
                explicit_filters = list(filters)

                validation = validate_extracted_filters(
                    filters,
                    con=self.con,
                    catalogue_id=catalogue_id
                )

                if not validation["valid"]:

                    return {
                        "status": "error",
                        "stage": "filter_validation",
                        "errors": validation["errors"]
                    }


                from hybrid_retriever import detect_availability_intent

                availability_intent = detect_availability_intent(
                    question
                )

                # Respect an explicitly extracted inventory condition.
                has_inventory_filter = any(
                    item.get("type") in (None, "record")
                    and item.get("field") == "inventory_quantity"
                    for item in filters
                )

                # Otherwise apply the customer availability intent,
                # or default to in-stock products.
                if not has_inventory_filter:

                    if availability_intent == "out_of_stock":
                        inventory_operator = "equals"
                        inventory_value = 0
                    else:
                        inventory_operator = "greater_than"
                        inventory_value = 0

                    filters.append({
                        "type": "record",
                        "field": "inventory_quantity",
                        "operator": inventory_operator,
                        "value": inventory_value
                    })

                # Validate again after adding the default condition.
                validation = validate_extracted_filters(
                    filters,
                    con=self.con,
                    catalogue_id=catalogue_id
                )

                if not validation["valid"]:
                    return {
                        "status": "error",
                        "stage": "availability_filter_validation",
                        "errors": validation["errors"]
                    }

                hybrid_output = execute_hybrid_search(
                    con=self.con,
                    semantic_manager=self.semantic_manager,
                    catalogue_id=catalogue_id,
                    semantic_query=semantic_query,
                    filters=filters,
                    # Category filtering and verified counting must happen
                    # before display truncation.
                    top_k=None
                )

                if hybrid_output["status"] != "success":
                    return hybrid_output

                hybrid_results = hybrid_output.get("results")
                if hybrid_results is None:
                    return {
                        "status": "error",
                        "stage": "hybrid_retrieval",
                        "errors": ["Hybrid retrieval returned no result table."]
                    }

                hybrid_results = add_category_column(hybrid_results)
                hybrid_results, resolved_category = filter_by_category(
                    hybrid_results, question
                )

                exact_count_is_supported = has_explicit_match_condition(
                    explicit_filters,
                    question,
                    category_resolved=resolved_category is not None
                )
                verified_matching_count = (
                    int(len(hybrid_results)) if exact_count_is_supported else None
                )
                displayed_results = hybrid_results.head(top_k).copy()

                retrieval_result = {
                    "status": "success",
                    "results": displayed_results.reset_index(drop=True),
                    "matching_count": verified_matching_count
                }


            else:

                return {
                    "status": "error",
                    "errors": [
                        f"Unsupported retrieval mode: {retrieval_mode}"
                    ]
                }


            # STEP 5: GENERATE A GROUNDED NATURAL-LANGUAGE ANSWER

            answer_output = generate_answer(
                client=self.client,
                question=question,
                retrieval_result=retrieval_result,
                retrieval_mode=retrieval_mode
            )

            if answer_output["status"] != "success":
                return answer_output


            # STEP 7: RETURN FINAL RESPONSE

            return {
                "status": "success",
                "retrieval_mode": retrieval_mode,
                "question": question,
                "answer": answer_output["answer"],
                "matching_records": answer_output.get(
                    "matching_count"
                ),
                "displayed_records": answer_output["displayed_count"],
                "records": answer_output["evidence"],
                "semantic_query": semantic_query,
                "filters": filters
            }


        except Exception as e:

            return {
                "status": "error",
                "stage": "catalogiq_engine",
                "errors": [str(e)]
            }

