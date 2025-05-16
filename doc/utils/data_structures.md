# Data Structures Utility (`data_struct.py`)

## File: `src/logllm/utils/data_struct.py`

### Overview

Defines `dataclasses` used throughout the application to structure log-related data and facilitate conversion to dictionaries (e.g., for database storage).

### Class: `BaseData`

- **Purpose**: Simple base class providing a `to_dict` method using `dataclasses.asdict`.

### Class: `LineOfLogFile(BaseData)`

- **Purpose**: Represents a single line from a log file with metadata.
- **Fields**: `content` (str), `line_number` (int), `name` (str: file path), `id` (int: file ID), `timestamp` (datetime).
- **`to_dict(self)`**: Overrides base to convert `timestamp` field to ISO 8601 string format.

### Class: `LastLineRead(BaseData)`

- **Purpose**: Represents the state of processing for a log file, tracking the last line number read.
- **Fields**: `last_line_read` (int), `id` (int: file ID), `name` (str: file path).

### Class: `LogFile`

- **Purpose**: Represents a log file, managing its metadata and providing methods for interacting with its stored data in Elasticsearch.
- **Attributes**: `id` (int: unique file ID), `belongs_to` (str: parent group name), `path` (str), `description` (str), `related_events` (list).
- **Key Methods**:
  - **`__init__(self, filename: str, parent: str)`**: Assigns a unique ID and stores path/parent info.
  - **`add_file_description(self, description: str)`**: Adds a textual description.
  - **`to_dict(self) -> dict`**: Returns the instance's attributes as a dictionary.
  - **`get_total_lines(self, db: ElasticsearchDatabase) -> int`**: Queries ES to count the number of stored lines for this file ID.
  - **`get_snapshot(self, id: int, earliest_timestamp: datetime, start: int, size: int, db: ElasticsearchDatabase) -> str | None`**: Retrieves a segment of log lines from ES for this file ID, filtering by timestamp and selecting by line number range. Uses the scroll API for efficiency.

### Class: `Event`

- **Purpose**: Represents a conceptual event derived from logs or user input.
- **Attributes**: `id` (int: unique event ID), `description` (str), `related_files` (list).
- **Key Methods**:
  - **`__init__(self, description: str)`**: Assigns a unique ID.
  - **`to_dict(self) -> dict`**: Returns the instance's attributes as a dictionary.
