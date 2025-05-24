# src/logllm/agents/static_grok_parser/api/es_data_service.py
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from elasticsearch import ConnectionError, NotFoundError

try:
    from ....config import config as cfg
    from ....utils.database import ElasticsearchDatabase
    from ....utils.logger import Logger
except ImportError:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from config import config as cfg
    from utils.database import ElasticsearchDatabase
    from utils.logger import Logger


INDEX_STATIC_GROK_PARSE_STATUS = "static_grok_parse_status"


class ElasticsearchDataService:
    def __init__(self, db: ElasticsearchDatabase):
        self._db = db
        self._logger = Logger()
        self._ensure_status_index()

    def _ensure_status_index(self):
        if not self._db.instance.indices.exists(index=INDEX_STATIC_GROK_PARSE_STATUS):
            try:
                self._db.instance.indices.create(
                    index=INDEX_STATIC_GROK_PARSE_STATUS,
                    body={
                        "mappings": {
                            "properties": {
                                "log_file_id": {"type": "keyword"},
                                "last_line_number_parsed_by_grok": {"type": "long"},
                                "last_total_lines_by_collector": {"type": "long"},
                                "last_parse_timestamp": {"type": "date"},
                            }
                        }
                    },
                )
                self._logger.info(
                    f"Created index '{INDEX_STATIC_GROK_PARSE_STATUS}' for static Grok parse status."
                )
            except Exception as e:
                self._logger.error(
                    f"Error creating index '{INDEX_STATIC_GROK_PARSE_STATUS}': {e}",
                    exc_info=True,
                )

    def get_all_log_group_names(self) -> List[str]:
        self._logger.debug(
            f"Fetching log group names from index: {cfg.INDEX_GROUP_INFOS}"
        )
        try:
            group_names = self._db.get_unique_values_composite(
                index=cfg.INDEX_GROUP_INFOS,
                field="group.keyword",
            )
            if not group_names:
                self._logger.info(f"No group names found in {cfg.INDEX_GROUP_INFOS}.")
                return []
            self._logger.info(f"Found {len(group_names)} log groups from DB.")
            return group_names
        except Exception as e:
            self._logger.error(f"Error fetching log groups: {e}", exc_info=True)
            return []

    def get_log_file_ids_for_group(self, group_name: str) -> List[str]:
        source_index_for_group = cfg.get_log_storage_index(group_name)
        self._logger.debug(
            f"Fetching distinct LogFile IDs for group '{group_name}' from '{source_index_for_group}'"
        )
        try:
            distinct_log_file_ids = self._db.get_unique_values_composite(
                index=source_index_for_group, field="id.keyword"
            )
            if not distinct_log_file_ids:
                self._logger.info(
                    f"No log files (distinct IDs) found in raw index '{source_index_for_group}' for group '{group_name}'."
                )
                return []
            self._logger.info(
                f"Found {len(distinct_log_file_ids)} distinct log file IDs in group '{group_name}'."
            )
            return distinct_log_file_ids
        except Exception as e:
            self._logger.error(
                f"Could not fetch distinct log file IDs for group '{group_name}' from '{source_index_for_group}': {e}",
                exc_info=True,
            )
            return []

    def get_grok_parse_status_for_file(self, log_file_id: str) -> Dict[str, Any]:
        try:
            doc = self._db.instance.get(
                index=INDEX_STATIC_GROK_PARSE_STATUS, id=log_file_id
            )
            source = doc.get("_source", {})
            return {
                "last_line_parsed_by_grok": source.get(
                    "last_line_number_parsed_by_grok", 0
                ),
                "last_total_lines_by_collector": source.get(
                    "last_total_lines_by_collector", 0
                ),
            }
        except NotFoundError:
            self._logger.debug(
                f"No static Grok parse status found for log_file_id '{log_file_id}'. Returning defaults."
            )
            return {"last_line_parsed_by_grok": 0, "last_total_lines_by_collector": 0}
        except Exception as e:
            self._logger.error(
                f"Error fetching static Grok parse status for '{log_file_id}': {e}",
                exc_info=True,
            )
            return {"last_line_parsed_by_grok": 0, "last_total_lines_by_collector": 0}

    def get_collector_status_for_file(self, log_file_id: str) -> int:
        try:
            collector_status_doc = self._db.instance.get(
                index=cfg.INDEX_LAST_LINE_STATUS, id=log_file_id
            )
            return collector_status_doc["_source"].get("last_line_read", 0)
        except NotFoundError:
            self._logger.warning(
                f"No collector status found for log_file_id '{log_file_id}'. Assuming 0 lines collected."
            )
            return 0
        except Exception as e:
            self._logger.error(
                f"Error fetching collector status for '{log_file_id}': {e}. Assuming 0 lines collected.",
                exc_info=True,
            )
            return 0

    def save_grok_parse_status_for_file(
        self,
        log_file_id: str,
        last_line_parsed_by_grok: int,
        current_total_lines_by_collector: int,
    ):
        status_doc = {
            "log_file_id": log_file_id,
            "last_line_number_parsed_by_grok": last_line_parsed_by_grok,
            "last_total_lines_by_collector": current_total_lines_by_collector,
            "last_parse_timestamp": datetime.now().isoformat(),
        }
        update_body = {"doc": status_doc, "doc_as_upsert": True}
        try:
            self._db.instance.update(
                index=INDEX_STATIC_GROK_PARSE_STATUS,
                id=log_file_id,
                body=update_body,
            )
            self._logger.debug(
                f"Saved static Grok parse status for '{log_file_id}': grok_line {last_line_parsed_by_grok}, collector_total {current_total_lines_by_collector}"
            )
        except Exception as e:
            self._logger.error(
                f"Error saving static Grok parse status for '{log_file_id}': {e}",
                exc_info=True,
            )

    def fetch_raw_log_line_batch(
        self,
        source_index: str,
        log_file_id: str,
        start_line_number_exclusive: int,
        batch_size: int,
    ) -> List[Dict[str, Any]]:
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"id.keyword": log_file_id}},
                        {"range": {"line_number": {"gt": start_line_number_exclusive}}},
                    ]
                }
            },
            "sort": [{"line_number": "asc"}],
            "size": batch_size,
            # "_source": ["content", "id", "line_number", "name", "ingestion_timestamp"], # MODIFIED
            "_source": [
                "content",
                "id",
                "line_number",
                "name",
            ],  # REMOVED ingestion_timestamp
        }
        try:
            response = self._db.instance.search(index=source_index, body=query_body)
            return response.get("hits", {}).get("hits", [])
        except Exception as e:
            self._logger.error(
                f"Error fetching batch for '{log_file_id}' from '{source_index}': {e}",
                exc_info=True,
            )
            return []

    def scroll_and_process_raw_log_lines(
        self,
        source_index: str,
        log_file_id: str,
        start_line_number_exclusive: int,
        scroll_batch_size: int,
        process_batch_callback: Callable[[List[Dict[str, Any]]], bool],
    ) -> Tuple[int, int]:
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"id.keyword": log_file_id}},
                        {"range": {"line_number": {"gt": start_line_number_exclusive}}},
                    ]
                }
            },
            "sort": [{"line_number": "asc"}],
        }
        fields_to_fetch = [
            "content",
            "id",
            "line_number",
            "name",
            # "ingestion_timestamp", # REMOVED
        ]

        total_processed_by_scroll, total_hits_estimate = (
            self._db.scroll_and_process_batches(
                index=source_index,
                query=query_body,
                batch_size=scroll_batch_size,
                process_batch_func=process_batch_callback,
                source_fields=fields_to_fetch,
            )
        )
        return total_processed_by_scroll, total_hits_estimate

    def bulk_index_formatted_actions(
        self, actions: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        if not actions:
            return 0, 0
        success_count, errors_list = self._db.bulk_operation(actions=actions)
        num_errors = len(errors_list)
        if num_errors > 0:
            self._logger.warning(
                f"{num_errors} errors occurred during bulk operation. First few: {errors_list[:3]}"
            )
        return success_count, num_errors
