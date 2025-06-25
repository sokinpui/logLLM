# Collector Utility (`collector.py`)

## File: `src/logllm/utils/collector.py`

### Overview

Handles the discovery and ingestion of log files from a specified directory into Elasticsearch.

### Class: `Collector`

- **Purpose**: Scans directories for log files (e.g., `.log`, `.txt`, `.gz`), groups them based on their parent directory structure, stores this group information in Elasticsearch, and ingests the content of these log files line by line into group-specific Elasticsearch indices.
- **Key Methods**:
  - **`__init__(self, dir: str)`**:
    - Initializes the collector with a base directory.
    - Calls `collect_logs` to find log files.
    - Calls `group_files` to organize them into groups.
    - Calls `insert_group_to_db` to store group metadata in `cfg.INDEX_GROUP_INFOS` in Elasticsearch.
  - **`collect_logs(self, directory: str) -> list[LogFile]`**:
    - Recursively scans the given `directory` for files with common log extensions.
    - For each found log file, creates a `LogFile` object. The `belongs_to` attribute of `LogFile` is set to the name of the immediate parent directory of the log file (if the file is in a subdirectory of `directory`) or the base name of `directory` itself (if the file is directly under `directory`).
    - Returns a list of `LogFile` objects.
  - **`group_files(self, files: list[LogFile]) -> dict[str, list[str]]`**:
    - Takes a list of `LogFile` objects.
    - Groups them into a dictionary where keys are the `belongs_to` attribute (group name) and values are lists of absolute file paths for that group.
  - **`insert_group_to_db(self, groups: dict[str, list[str]], db: Database)`**:
    - Clears the existing `cfg.INDEX_GROUP_INFOS` index.
    - For each group, inserts a document into `cfg.INDEX_GROUP_INFOS` containing the group name and a list of relative file paths (relative to `self._base_directory`).
  - **`collect_events(self, file: str) -> list[Event]`**:
    - Reads event descriptions from a specified text file, where events are separated by blank lines.
    - Returns a list of `Event` objects.
  - **`insert_events_to_db(self, db: Database, events: list[Event])`**:
    - Inserts `Event` objects into the `cfg.INDEX_EVENTS_STORAGE` index.
  - **`insert_very_large_logs_into_db(self, db: ElasticsearchDatabase, files: list[LogFile])`**:
    - **Preferred method for log ingestion.**
    - Iterates through each `LogFile` object.
    - Retrieves the last line number read for the file using `_get_last_line_read`.
    - Reads the log file line by line, starting from after the `last_line_read`.
    - For each new line, creates a `LineOfLogFile` object (which no longer includes `ingestion_timestamp`). The `name` attribute is the relative path of the log file. The `id` attribute is the stable ID (hash) of the `LogFile`.
    - Batches these `LineOfLogFile` objects and uses `elasticsearch.helpers.bulk` for efficient insertion into a group-specific Elasticsearch index (determined by `cfg.get_log_storage_index(file_obj.belongs_to)`).
    - After processing a file, updates the last line read status using `_save_last_line_read`.
    - Handles `FileNotFoundError` and other exceptions during processing.
  - **`_get_last_line_read(self, log_file: LogFile, db: Database) -> int`**:
    - Retrieves the last processed line number for `log_file` (using `log_file.id`) from the `cfg.INDEX_LAST_LINE_STATUS` index. Returns 0 if no status is found.
  - **`_save_last_line_read(self, log_file: LogFile, db: Database, line_number: int)`**:
    - Updates/upserts the last processed line number for `log_file` (using `log_file.id`) in the `cfg.INDEX_LAST_LINE_STATUS` index. The document now includes `name` (relative path of the log file).
  - **`_clear_records(self, db: Database)`**:
    - Utility method to delete the `cfg.INDEX_LAST_LINE_STATUS` index. (Note: It previously mentioned deleting `cfg.INDEX_LOG_FILES_STORAGE`, but the primary ingestion now goes to group-specific indices).

### Related Data Structures (from `src.logllm.utils.data_struct`)

- `LogFile`: Represents a single log file, now using a hash of its absolute path as its stable `id`.
- `LineOfLogFile`: Represents a single line of a log file, associated with the `LogFile`'s `id`.
- `LastLineRead`: Stores the progress of ingestion for each `LogFile`.
