# Data Structures Utility (`data_struct.py`)

## File: `src/logllm/utils/data_struct.py`

### Overview

Defines `dataclasses` used throughout the application to structure log-related data and facilitate conversion to dictionaries (e.g., for database storage).

### Class: `BaseData`

- **Purpose**: Simple base class providing a `to_dict` method using `dataclasses.asdict`.

### Class: `LineOfLogFile(BaseData)`

- **Purpose**: Represents a single line from a log file with metadata.
- **Fields**:
  - `content` (str): The raw content of the log line.
  - `line_number` (int): The 0-indexed line number within its original file.
  - `name` (str): The relative path of the log file from the collector's base directory.
  - `id` (str): The stable ID (MD5 hash of the absolute file path) of the `LogFile` this line belongs to.
  - **Note**: `ingestion_timestamp` has been removed from this dataclass.

### Class: `LastLineRead(BaseData)`

- **Purpose**: Represents the state of processing for a log file, tracking the last line number read by the `Collector`.
- **Fields**:
  - `last_line_read` (int): The number of lines previously read (i.e., the next line to read is this value, 0-indexed).
  - `id` (str): The stable ID (MD5 hash) of the `LogFile`.
  - `name` (str): The relative path of the log file.

### Class: `LogFile`

- **Purpose**: Represents a log file, managing its metadata and providing methods for interacting with its stored data in Elasticsearch.
- **Attributes**:
  - `path` (str): The absolute, normalized path to the log file.
  - `id` (str): A stable identifier for the log file, generated as an MD5 hash of its `path`.
  - `belongs_to` (str): The name of the group (typically parent directory name) this log file belongs to.
  - `description` (str): A textual description of the log file (optional).
  - `related_events` (list): A list to store related event information (optional).
- **Key Methods**:
  - **`__init__(self, filename: str, parent: str)`**: Initializes the `LogFile` instance. Normalizes `filename` to an absolute path and generates the `id` using MD5 hash. Sets `belongs_to`.
  - **`add_file_description(self, description: str)`**: Adds a textual description to the log file.
  - **`to_dict(self) -> dict`**: Returns a dictionary representation of the `LogFile` instance, suitable for storage or serialization. Includes `id`, `path`, `belongs_to`, and `description`.
  - **`get_total_lines(self, db: ElasticsearchDatabase) -> int`**: Queries Elasticsearch (`log_<group_name>` index) to count the number of stored line entries associated with this `LogFile`'s `id`.
  - **`get_snapshot(self, earliest_timestamp: datetime, start: int, size: int, db: ElasticsearchDatabase) -> str | None`**:
    - Retrieves a segment of log lines from Elasticsearch for this `LogFile`'s `id`.
    - **Note**: The `earliest_timestamp` parameter is currently commented out in the implementation's query, meaning it fetches based on line number and ID primarily. The query sorts by `line_number`.
    - Returns a string concatenating the line number and content for the fetched snapshot, or `None` if no lines are found or an error occurs.

### Class: `Event`

- **Purpose**: Represents a conceptual event derived from logs or user input.
- **Attributes**:
  - `id` (int): A unique, auto-incrementing ID for the event.
  - `description` (str): Textual description of the event.
  - `related_files` (list): A list to store associated file information.
- **Key Methods**:
  - **`__init__(self, description: str)`**: Assigns a unique ID and sets the description.
  - **`to_dict(self) -> dict`**: Returns the instance's attributes as a dictionary.
