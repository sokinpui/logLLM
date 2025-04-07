# Detailed Documentation for `src/logllm/utils/` Modules

This document provides details on the utility classes and functions located within the `src/logllm/utils/` directory, which support the core functionality of the `logLLM` system.

*(Note: `prompts_manager.py` is covered in detail in `doc/prompts_manager.md`)*

---

## File: `src/logllm/utils/llm_model.py`

### Overview
Defines base classes and specific implementations for interacting with Large Language Models (LLMs). Includes handling for API calls, token counting, and structured output generation.

### Class: `LLMModel(ABC)`
- **Purpose**: Abstract base class providing a common interface for various LLM implementations (e.g., Gemini).
- **Key Attributes**: `model`, `embedding`, `context_size`, `rpm_limit`, `min_request_interval`, `_last_api_call_time`.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger, rate limiting defaults.
  - **`_wait_for_rate_limit(self)`**: Pauses execution if the time since the last API call is less than the calculated `min_request_interval`.
  - **`_update_last_call_time(self)`**: Updates the timestamp of the last API call.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**: Abstract method for generating text or structured output. *Must be implemented by subclasses.*
  - **`token_count(self, prompt: str | None) -> int`**: Abstract method for counting tokens. *Must be implemented by subclasses.*

### Class: `GeminiModel(LLMModel)`
- **Purpose**: Implements interaction with Google's Gemini models using the direct `google-generativeai` SDK.
- **Key Methods**:
  - **`__init__(self, model_name: str | None = None)`**:
    - Initializes the connection to the Gemini API using `GENAI_API_KEY` environment variable.
    - Sets the `model_name` (defaults to `cfg.GEMINI_LLM_MODEL`).
    - Configures rate limiting (`rpm_limit`, `min_request_interval`) based on the specific Gemini model using `MODEL_RPM_LIMITS`.
    - Initializes `genai.GenerativeModel` for generation and `GoogleGenerativeAIEmbeddings` (from Langchain) for embeddings.
  - **`token_count(self, prompt: str | None) -> int`**: Implements token counting using `self.model.count_tokens()`. Includes basic fallback estimate.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**:
    - Implements generation using `self.model.generate_content()`.
    - Applies rate limiting (`_wait_for_rate_limit`).
    - If `schema` (Pydantic model) is provided:
        - Converts the schema to a Google API `Tool` using `pydantic_to_google_tool`.
        - Instructs the model to use the tool (`function_calling_config`).
        - Parses the model's function call response, validates against the schema, and returns the Pydantic object. Includes fixes for handling the response arguments.
    - If no schema or function call fails/is absent, returns the text content (`response.text`).
    - Includes error handling for API errors, validation errors, and safety blocking.

- **Utility Function**: **`pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool`**:
  - Converts a Pydantic model into a `google.ai.generativelanguage.Tool` object compatible with the Gemini API's function calling feature. Handles type mapping and schema properties.

---

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

---

## File: `src/logllm/utils/database.py`

### Overview
Provides an abstraction layer for database operations, with a concrete implementation for Elasticsearch.

### Class: `Database(ABC)`
- **Purpose**: Abstract base class defining the required methods for any database implementation.
- **Abstract Methods**: `insert`, `single_search`, `update`, `delete`, `set_vector_store`.

### Class: `ElasticsearchDatabase(Database)`
- **Purpose**: Implements the `Database` interface using the `elasticsearch-py` library.
- **Key Methods**:
  - **`__init__(self)`**: Initializes the `Elasticsearch` client, checks connection to `cfg.ELASTIC_SEARCH_URL`. Stores the client instance in `self.instance`.
  - **`insert(self, data: dict, index: str)`**: Inserts a document into the specified index.
  - **`single_search(self, query: dict, index: str)`**: Executes a search query and returns only the first hit.
  - **`scroll_search(self, query: dict, index: str)`**: Retrieves *all* documents matching a query using the Elasticsearch Scroll API, handling pagination automatically.
  - **`update(self, id: str, data: dict, index: str)`**: Updates an existing document by its ID.
  - **`delete(self, id: str, index: str)`**: Deletes a document by its ID.
  - **`set_vector_store(self, embeddings, index) -> ElasticsearchStore`**: Configures and returns a `langchain_elasticsearch.ElasticsearchStore` instance for vector similarity searches.
  - **`random_sample(self, index: str, size: int)`**: Retrieves a random sample of documents using `function_score` with `random_score`.
  - **`add_alias(self, index: str, alias: str, filter: dict = None)`**: Adds an alias to an index, optionally with a filter, and returns the count of documents matching the filter.
  - **`count_docs(self, index: str, filter: dict = None)`**: Returns the count of documents in an index, optionally matching a filter.
  - **`get_unique_values_composite(...)`**: Retrieves unique values using composite aggregation (handles pagination for large cardinality fields).
  - **`get_unique_values(...)`**: Retrieves unique values using terms aggregation (simpler but potentially limited by `size`).
  - **`scroll_and_process_batches(...)`**: Scrolls through documents matching a query and processes them in batches using a provided callback function (`process_batch_func`). Efficient for large-scale processing tasks. Returns total processed count and estimated total hits.
  - **`bulk_operation(...) -> Tuple[int, List[Dict]]`**: Performs bulk operations (index, update, delete) using pre-formatted actions following the Elasticsearch bulk API syntax. Uses `elasticsearch.helpers.bulk`. Returns success count and list of errors.
  - **`bulk_index(...)`**: [DEPRECATED] Simple bulk indexing wrapper; `bulk_operation` is preferred.
  - **`get_sample_lines(...) -> List[str]`**: Retrieves a random sample of values from a *specific field* within documents matching an optional query. Uses `function_score`.

---

## File: `src/logllm/utils/container_manager.py`

### Overview
Manages Docker containers, primarily for setting up the Elasticsearch and Kibana environment. Includes logic for handling different operating systems (macOS via Colima, Linux, basic Windows check).

### Class: `ContainerManager(ABC)`
- **Purpose**: Abstract base class for container management.
- **Abstract Methods**: `remove_container` (and potentially others like start, stop, status if formalized).

### Class: `DockerManager(ContainerManager)`
- **Purpose**: Concrete implementation using `docker-py` to interact with the Docker daemon.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger. Client is initialized lazily by `_ensure_client`.
  - **`_ensure_client(self, memory_gb: Optional[int] = None) -> bool`**: Checks if the client is initialized. If not, calls `_start_daemon` (passing `memory_gb`). Returns `True` if client is ready.
  - **`_start_daemon(self, memory_gb: Optional[int] = None) -> Optional[docker.client.DockerClient]`**: Detects OS. On macOS, checks Colima status, starts it if necessary (using `memory_gb` or `cfg.COLIMA_MEMORY_SIZE`), sets `DOCKER_HOST`, and returns a client. On Linux/Windows, attempts direct connection assuming daemon/Desktop is running.
  - **`start_container(self, name: str, image: str, ..., memory_gb: int = 4) -> Optional[str]`**: Starts a container. Ensures client is ready via `_ensure_client` (passing `memory_gb`), removes existing container with the same name, pulls image if needed, creates network/volume if needed (via internal methods), and runs the container. Returns container ID or `None`.
  - **`stop_container(self, name: str) -> bool`**: Stops a running container by name.
  - **`remove_container(self, name: str) -> bool`**: Forcefully removes a container by name.
  - **`get_container_status(self, name: str) -> str`**: Returns the status ('running', 'exited', 'not found', 'error') of a container.
  - **`_remove_container_if_exists(self, container_name: str)`**: Helper to stop and remove a container by name if it exists.
  - **`_create_network(self, network_name: str)`**: Creates Docker network if it doesn't exist.
  - **`_create_volume(self, volume_name: str)`**: Creates Docker volume if it doesn't exist.
  - **`_pull_image(self, image: str) -> None`**: Pulls Docker image if not found locally.

---

## File: `src/logllm/utils/logger.py`

### Overview
Provides a singleton `Logger` class for consistent logging across the application.

### Class: `Logger`
- **Purpose**: Singleton logger setup using Python's `logging` module. Configures handlers for console output (INFO level) and rotating file output (DEBUG level).
- **`__new__(cls, *args, **kwargs)`**: Ensures only one instance of the logger is created (Singleton pattern).
- **`__init__(self, name: str = cfg.LOGGER_NAME, log_file: str = cfg.LOG_FILE)`**: Initializes the logger (only runs once per instance). Sets up a `StreamHandler` (console) and `RotatingFileHandler` (file) with a detailed formatter. Creates log directory if needed.
- **Logging Methods** (`info`, `debug`, `warning`, `error`, `critical`, `exception`): Wrapper methods that call the corresponding methods on the underlying `logging.Logger` instance. They accept `*args` and `**kwargs` for flexible message formatting and logging options (like `exc_info=True`).

---

## File: `src/logllm/utils/collector.py`

### Overview
Handles the discovery and ingestion of log files from a specified directory into Elasticsearch.

### Class: `Collector`
- **Purpose**: Scans directories for `.log` files, groups them by parent directory, stores group information in ES, and ingests log lines into group-specific ES indices.
- **Key Methods**:
  - **`__init__(self, dir: str)`**: Initializes the collector, scans the directory (`collect_logs`), groups the files (`group_files`), and inserts group info into ES (`insert_group_to_db`).
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

---

## File: `src/logllm/utils/rag_manager.py`

### Overview
Manages Retrieval-Augmented Generation (RAG) capabilities, using Elasticsearch as a vector store for document embeddings.

### Class: `RAGManager`
- **Purpose**: Loads documents, splits them, creates embeddings, stores them in an Elasticsearch vector index, and retrieves relevant document chunks based on a query to provide context to an LLM.
- **Key Methods**:
  - **`__init__(self, name: str, db: ElasticsearchDatabase, embeddings, model: LLMModel, multi_threading: bool = False)`**: Initializes the manager, setting up the `ElasticsearchStore` connected to a specific index (`cfg.INDEX_VECTOR_STORE + "_" + name`).
  - **`retrieve(self, prompt: str) -> str`**: Performs a similarity search in the vector store based on the `prompt`, retrieves top N documents, formats their content, and embeds it into a contextual prompt template (`prompts.rag.prompt`).
  - **`update_rag_from_directory(self, directory: str, db: ElasticsearchDatabase, file_extension: str = "md")`**: Clears the existing vector index, loads documents from the specified `directory` (using `DirectoryLoader`), splits them into chunks (using `RecursiveCharacterTextSplitter`), generates embeddings, and indexes the chunks into the Elasticsearch vector store.
  - **`_load_from_directory(...)`**: Internal helper called by `update_rag_from_directory` to handle loading, splitting, and indexing documents.

---

## File: `src/logllm/utils/chunk_manager.py`

### Overview
Utility class designed to fetch large amounts of text data (like log lines associated with an event or file) from Elasticsearch and serve it in manageable chunks that respect LLM token limits.

### Class: `ESTextChunkManager`
- **Purpose**: Given an identifier (like a file ID or event ID), fetches all associated documents from a specified ES index, and provides methods to iterate through the content field (`field`) of these documents in chunks, ensuring each chunk's token count (calculated via `len_fn`) does not exceed `max_len`.
- **Key Methods**:
  - **`__init__(self, id: Any, field: str, index: str, db: ElasticsearchDatabase)`**: Initializes by fetching *all* relevant hits using `_get_all_hits` (which uses `db.scroll_search`).
  - **`get_next_chunk(self, max_len: int, len_fn: Callable[[str], int]) -> str`**: Returns the next chunk of aggregated text content. Internally uses `_build_chunk` which dynamically adjusts how many hits' content are combined to stay under `max_len`. Updates internal pointers. Returns empty string when done.
  - **`is_end(self) -> bool`**: Returns `True` if all fetched hits have been processed into chunks.
  - **`get_current_chunk(self) -> str | None`**: Returns the last chunk generated by `get_next_chunk`.
  - **`_get_all_hits() -> list`**: Fetches all documents matching the ID using scrolling.
  - **`_build_chunk(...) -> str`**: Iteratively adds content from hits to the chunk, adjusting the number added per step based on token limits.

---
These descriptions cover the primary roles and key methods of the utility classes within the `src/logllm/utils/` directory, reflecting the latest code provided.

