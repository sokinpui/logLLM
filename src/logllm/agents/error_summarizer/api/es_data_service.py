# src/logllm/agents/error_summarizer/api/es_data_service.py
from typing import Any, Dict, List, Optional

from ....config import config as cfg
from ....utils.database import ElasticsearchDatabase
from ....utils.logger import Logger


class ErrorSummarizerESDataService:
    def __init__(self, db: ElasticsearchDatabase, logger: Optional[Logger] = None):
        self._db = db
        self._logger = logger or Logger()

    def check_field_exists_in_mapping(self, index_name: str, field_name: str) -> bool:
        self._logger.debug(
            f"Checking for field '{field_name}' in mapping of index '{index_name}'"
        )
        if not self._db.instance or not self._db.instance.indices.exists(
            index=index_name
        ):
            self._logger.warning(f"Index '{index_name}' does not exist.")
            return False
        try:
            mapping = self._db.instance.indices.get_mapping(index=index_name)
            # Mapping structure: {index_name: {"mappings": {"properties": {...}}}}
            properties = mapping[index_name]["mappings"].get("properties", {})
            # Check if field_name is a top-level field or nested (simple check for now)
            # For deeply nested fields like "field.subfield.keyword", this needs more robust parsing.
            # Assuming 'loglevel' is a top-level field or field.keyword.
            if field_name in properties:
                return True
            # Check for common keyword subfield
            if f"{field_name}.keyword" in properties:
                return True

            # Check if field_name is part of a path (e.g., "kubernetes.labels.app")
            keys = field_name.split(".")
            current_level = properties
            for key in keys:
                if key in current_level:
                    current_level = current_level[key].get("properties", {})
                    if (
                        current_level is None and key == keys[-1]
                    ):  # Reached the end and it's not a properties dict itself
                        return True
                else:  # A part of the path is missing
                    # Check for keyword variant at the last step
                    if key == keys[-1] and f"{key}.keyword" in current_level:
                        return True
                    return False
            return True  # If loop completes, path exists

        except Exception as e:
            self._logger.error(
                f"Error getting mapping for index '{index_name}': {e}", exc_info=True
            )
            return False

    def fetch_error_logs_in_time_window(
        self,
        index_name: str,
        start_time_iso: str,
        end_time_iso: str,
        error_levels: List[str],
        timestamp_field: str = "@timestamp",  # Assuming normalized timestamp field
        loglevel_field: str = "loglevel",
        content_field: str = "message",  # Or 'content' depending on your parsed log structure
        max_logs: int = 5000,
    ) -> List[Dict[str, Any]]:
        self._logger.info(
            f"Fetching error logs from '{index_name}' for levels {error_levels} between {start_time_iso} and {end_time_iso} (max: {max_logs})"
        )
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "range": {
                                timestamp_field: {
                                    "gte": start_time_iso,
                                    "lte": end_time_iso,
                                    "format": "strict_date_optional_time_nanos",  # Handles ISO8601 UTC
                                }
                            }
                        },
                        {
                            "terms": {f"{loglevel_field}.keyword": error_levels}
                        },  # Use .keyword for exact match on terms
                    ]
                }
            },
            "size": max_logs,
            "sort": [{timestamp_field: {"order": "asc"}}],
            "_source": [
                timestamp_field,
                loglevel_field,
                content_field,
                "original_line_number",
                "original_log_file_name",
            ],  # Add fields you need
        }
        try:
            # Using scroll_search to ensure all (up to max_logs) are fetched if they exceed single search window
            # Note: scroll_search default size is from query, which is good.
            results = self._db.scroll_search(index=index_name, query=query)
            self._logger.info(f"Fetched {len(results)} error logs from '{index_name}'.")
            return [r["_source"] for r in results]
        except Exception as e:
            self._logger.error(
                f"Error fetching error logs from '{index_name}': {e}", exc_info=True
            )
            return []

    def store_error_summary(
        self, summary_doc: Dict[str, Any], target_index: str
    ) -> Optional[str]:
        self._logger.debug(f"Storing error summary in index '{target_index}'")
        try:
            # Ensure target_index exists with a suitable mapping (minimal for now)
            if not self._db.instance.indices.exists(index=target_index):
                self._logger.info(f"Creating summary index: {target_index}")
                self._db.instance.indices.create(
                    index=target_index,
                    body={
                        "mappings": {
                            "properties": {
                                "group_name": {"type": "keyword"},
                                "analysis_start_time": {"type": "date"},
                                "analysis_end_time": {"type": "date"},
                                "cluster_id": {"type": "keyword"},
                                "log_level_filter": {"type": "keyword"},
                                "summary_text": {"type": "text"},
                                "potential_cause_text": {"type": "text"},
                                "keywords": {"type": "keyword"},
                                "representative_log_line_text": {"type": "text"},
                                "sample_log_count": {"type": "integer"},
                                "total_logs_in_cluster": {"type": "integer"},
                                "cluster_time_range_start": {"type": "date"},
                                "cluster_time_range_end": {"type": "date"},
                                "generation_timestamp": {"type": "date"},
                            }
                        }
                    },
                    ignore=[400],  # Ignore if already created by a concurrent process
                )

            res = self._db.instance.index(index=target_index, document=summary_doc)
            self._logger.info(
                f"Error summary stored with ID: {res.get('_id')} in '{target_index}'."
            )
            return res.get("_id")
        except Exception as e:
            self._logger.error(
                f"Error storing error summary in '{target_index}': {e}", exc_info=True
            )
            return None
