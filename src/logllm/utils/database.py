from abc import ABC, abstractmethod
from typing import (  # Add necessary types
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
)

import requests
from elasticsearch import Elasticsearch, helpers
from langchain_elasticsearch import ElasticsearchStore

from ..config import config as cfg
from .logger import Logger


class Database(ABC):
    @abstractmethod
    def insert(self, data: dict, identifier: str = None):
        """Insert data into the database. Identifier may specify a collection or index."""
        pass

    @abstractmethod
    def single_search(self, query: dict, identifier: str = None):
        """Search for data in the database. Identifier may specify a collection or index."""
        pass

    @abstractmethod
    def update(self, id, data: dict, identifier: str = None):
        """Update existing data in the database."""
        pass

    @abstractmethod
    def delete(self, id: id, identifier: str = None):
        """Delete data from the database."""
        pass

    @abstractmethod
    def set_vector_store(self, embeddings, index):
        """Set the vector store for the database."""
        pass


class ElasticsearchDatabase(Database):
    """
    provide some simple interface for common operations,
    but user can still access elasticsearch api via self.instance directly
    """

    def __init__(self):
        self._logger = Logger()
        self.instance = self._connect()
        self.vector_store = None

    def insert(self, data: dict, index: str):
        if self.instance is None:
            self._logger.error(
                "Elasticsearch instance not initialized, please check if container is running"
            )
            print("please check if Container is running")

        self.instance.index(index=index, body=data)

    def single_search(self, query: dict, index: str):
        """
        return single search result
        """
        query["size"] = 1
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized")
            print("please check if Container is running")
            exit(1)

        result = self.instance.search(index=index, body=query)
        return result["hits"]["hits"]

    def scroll_search(self, query: dict, index: str):
        """
        Return all search results using the Scroll API.

        Args:
            query (dict): The Elasticsearch query body. This body SHOULD contain
                          the desired 'size' for the initial batch.
            index (str): The index to search in.

        Returns:
            list: A list of all matching documents (response["hits"]["hits"]).
        """
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized")
            print("please check if Container is running")
            return []  # Return empty list on error

        all_hits = []
        scroll_id = None  # Initialize scroll_id

        try:
            # Initial search with scroll
            # The 'query' dict should already contain 'size' if specified by the caller.
            # If not, Elasticsearch defaults (usually 10).
            # We ensure scroll parameter is present.
            self._logger.debug(
                f"Initial scroll search query for index '{index}': {query}"
            )
            resp = self.instance.search(
                index=index,
                body=query,  # Pass the query body as is
                scroll="5m",  # Keep scroll context alive
                # DO NOT specify 'size' here if it's in the 'query' body
            )
            scroll_id = resp.get("_scroll_id")
            hits = resp["hits"]["hits"]
            all_hits.extend(hits)
            self._logger.debug(
                f"Initial scroll fetch: {len(hits)} hits. Scroll ID: {scroll_id}"
            )

            # Continue scrolling until no more results or scroll_id is missing
            while scroll_id and len(hits) > 0:
                self._logger.debug(f"Continuing scroll with ID: {scroll_id}")
                resp = self.instance.scroll(scroll_id=scroll_id, scroll="5m")
                scroll_id = resp.get(
                    "_scroll_id"
                )  # Update scroll_id for the next iteration
                hits = resp["hits"]["hits"]
                all_hits.extend(hits)
                self._logger.debug(f"Next scroll batch: {len(hits)} hits.")

        except Exception as e:
            self._logger.error(
                f"Error during scroll search on index '{index}': {e}", exc_info=True
            )
            # Optionally re-raise or return partial results
            # Current behavior returns what was gathered so far
        finally:  # Ensure clear_scroll is attempted
            if scroll_id:
                try:
                    self.instance.clear_scroll(scroll_id=scroll_id)
                    self._logger.debug(f"Scroll context {scroll_id} cleared.")
                except Exception as clear_err:
                    self._logger.warning(
                        f"Failed to clear scroll context {scroll_id}: {clear_err}"
                    )

        self._logger.info(
            f"Scroll search completed for index '{index}'. Total hits retrieved: {len(all_hits)}"
        )
        return all_hits

    def update(
        self,
        id: str,
        data: dict,
        index: str,
    ):
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized")
            print("please check if Container is running")
            exit(1)

        self.instance.update(index=index, body=data, id=id)

    def delete(self, id: str, index: str):
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized")
            print("please check if Container is running")
            exit(1)

        self.instance.delete(index=index, id=id)

    def _connect(self) -> Elasticsearch | None:
        es_url = cfg.ELASTIC_SEARCH_URL
        try:
            requests.get(es_url)
            instance = Elasticsearch([es_url])
            self._logger.info("Connected to Elasticsearch")
            return instance
        except requests.exceptions.ConnectionError as e:
            self._logger.error(f"Error connecting to Elasticsearch: {e}")
            print("please check if Container is running")
            return None

    def set_vector_store(self, embeddings, index) -> ElasticsearchStore:
        try:
            vector_store = ElasticsearchStore(
                es_url=cfg.ELASTIC_SEARCH_URL,
                index_name=index,
                embedding=embeddings,
            )
            return vector_store
        except Exception as e:
            self._logger.error(f"Error setting vector store: {e}")
            exit(1)

    def random_sample(self, index: str, size: int):
        """
        return random sample of all field and size from index
        the maximum size is 10000
        """
        query = {
            "size": size,
            "query": {
                "function_score": {"query": {"match_all": {}}, "random_score": {}}
            },
        }
        try:
            return self.instance.search(index=index, body=query)["hits"]["hits"]
        except Exception as e:
            self._logger.error(f"Error fetching random sample from index {index}: {e}")
            exit(1)

    def add_alias(self, index: str, alias: str, filter: dict = None):
        """
        Add an alias to an index and return the count of documents matching the filter.

        Args:
            index: The index to alias.
            alias: The name of the alias.
            filter: Optional filter to apply to the alias (dict).

        Returns:
            'count' (number of matching documents).
        """
        # Step 1: Get the count of documents matching the filter
        try:
            count_res = self.instance.count(
                index=index, body={"query": filter} if filter else None
            )
            count = count_res["count"]
        except Exception as e:
            self._logger.error(
                f"Error counting documents for index {index} with filter {filter}: {e}"
            )
            exit(1)

        # Step 2: Create the alias
        query = {
            "actions": [{"add": {"index": index, "alias": alias, "filter": filter}}]
        }
        try:
            res = self.instance.indices.update_aliases(body=query)
            return count
        except Exception as e:
            self._logger.error(f"Error adding alias {alias} to index {index}: {e}")
            exit(1)

    def count_docs(self, index: str, filter: dict = None):
        resp = self.instance.count(
            index=index, body={"query": filter} if filter else None
        )

        count = resp["count"]
        return count

    def get_unique_values_composite(
        self, index: str, field: str, page_size=1000, sort_order="asc"
    ):
        """
        Retrieves unique values from a field in Elasticsearch using the composite aggregation.
        Returns all unique values in the field.

        Args:
            es_client (Elasticsearch): Elasticsearch client instance.
            index_name (str): Name of the Elasticsearch index.
            field_name (str): Name of the field to get unique values from.
            page_size (int): The number of terms to return per page.

        Returns:
            list: A list of unique values.
        """
        unique_values = []
        after_key = None

        try:
            while True:
                query = {
                    "size": 0,
                    "aggs": {
                        "unique_values": {
                            "composite": {
                                "sources": [
                                    {
                                        field: {
                                            "terms": {
                                                "field": field,
                                                "order": sort_order,
                                            },
                                        }
                                    }
                                ],
                                "size": page_size,
                            }
                        }
                    },
                }

                if after_key:
                    query["aggs"]["unique_values"]["composite"]["after"] = after_key

                response = self.instance.search(index=index, body=query)

                buckets = response["aggregations"]["unique_values"]["buckets"]
                unique_values.extend([bucket["key"][field] for bucket in buckets])

                if "after_key" in response["aggregations"]["unique_values"]:
                    after_key = response["aggregations"]["unique_values"]["after_key"]
                else:
                    break

            return unique_values

        except Exception as e:
            print(f"Error retrieving unique values: {e}")
            return []

    def get_unique_values(self, index: str, field: str, size=1000, sort_order="asc"):
        """
        Retrieves unique values from a field in Elasticsearch using the terms aggregation.

        Args:
            es_client (Elasticsearch): Elasticsearch client instance.
            index_name (str): Name of the Elasticsearch index.
            field_name (str): Name of the field to get unique values from.
            size (int): The maximum number of terms to return. range: 1-10000

        Returns:
            list: A list of unique values.
        """
        try:
            response = self.instance.search(
                index=index,
                size=0,
                aggs={
                    "unique_values": {
                        "terms": {
                            "field": field,
                            "size": size,
                            "order": {"_key": sort_order},
                        }
                    }
                },
            )

            unique_values = [
                bucket["key"]
                for bucket in response["aggregations"]["unique_values"]["buckets"]
            ]
            return unique_values

        except Exception as e:
            print(f"Error retrieving unique values: {e}")
            return []

    def scroll_and_process_batches(
        self,
        index: str,
        query: Dict[str, Any],
        batch_size: int,
        process_batch_func: Callable[[List[Dict[str, Any]]], bool],
        source_fields: Optional[List[str]] = None,
        scroll_context_time: str = "5m",
    ) -> Tuple[int, int]:
        """
        Scrolls through documents matching a query and processes them in batches.

        Args:
            index: The index to search.
            query: The Elasticsearch query body.
            batch_size: The number of documents to process in each batch.
            process_batch_func: A function that takes a list of hits
                                (each hit is a dict like response['hits']['hits'][n])
                                and processes them. It should return True to continue
                                scrolling, False to stop early.
            source_fields: Optional list of fields to retrieve (_source). If None, retrieves all.
            scroll_context_time: How long the scroll context should be kept alive.

        Returns:
            A tuple (total_processed, total_hits). total_processed might be less
            than total_hits if process_batch_func returned False.
        """
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized.")
            return 0, 0

        total_processed = 0
        total_hits_estimate = 0
        scroll_id = None

        try:
            search_args = {
                "index": index,
                "scroll": scroll_context_time,
                "size": batch_size,
                "body": query,
            }
            if source_fields is not None:
                search_args["_source"] = source_fields  # Specify fields to retrieve

            response = self.instance.search(**search_args)
            scroll_id = response.get("_scroll_id")
            hits = response["hits"]["hits"]
            total_hits_estimate = response["hits"]["total"]["value"]
            self._logger.info(
                f"Scroll initiated on index '{index}'. Estimated total hits: {total_hits_estimate}. Batch size: {batch_size}."
            )

            while scroll_id and hits:
                self._logger.debug(f"Processing batch of {len(hits)} documents...")
                # Process the current batch of hits
                should_continue = process_batch_func(hits)
                total_processed += len(hits)

                if not should_continue:
                    self._logger.warning("Processing function requested early stop.")
                    break

                # Fetch the next batch
                response = self.instance.scroll(
                    scroll_id=scroll_id, scroll=scroll_context_time
                )
                scroll_id = response.get("_scroll_id")
                hits = response["hits"]["hits"]

        except Exception as e:
            self._logger.error(
                f"Error during scroll/batch processing on index '{index}': {e}",
                exc_info=True,
            )
            # Returns counts processed so far before the error

        finally:
            # Clear the scroll context
            if scroll_id:
                try:
                    self.instance.clear_scroll(scroll_id=scroll_id)
                    self._logger.debug(f"Scroll context {scroll_id} cleared.")
                except Exception as clear_err:
                    self._logger.warning(
                        f"Failed to clear scroll context {scroll_id}: {clear_err}"
                    )

        self._logger.info(
            f"Finished scroll/batch processing on index '{index}'. Total documents processed: {total_processed}"
        )
        return total_processed, total_hits_estimate

    # --- NEW METHOD for Bulk Indexing ---
    def bulk_operation(
        self,
        actions: List[Dict[str, Any]],
        raise_on_error: bool = False,
        **kwargs,  # Allow passing other helpers.bulk kwargs like request_timeout
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Performs a bulk operation (index, update, delete) using pre-formatted actions.

        Args:
            actions: A list of bulk action dictionaries. Each dict represents one
                     action line (e.g., {"update": {"_index": "my-index", "_id": "1"}})
                     followed potentially by a data line (e.g., {"doc": {...}, "doc_as_upsert": True}).
                     The format should follow Elasticsearch bulk API syntax.
            raise_on_error: If True, raises the first BulkIndexError encountered.
                            If False (default), logs errors and returns them.
            kwargs: Additional keyword arguments to pass to elasticsearch.helpers.bulk.

        Returns:
            A tuple (number_of_successes, list_of_errors).
            Each error dict contains details about the failed operation.
        """
        if self.instance is None:
            self._logger.error(
                "Elasticsearch instance not initialized. Cannot perform bulk operation."
            )
            return 0, [{"error": "Elasticsearch connection failed"}]
        if not actions:
            self._logger.info("No actions provided for bulk operation.")
            return 0, []

        # Set default timeout if not provided
        if "request_timeout" not in kwargs:
            kwargs["request_timeout"] = (
                120  # Increase default timeout for potentially larger bulk updates
            )

        try:
            self._logger.debug(
                f"Performing bulk operation with {len(actions)} actions..."
            )
            # Pass the actions list directly to helpers.bulk
            success_count, errors = helpers.bulk(
                self.instance,
                actions,  # Pass the pre-formatted actions
                raise_on_error=raise_on_error,
                raise_on_exception=raise_on_error,
                **kwargs,  # Pass additional arguments like timeout
            )
            if errors:
                self._logger.error(
                    f"Encountered {len(errors)} errors during bulk operation."
                )
                for i, err in enumerate(errors[:5]):
                    self._logger.error(f"Bulk Error {i + 1}/{len(errors)}: {err}")
            self._logger.debug(
                f"Bulk operation completed. Successes: {success_count}, Errors: {len(errors)}"
            )
            return success_count, errors
        except helpers.BulkIndexError as e:
            self._logger.error(
                f"Bulk operation failed with BulkIndexError: {len(e.errors)} errors.",
                exc_info=True,
            )
            return 0, e.errors
        except Exception as e:
            self._logger.error(
                f"Unexpected error during bulk operation: {e}", exc_info=True
            )
            return 0, [{"error": "Unexpected bulk operation error", "details": str(e)}]

    # --- (Optional) Keep the old bulk_index for simple cases or deprecate it ---
    def bulk_index(
        self, actions: List[Dict[str, Any]], index: str, raise_on_error: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        [DEPRECATED - Use bulk_operation for more flexibility]
        Performs a simple bulk indexing operation.
        """
        self._logger.warning(
            "Method 'bulk_index' is deprecated. Use 'bulk_operation' with formatted actions."
        )
        formatted_actions = [{"_index": index, "_source": doc} for doc in actions]
        return self.bulk_operation(
            actions=formatted_actions, raise_on_error=raise_on_error
        )

    # --- REFINED/NEW Sampling Method ---
    def get_sample_lines(
        self,
        index: str,
        field: str,
        sample_size: int,
        query: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Retrieves a random sample of values from a specific field in an index,
        optionally matching a query.

        Args:
            index: The index to sample from.
            field: The field whose values are to be sampled (e.g., "content").
            sample_size: The number of samples to retrieve.
            query: Optional Elasticsearch query body to filter documents before sampling.
                   Defaults to {"match_all": {}}.

        Returns:
            A list of strings, where each string is a value from the specified field
            from the sampled documents. Returns empty list on error or if no hits.
        """
        if self.instance is None:
            self._logger.error("Elasticsearch instance not initialized.")
            return []

        # Ensure query is valid
        if query is None:
            search_query = {"match_all": {}}
        else:
            search_query = query

        # Use function_score with random_score for sampling
        es_query = {
            "size": sample_size,
            "query": {
                "function_score": {
                    "query": search_query,
                    "random_score": {},  # Provides random scoring
                }
            },
            "_source": [field],  # Only fetch the required field
        }

        try:
            self._logger.debug(
                f"Fetching {sample_size} random samples of field '{field}' from index '{index}'..."
            )
            response = self.instance.search(index=index, body=es_query)
            hits = response["hits"]["hits"]
            # Extract the content from the specified field
            samples = [
                hit["_source"][field] for hit in hits if field in hit.get("_source", {})
            ]
            self._logger.info(
                f"Retrieved {len(samples)} samples for field '{field}' from index '{index}'."
            )
            return samples
        except Exception as e:
            self._logger.error(
                f"Error fetching random samples for field '{field}' from index '{index}': {e}",
                exc_info=True,
            )
            return []
