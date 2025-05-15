# src/logllm/processors/timestamp_normalizer.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dateutil.parser import parse as dateutil_parse

from ..config import config as cfg
from ..utils.database import ElasticsearchDatabase
from ..utils.logger import Logger


class TimestampNormalizerAgent:
    def __init__(self, db: ElasticsearchDatabase):
        self.db = db
        self.logger = Logger()
        self.potential_raw_ts_fields = [
            "event_timestamp",
            "raw_event_timestamp",
            "timestamp",
            "Timestamp",
            "SYSLOGTIMESTAMP",
            "TIMESTAMP_ISO8601",
            "HTTPDATE",
            "DATESTAMP_APACHELOG",
            "asctime",
        ]
        self.potential_date_part_fields = [
            "date",
            "log_date",
            "event_date",
            "month",
            "day",
            "year",
        ]
        self.potential_time_part_fields = [
            "time",
            "log_time",
            "event_time",
            "timestamp",
        ]

    def _extract_and_parse_datetime(
        self, doc_source: Dict[str, Any], doc_id: str
    ) -> Optional[datetime]:  # Added doc_id for print
        """
        Intelligently tries to find and parse a datetime object from various fields in the document source.
        Prints info about successful parsing.
        """
        # Attempt 1: Look for explicitly named timestamp fields
        for field_name in self.potential_raw_ts_fields:
            if field_name in doc_source:
                raw_value = doc_source[field_name]
                if isinstance(raw_value, (int, float)):  # Unix epoch
                    try:
                        if raw_value > 1e14:
                            dt_obj = datetime.fromtimestamp(
                                raw_value / 1000000.0, tz=timezone.utc
                            )
                        elif raw_value > 1e11:
                            dt_obj = datetime.fromtimestamp(
                                raw_value / 1000.0, tz=timezone.utc
                            )
                        else:
                            dt_obj = datetime.fromtimestamp(raw_value, tz=timezone.utc)
                        self.logger.debug(
                            f"DocID {doc_id}: Parsed epoch from '{field_name}': {raw_value} -> {dt_obj}"
                        )
                        # print(f"  DocID {doc_id}: Found epoch in '{field_name}' ('{raw_value}') -> Parsed: {dt_obj}") # Optional: too verbose
                        return dt_obj
                    except (ValueError, TypeError, OverflowError) as e:
                        self.logger.debug(
                            f"DocID {doc_id}: Could not parse epoch from '{field_name}' value '{raw_value}': {e}"
                        )
                elif isinstance(raw_value, str) and raw_value.strip():
                    try:
                        dt_obj = dateutil_parse(raw_value)
                        self.logger.debug(
                            f"DocID {doc_id}: Parsed string from '{field_name}': '{raw_value}' -> {dt_obj}"
                        )
                        print(
                            f"  DocID {doc_id}: Found timestamp in field '{field_name}' ('{raw_value}') -> Parsed: {dt_obj.isoformat()}"
                        )
                        return dt_obj
                    except (ValueError, TypeError) as e:
                        self.logger.debug(
                            f"DocID {doc_id}: Could not parse string from '{field_name}' value '{raw_value}': {e}"
                        )

        date_str, time_str = None, None
        combined_fields_used = []
        for field_name in self.potential_date_part_fields:
            if (
                field_name in doc_source
                and isinstance(doc_source[field_name], str)
                and doc_source[field_name].strip()
            ):
                date_str = doc_source[field_name]
                combined_fields_used.append(field_name)
                break
        for field_name in self.potential_time_part_fields:
            if (
                field_name in doc_source
                and isinstance(doc_source[field_name], str)
                and doc_source[field_name].strip()
            ):
                if field_name == "timestamp" and date_str:
                    try:
                        dateutil_parse(
                            doc_source[field_name], default=datetime(1900, 1, 1)
                        )
                        time_str = doc_source[field_name]
                        combined_fields_used.append(field_name)
                    except ValueError:
                        pass
                elif field_name != "timestamp":
                    time_str = doc_source[field_name]
                    combined_fields_used.append(field_name)
                break
        if date_str and time_str:
            try:
                dt_obj = dateutil_parse(f"{date_str} {time_str}")
                self.logger.debug(
                    f"DocID {doc_id}: Parsed combined date/time: '{date_str} {time_str}' (from {combined_fields_used}) -> {dt_obj}"
                )
                print(
                    f"  DocID {doc_id}: Combined fields {combined_fields_used} ('{date_str} {time_str}') -> Parsed: {dt_obj.isoformat()}"
                )
                return dt_obj
            except (ValueError, TypeError) as e:
                self.logger.debug(
                    f"DocID {doc_id}: Could not parse combined date/time '{date_str} {time_str}': {e}"
                )
        elif date_str:
            try:
                dt_obj = dateutil_parse(date_str)
                self.logger.debug(
                    f"DocID {doc_id}: Parsed date-only: '{date_str}' (from {combined_fields_used}) -> {dt_obj}"
                )
                print(
                    f"  DocID {doc_id}: Found date-only in {combined_fields_used} ('{date_str}') -> Parsed: {dt_obj.isoformat()}"
                )
                return dt_obj
            except (ValueError, TypeError) as e:
                self.logger.debug(
                    f"DocID {doc_id}: Could not parse date-only '{date_str}': {e}"
                )

        if "@timestamp" in doc_source and isinstance(doc_source["@timestamp"], str):
            try:
                dt_obj = dateutil_parse(doc_source["@timestamp"])
                self.logger.debug(
                    f"DocID {doc_id}: Reparsing existing '@timestamp': '{doc_source['@timestamp']}' -> {dt_obj}"
                )
                print(
                    f"  DocID {doc_id}: Found existing '@timestamp' ('{doc_source['@timestamp']}') -> Reparsed: {dt_obj.isoformat()}"
                )
                return dt_obj
            except (ValueError, TypeError):
                self.logger.debug(
                    f"DocID {doc_id}: Existing '@timestamp' ('{doc_source['@timestamp']}') is not parsable by dateutil."
                )

        self.logger.debug(f"DocID {doc_id}: No parsable timestamp found.")
        return None

    def normalize_document_timestamp(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_source = doc.get("_source", {})
        doc_id = doc.get("_id", "UnknownID")  # Get ID for print statements
        updated_source = doc_source.copy()

        dt_obj = self._extract_and_parse_datetime(updated_source, doc_id)  # Pass doc_id
        original_timestamp_data = {
            k: v
            for k, v in updated_source.items()
            if k in self.potential_raw_ts_fields
            or k in self.potential_date_part_fields
            or k in self.potential_time_part_fields
            or k == "@timestamp"
        }

        if dt_obj:
            if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
                dt_obj_utc = dt_obj.replace(tzinfo=timezone.utc)
                self.logger.debug(
                    f"DocID {doc_id}: Timestamp was naive, made UTC: {dt_obj} -> {dt_obj_utc}"
                )
            else:
                dt_obj_utc = dt_obj.astimezone(timezone.utc)
                self.logger.debug(
                    f"DocID {doc_id}: Timestamp was tz-aware, converted to UTC: {dt_obj} -> {dt_obj_utc}"
                )

            normalized_iso_ts = dt_obj_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            updated_source["@timestamp"] = normalized_iso_ts
            # Print success information to stdout
            print(f"  DocID {doc_id}: Normalized to -> @timestamp: {normalized_iso_ts}")

            updated_source["timestamp_normalized_details"] = {
                "status": "success",
                "original_data_used": original_timestamp_data,
                "parsed_datetime_object": str(
                    dt_obj
                ),  # Keep original parsed object string
                "normalized_datetime_utc": str(
                    dt_obj_utc
                ),  # Keep normalized object string
                "normalized_at": datetime.now(timezone.utc).isoformat(),
            }
            if "timestamp_normalization_issue" in updated_source:
                del updated_source["timestamp_normalization_issue"]
        else:
            self.logger.warning(f"DocID {doc_id}: No parsable timestamp found.")
            # Print fallback information to stdout
            if "@timestamp" not in updated_source:
                current_time_iso = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                updated_source["@timestamp"] = current_time_iso
                print(
                    f"  DocID {doc_id}: Fallback -> @timestamp set to current time: {current_time_iso}"
                )
                updated_source["timestamp_normalized_details"] = {
                    "status": "fallback_to_current_time",
                    "reason": "No parsable timestamp fields found.",
                    "normalized_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                print(
                    f"  DocID {doc_id}: Kept existing '@timestamp': {updated_source['@timestamp']} (no other parsable fields or existing not re-processed)."
                )
                updated_source["timestamp_normalized_details"] = {
                    "status": "kept_existing_at_timestamp",
                    "reason": "No other parsable fields found or existing @timestamp was not re-processed.",
                    "normalized_at": datetime.now(timezone.utc).isoformat(),
                }

        return {"_id": doc_id, "_source": updated_source}

    def process_group(
        self, group_name: str, limit: Optional[int] = None, batch_size: int = 100
    ):
        source_index = cfg.get_parsed_log_storage_index(group_name)
        target_index = cfg.get_normalized_parsed_log_storage_index(group_name)

        self.logger.info(f"Starting timestamp normalization for group '{group_name}'.")
        self.logger.info(
            f"Source index: '{source_index}', Target index: '{target_index}'"
        )
        if limit:
            self.logger.info(f"Processing limit: {limit} documents.")
            print(
                f"Processing group '{group_name}' (Limit: {limit} documents)"
            )  # Added print

        if not self.db.instance.indices.exists(index=source_index):
            self.logger.error(
                f"Source index '{source_index}' does not exist. Skipping group '{group_name}'."
            )
            print(
                f"Error: Source index '{source_index}' not found for group '{group_name}'."
            )
            return 0, 0

        if not self.db.instance.indices.exists(index=target_index):
            mapping = {
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "timestamp_normalized_details": {
                            "type": "object",
                            "enabled": False,
                        },
                    }
                }
            }
            try:
                self.db.instance.indices.create(index=target_index, body=mapping)
                self.logger.info(
                    f"Created target index '{target_index}' with mapping for '@timestamp'."
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create target index '{target_index}': {e}. Aborting for this group."
                )
                print(f"Error creating target index for {group_name}: {e}")
                return 0, 0

        processed_docs_count = 0
        successfully_indexed_count = 0
        actions_for_bulk = []
        current_batch_doc_ids_for_print = []  # For printing which docs are in batch

        def process_batch_callback(hits: List[Dict[str, Any]]) -> bool:
            nonlocal processed_docs_count, successfully_indexed_count, actions_for_bulk, current_batch_doc_ids_for_print

            print(
                f"\nProcessing batch of {len(hits)} documents for group '{group_name}'..."
            )  # Print batch start
            current_batch_doc_ids_for_print = []

            for hit in hits:
                if limit is not None and processed_docs_count >= limit:
                    print(
                        f"Limit of {limit} documents reached for group '{group_name}'. Stopping batch processing."
                    )
                    return False

                doc_id_for_print = hit.get("_id", "N/A")
                current_batch_doc_ids_for_print.append(doc_id_for_print)
                # print(f"  Normalizing DocID: {doc_id_for_print}...") # Can be too verbose, let normalize_document_timestamp print specifics

                normalized_doc = self.normalize_document_timestamp(hit)
                actions_for_bulk.append(
                    {
                        "_op_type": "index",
                        "_index": target_index,
                        "_id": normalized_doc["_id"],
                        "_source": normalized_doc["_source"],
                    }
                )
                processed_docs_count += 1

                if len(actions_for_bulk) >= batch_size:
                    print(
                        f"  Flushing batch of {len(actions_for_bulk)} to '{target_index}' (Doc IDs: {', '.join(current_batch_doc_ids_for_print[:3])}{'...' if len(current_batch_doc_ids_for_print) > 3 else ''})..."
                    )
                    succeeded, errors = self.db.bulk_operation(actions=actions_for_bulk)
                    successfully_indexed_count += succeeded
                    if errors:
                        self.logger.error(
                            f"{len(errors)} errors during bulk indexing to '{target_index}'. First error: {errors[0]}"
                        )
                        print(
                            f"  ERROR during bulk indexing: {len(errors)} errors. See logs."
                        )
                    else:
                        print(
                            f"  Successfully indexed {succeeded} documents in this batch."
                        )
                    actions_for_bulk = []
                    current_batch_doc_ids_for_print = []  # Reset for next batch
            return True

        scanned_count, _ = self.db.scroll_and_process_batches(
            index=source_index,
            query={"query": {"match_all": {}}},
            batch_size=(
                batch_size
                if limit is None
                else min(
                    batch_size,
                    (
                        limit - processed_docs_count
                        if limit is not None and limit - processed_docs_count > 0
                        else 1
                    ),
                )
            ),
            process_batch_func=process_batch_callback,
        )

        if actions_for_bulk:
            print(
                f"\nFlushing final batch of {len(actions_for_bulk)} to '{target_index}' (Doc IDs: {', '.join(current_batch_doc_ids_for_print[:3])}{'...' if len(current_batch_doc_ids_for_print) > 3 else ''})..."
            )
            succeeded, errors = self.db.bulk_operation(actions=actions_for_bulk)
            successfully_indexed_count += succeeded
            if errors:
                self.logger.error(
                    f"{len(errors)} errors during final bulk indexing to '{target_index}'. First error: {errors[0]}"
                )
                print(
                    f"  ERROR during final bulk indexing: {len(errors)} errors. See logs."
                )
            else:
                print(f"  Successfully indexed {succeeded} documents in final batch.")

        self.logger.info(f"Timestamp normalization finished for group '{group_name}'.")
        self.logger.info(
            f"Documents scanned from '{source_index}': {scanned_count} (Processed up to limit: {processed_docs_count})"
        )
        self.logger.info(
            f"Documents successfully indexed to '{target_index}': {successfully_indexed_count}"
        )
        # This summary is now printed by the CLI handler after all groups.
        # print(f"Group '{group_name}': Processed {processed_docs_count} docs. Indexed {successfully_indexed_count} to '{target_index}'.")
        return processed_docs_count, successfully_indexed_count
