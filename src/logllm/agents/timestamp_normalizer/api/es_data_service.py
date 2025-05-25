# src/logllm/agents/timestamp_normalizer/api/es_data_service.py
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....config import config as cfg
from ....utils.database import ElasticsearchDatabase
from ....utils.logger import Logger


class TimestampESDataService:
    """
    Handles Elasticsearch interactions specific to the TimestampNormalizerAgent,
    such as fetching group names, and scrolling/updating documents in parsed_log_* indices.
    """

    def __init__(self, db: ElasticsearchDatabase, logger: Optional[Logger] = None):
        self._db = db
        self._logger = logger if logger else Logger()

    def get_all_log_group_names(self) -> List[str]:
        """Fetches all unique log group names from the group_infos index."""
        self._logger.debug(
            f"Fetching all log group names from index: {cfg.INDEX_GROUP_INFOS}"
        )
        try:
            group_names = self._db.get_unique_values_composite(
                index=cfg.INDEX_GROUP_INFOS,
                field="group.keyword",  # Assuming 'group' is the field name
            )
            if not group_names:
                self._logger.info(f"No group names found in {cfg.INDEX_GROUP_INFOS}.")
                return []
            self._logger.info(
                f"Found {len(group_names)} log groups from DB: {group_names}"
            )
            return group_names
        except Exception as e:
            self._logger.error(f"Error fetching log groups: {e}", exc_info=True)
            return []

    def check_index_exists(self, index_name: str) -> bool:
        """Checks if a given Elasticsearch index exists."""
        try:
            return self._db.instance.indices.exists(index=index_name)
        except Exception as e:
            self._logger.error(
                f"Error checking if index '{index_name}' exists: {e}", exc_info=True
            )
            return False

    def scroll_and_process_documents(
        self,
        index_name: str,
        query_body: Dict[str, Any],
        batch_size: int,
        process_batch_callback: Callable[[List[Dict[str, Any]]], bool],
        source_fields: Optional[List[str]] = None,
        limit: Optional[int] = None,  # Added limit parameter
    ) -> Tuple[int, int]:
        """
        Scrolls through documents in an index and processes them in batches.
        The process_batch_callback controls continuation.
        Includes an optional limit on the total number of documents processed.

        Returns:
            Tuple (total_documents_scrolled_from_es, documents_considered_by_callback_due_to_limit)
        """
        docs_processed_by_callback = 0

        # Wrapper for the original callback to implement the limit
        def limited_process_batch_callback(hits_batch: List[Dict[str, Any]]) -> bool:
            nonlocal docs_processed_by_callback
            if not hits_batch:
                return True  # Continue if ES gives an empty batch but scroll is active

            batch_to_feed_callback = hits_batch
            if limit is not None:
                remaining_for_limit = limit - docs_processed_by_callback
                if remaining_for_limit <= 0:
                    return False  # Limit reached, stop scrolling
                batch_to_feed_callback = hits_batch[:remaining_for_limit]

            if not batch_to_feed_callback:  # If limit truncation results in empty batch
                return False

            should_continue = process_batch_callback(batch_to_feed_callback)
            docs_processed_by_callback += len(batch_to_feed_callback)

            if limit is not None and docs_processed_by_callback >= limit:
                return False  # Limit reached or exceeded, stop scrolling

            return should_continue

        # The scroll_and_process_batches method from ElasticsearchDatabase handles the actual scroll
        total_scrolled_from_es, _ = self._db.scroll_and_process_batches(
            index=index_name,
            query=query_body,
            batch_size=batch_size,
            process_batch_func=limited_process_batch_callback,  # Use the wrapped callback
            source_fields=source_fields,
        )
        return total_scrolled_from_es, docs_processed_by_callback

    def bulk_update_documents(self, actions: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Performs bulk update operations in Elasticsearch.

        Args:
            actions: A list of ES bulk actions.

        Returns:
            A tuple (number_of_successes, number_of_errors).
        """
        if not actions:
            return 0, 0
        success_count, errors_list = self._db.bulk_operation(actions=actions)
        num_errors = len(errors_list)
        if num_errors > 0:
            self._logger.warning(
                f"{num_errors} errors occurred during bulk update operation. First few: {errors_list[:3]}"
            )
        return success_count, num_errors
