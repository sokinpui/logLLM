# Collector Utility (`collector.py`)

## File: `src/logllm/utils/collector.py`

### Overview

Handles the discovery and ingestion of log files from a specified directory into Elasticsearch.

### Class: `Collector`

- **Purpose**: Scans directories for `.log` files, groups them by parent directory, stores group information in ES, and ingests log lines into group-specific ES indices.
- **Key Methods**:
  - **`__init__(self, dir: str)`**: Initializes the collector by scanning the directory (`collect_logs`), grouping the files (`group_files`), and inserting group info into ES (`insert_group_to_db`) using an `ElasticsearchDatabase` instance.
  - **`collect_logs(self, directory: str) -> list[LogFile]`**: Recursively finds `.log` files in the specified directory, creating `LogFile` objects with parent group information.
  - **`group_files(self, files: list[LogFile]) -> dict[str, list[str]]`**: Groups the collected `LogFile` objects by their `belongs_to` attribute (parent directory name).
  - **`insert_group_to_db(self, groups: dict[str, list[str]], db: Database)`**: Clears and inserts the group name to file path mappings into the `cfg.INDEX_GROUP_INFOS` index in Elasticsearch.
  - **`collect_events(self, file: str) -> list[Event]`**: Reads event descriptions from a text file (split by blank lines).
  - **`insert_events_to_db(self, db: Database, events: list[Event])`**: Inserts `Event` objects into the `cfg.INDEX_EVENTS_STORAGE` index.
  - **`insert_logs_to_db(self, db: Database, files: list)`**: [Less efficient] Inserts logs line-by-line, potentially loading whole files into memory. Tracks progress using `_get/save_last_line_read`.
  - **`insert_very_large_logs_into_db(self, db: ElasticsearchDatabase, files: list[LogFile])`**: **Preferred method.** Efficiently inserts log lines in batches using `elasticsearch.helpers.bulk`. Reads files line-by-line, respects `_get/save_last_line_read` for incremental updates. Inserts into group-specific indices obtained via `cfg.get_log_storage_index(group_name)`.
  - **`_get_last_line_read(...) -> int`**: Retrieves the last processed line number for a file from `cfg.INDEX_LAST_LINE_STATUS`.
  - **`_save_last_line_read(...)`**: Updates the last processed line number for a file in `cfg.INDEX_LAST_LINE_STATUS` using an upsert operation.
  - **`_clear_records(self, db: Database)`**: Utility to delete log storage and status indices (for cleanup/reset).
