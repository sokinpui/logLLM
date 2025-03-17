# Detailed Documentation of Functions by File

## File: `llm_model.py`

### Class: `LLMModel`
- **Purpose**: Abstract base class providing a common interface for language model implementations (e.g., Gemini, Qwen).
- **Key Methods**:
  - **`__init__(self)`**
    - **Description**: Initializes the base LLM model with a logger and placeholders for model and embedding objects.
    - **Parameters**: None
    - **Returns**: None
    - **Usage**: Subclasses override this to set up specific model configurations.
  - **`generate(self, prompt, schema=None)`**
    - **Description**: Generates a response from the model based on a prompt. Supports structured output if a schema is provided.
    - **Parameters**:
      - `prompt` (str): The input text to generate a response for.
      - `schema` (Optional): A schema for structured output (if supported by the model).
    - **Returns**: The generated content (str or structured output).
    - **Usage**: `model.generate("What is the capital of France?")` returns "The capital of France is Paris."
  - **`token_count(self, prompt: str) -> int`**
    - **Description**: Counts the number of tokens in a given prompt using the `tiktoken` library.
    - **Parameters**:
      - `prompt` (str): The text to tokenize.
    - **Returns**: Integer number of tokens.
    - **Usage**: `model.token_count("Hello world")` might return 2.

### Class: `GeminiModel(LLMModel)`
- **Purpose**: Implements the Gemini model from Google Generative AI.
- **Key Methods**:
  - **`__init__(self)`**
    - **Description**: Initializes the Gemini model with a specified context size (100,000 tokens) and API key from environment variables.
    - **Parameters**: None
    - **Returns**: None
    - **Usage**: Requires `GENAI_API_KEY` to be set in the environment.
  - **`token_count(self, prompt: str | None) -> int`**
    - **Description**: Overrides base method to use Gemini-specific tokenizer.
    - **Parameters**:
      - `prompt` (str | None): Text to count tokens for; returns 0 if None.
    - **Returns**: Total token count.
    - **Usage**: `gemini.token_count("Test prompt")` returns the token count specific to Gemini's tokenizer.
  - **`generate(self, prompt, schema=None)`**
    - **Description**: Extends base method with a 5-second delay (possibly for rate limiting).
    - **Parameters**: Same as base `generate`.
    - **Returns**: Generated content.
    - **Usage**: Adds a delay to base generation logic.

### Class: `QwenModel(LLMModel)`
- **Purpose**: Implements the Qwen model using LlamaCpp for local execution.
- **Key Methods**:
  - **`__init__(self)`**
    - **Description**: Initializes the Qwen model with a specific model file path and a large context size (128,000 tokens).
    - **Parameters**: None
    - **Returns**: None
    - **Usage**: Loads a pre-trained Qwen model from `./models/qwen/qwen2.5-7b-instruct-1m-q4_k_m.gguf`.
  - **`token_count(self, text: str | None) -> int`**
    - **Description**: Counts tokens using the LlamaCpp tokenizer.
    - **Parameters**:
      - `text` (str | None): Text to tokenize; returns 0 if None.
    - **Returns**: Token count.
    - **Usage**: `qwen.token_count("Sample text")` returns token count based on Qwen's tokenization.
  - **`generate(self, prompt, schema=None)`**
    - **Description**: Generates a response using the Qwen model.
    - **Parameters**: Same as base `generate`.
    - **Returns**: Generated content.
    - **Usage**: `qwen.generate("What is AI?")` invokes the Qwen model for a response.

---

## File: `data_struct.py`

### Class: `BaseData`
- **Purpose**: Base dataclass for converting objects to dictionaries.
- **Key Methods**:
  - **`to_dict(self)`**
    - **Description**: Converts the dataclass instance to a dictionary.
    - **Parameters**: None
    - **Returns**: dict
    - **Usage**: Used by subclasses for serialization.

### Class: `LineOfLogFile(BaseData)`
- **Purpose**: Represents a single line in a log file.
- **Fields**:
  - `content` (str): Line content.
  - `line_number` (int): Line number in the file.
  - `name` (str): File name.
  - `id` (int): File ID.
  - `timestamp` (datetime): When the line was recorded.
- **Key Methods**:
  - **`to_dict(self)`**
    - **Description**: Converts to a dictionary, formatting `timestamp` as ISO 8601 string.
    - **Returns**: dict
    - **Usage**: `line.to_dict()` for database insertion.

### Class: `LastLineRead(BaseData)`
- **Purpose**: Tracks the last line read for a log file.
- **Fields**:
  - `last_line_read` (int): Last line number processed.
  - `id` (int): File ID.
  - `name` (str): File name.

### Class: `LogFile`
- **Purpose**: Represents a log file with metadata and database interaction methods.
- **Key Methods**:
  - **`__init__(self, filename: str, parent: str)`**
    - **Description**: Initializes a log file with a unique ID.
    - **Parameters**:
      - `filename` (str): Path to the log file.
      - `parent` (str): Parent directory or group name.
    - **Usage**: `log = LogFile("/path/to/log.txt", "group1")`
  - **`add_file_description(self, description: str)`**
    - **Description**: Adds a description to the log file.
    - **Parameters**:
      - `description` (str): Description text.
    - **Usage**: `log.add_file_description("System logs")`
  - **`to_dict(self) -> dict`**
    - **Description**: Serializes the log file to a dictionary.
    - **Returns**: dict
    - **Usage**: For database storage.
  - **`get_total_lines(self, db: eldb) -> int`**
    - **Description**: Queries Elasticsearch for the total number of lines stored for this file.
    - **Parameters**:
      - `db` (ElasticsearchDatabase): Database instance.
    - **Returns**: Integer count of lines.
    - **Usage**: `log.get_total_lines(db)` to check stored line count.
  - **`get_snapshot(self, id: int, earliest_timestamp: datetime, start: int, size: int, db: eldb) -> str | None`**
    - **Description**: Retrieves a snapshot of log lines from Elasticsearch, sorted by line number.
    - **Parameters**:
      - `id` (int): File ID.
      - `earliest_timestamp` (datetime): Filter logs after this time.
      - `start` (int): Starting line number.
      - `size` (int): Number of lines to retrieve.
      - `db` (ElasticsearchDatabase): Database instance.
    - **Returns**: String of formatted log lines or None if empty.
    - **Usage**: `log.get_snapshot(1, datetime(2023, 1, 1), 10, 5, db)` gets 5 lines starting at line 10.

### Class: `Event`
- **Purpose**: Represents an event with a description and related files.
- **Key Methods**:
  - **`__init__(self, description: str)`**
    - **Description**: Initializes an event with a unique ID.
    - **Parameters**:
      - `description` (str): Event description.
    - **Usage**: `event = Event("Server crash at 3 PM")`
  - **`to_dict(self) -> dict`**
    - **Description**: Serializes the event to a dictionary.
    - **Returns**: dict
    - **Usage**: For database storage.

---

## File: `database.py`

### Class: `Database(ABC)`
- **Purpose**: Abstract base class defining database operations.
- **Abstract Methods**:
  - **`insert`, `single_search`, `update`, `delete`, `set_vector_store`**

### Class: `ElasticsearchDatabase(Database)`
- **Purpose**: Implements database operations using Elasticsearch.
- **Key Methods**:
  - **`__init__(self)`**
    - **Description**: Initializes the Elasticsearch client with a connection check.
    - **Usage**: `db = ElasticsearchDatabase()`
  - **`insert(self, data: dict, index: str)`**
    - **Description**: Inserts a document into the specified index.
    - **Parameters**:
      - `data` (dict): Document to insert.
      - `index` (str): Target index.
    - **Usage**: `db.insert({"content": "log line"}, "log_files")`
  - **`single_search(self, query: dict, index: str)`**
    - **Description**: Performs a single-result search.
    - **Parameters**:
      - `query` (dict): Elasticsearch query.
      - `index` (str): Target index.
    - **Returns**: List of hits (limited to 1).
    - **Usage**: `db.single_search({"match": {"id": 1}}, "log_files")`
  - **`scroll_search(self, query: dict, index: str)`**
    - **Description**: Retrieves all results using Elasticsearch’s Scroll API.
    - **Parameters**: Same as `single_search`.
    - **Returns**: List of all matching hits.
    - **Usage**: For large datasets, e.g., `db.scroll_search({"match_all": {}}, "log_files")`
  - **`update(self, id: str, data: dict, index: str)`**
    - **Description**: Updates a document by ID.
    - **Parameters**:
      - `id` (str): Document ID.
      - `data` (dict): Update data.
      - `index` (str): Target index.
    - **Usage**: `db.update("1", {"doc": {"content": "updated"}}, "log_files")`
  - **`delete(self, id: str, index: str)`**
    - **Description**: Deletes a document by ID.
    - **Parameters**: Same as `update`.
    - **Usage**: `db.delete("1", "log_files")`
  - **`set_vector_store(self, embeddings, index)`**
    - **Description**: Sets up a vector store for embeddings.
    - **Parameters**:
      - `embeddings`: Embedding model.
      - `index` (str): Index for the vector store.
    - **Returns**: `ElasticsearchStore` instance.
    - **Usage**: `db.set_vector_store(embeddings, "vector_store")`
  - **`random_sample(self, index: str, size: int)`**
    - **Description**: Returns a random sample of documents.
    - **Parameters**:
      - `index` (str): Target index.
      - `size` (int): Number of documents (max 10,000).
    - **Returns**: List of hits.
    - **Usage**: `db.random_sample("log_files", 100)`
  - **`add_alias(self, index: str, alias: str, filter: dict = None)`**
    - **Description**: Adds an alias to an index with an optional filter and returns document count.
    - **Parameters**:
      - `index` (str): Source index.
      - `alias` (str): Alias name.
      - `filter` (dict, optional): Filter for the alias.
    - **Returns**: Integer count of matching documents.
    - **Usage**: `db.add_alias("log_files", "recent_logs", {"range": {"timestamp": {"gte": "2023-01-01"}}})`
  - **`count_docs(self, index: str, filter: dict = None)`**
    - **Description**: Counts documents matching a filter.
    - **Parameters**: Same as `add_alias`.
    - **Returns**: Integer count.
    - **Usage**: `db.count_docs("log_files")`
  - **`get_unique_values_composite(self, index: str, field: str, page_size=1000, sort_order="asc")`**
    - **Description**: Retrieves all unique values for a field using composite aggregation.
    - **Parameters**:
      - `index` (str): Target index.
      - `field` (str): Field to analyze.
      - `page_size` (int): Pagination size.
      - `sort_order` (str): "asc" or "desc".
    - **Returns**: List of unique values.
    - **Usage**: `db.get_unique_values_composite("log_files", "name")`
  - **`get_unique_values(self, index: str, field: str, size=1000, sort_order="asc")`**
    - **Description**: Retrieves unique values using terms aggregation (limited to `size`).
    - **Parameters**: Similar to `get_unique_values_composite`.
    - **Returns**: List of unique values.
    - **Usage**: `db.get_unique_values("log_files", "name", 500)`

---

## File: `container_manger.py`

### Class: `ContainerManager(ABC)`
- **Purpose**: Abstract base class for container management.

### Class: `DockerManager(ContainerManager)`
- **Purpose**: Manages Docker containers for services like Elasticsearch and Kibana.
- **Key Methods**:
  - **`__init__(self)`**
    - **Description**: Initializes the Docker client.
    - **Usage**: `manager = DockerManager()`
  - **`start_container(self, name: str, image: str, network: str, volume_setup: dict, ports: dict, env_vars: dict, detach: bool, remove: bool)`**
    - **Description**: Starts a Docker container with specified configurations.
    - **Parameters**:
      - `name` (str): Container name.
      - `image` (str): Docker image.
      - `network` (str): Network name.
      - `volume_setup` (dict): Volume bindings.
      - `ports` (dict): Port mappings.
      - `env_vars` (dict): Environment variables.
      - `detach` (bool): Run in detached mode.
      - `remove` (bool): Auto-remove on stop.
    - **Returns**: Container ID or None on failure.
    - **Usage**: Starts Elasticsearch or Kibana containers.
  - **`stop_container(self)`**
    - **Description**: Placeholder for stopping a container (not implemented).
    - **Usage**: Needs implementation.
  - **`get_container_status(self)`**
    - **Description**: Placeholder for checking container status (not implemented).
    - **Usage**: Needs implementation.
  - **`_remove_container(self, container_name: str)`**
    - **Description**: Removes a container by name if it exists.
    - **Parameters**:
      - `container_name` (str): Name of the container.
    - **Usage**: Cleans up before starting a new container.
  - **`_create_network(self, network_name: str)`**
    - **Description**: Creates a Docker network if it doesn’t exist.
    - **Parameters**:
      - `network_name` (str): Network name.
    - **Usage**: Ensures network availability.
  - **`_create_volume(self, volume_name: str)`**
    - **Description**: Creates a Docker volume if it doesn’t exist.
    - **Parameters**:
      - `volume_name` (str): Volume name.
    - **Usage**: Sets up persistent storage.
  - **`_pull_image(self, image: str)`**
    - **Description**: Pulls a Docker image if not present locally.
    - **Parameters**:
      - `image` (str): Image name (e.g., "elasticsearch:8.17.1").
    - **Usage**: Ensures the image is available.
  - **`_start_daemon(self)`**
    - **Description**: Starts the Docker daemon (supports macOS with Colima).
    - **Returns**: Docker client instance.
    - **Usage**: Configures Docker environment based on OS.

---

## File: `logger.py`

### Class: `Logger`
- **Purpose**: Singleton class for logging to file and console.
- **Key Methods**:
  - **`__init__(self, name: str = cfg.LOGGER_NAME, log_file: str = cfg.LOG_FILE)`**
    - **Description**: Initializes logging with DEBUG level to file and INFO to console.
    - **Parameters**:
      - `name` (str): Logger name.
      - `log_file` (str): Log file path.
    - **Usage**: `logger = Logger()`
  - **`info(self, message: str)`**, **`debug(self, message: str)`**, **`warning(self, message: str)`**, **`error(self, message: str)`**, **`critical(self, message: str)`**
    - **Description**: Logs messages at respective levels.
    - **Parameters**:
      - `message` (str): Log message.
    - **Usage**: `logger.info("Process started")`

---

## File: `collector.py`

### Class: `Collector`
- **Purpose**: Collects log files and events, inserting them into Elasticsearch.
- **Key Methods**:
  - **`__init__(self, dir: str)`**
    - **Description**: Initializes with a directory to collect logs from.
    - **Parameters**:
      - `dir` (str): Directory path.
    - **Usage**: `collector = Collector("../logs/")`
  - **`collect_logs(self, directory: str) -> list[LogFile]`**
    - **Description**: Recursively collects log files, skipping hidden files.
    - **Parameters**:
      - `directory` (str): Root directory.
    - **Returns**: List of `LogFile` objects.
    - **Usage**: Gathers all logs in a directory tree.
  - **`collect_events(self, file: str) -> list[Event]`**
    - **Description**: Reads events from a file, splitting by empty lines.
    - **Parameters**:
      - `file` (str): Event file path.
    - **Returns**: List of `Event` objects.
    - **Usage**: `events = collector.collect_events("events.txt")`
  - **`insert_events_to_db(self, db: Database, events: list[Event])`**
    - **Description**: Inserts events into Elasticsearch, clearing old records first.
    - **Parameters**:
      - `db` (Database): Database instance.
      - `events` (list[Event]): Events to insert.
    - **Usage**: Stores event data.
  - **`insert_logs_to_db(self, db: Database, files: list)`**
    - **Description**: Inserts log lines into Elasticsearch, tracking last read line (memory-intensive).
    - **Parameters**:
      - `db` (Database): Database instance.
      - `files` (list): List of log files.
    - **Usage**: For smaller log files; loads entire file into memory.
  - **`insert_very_large_logs_into_db(self, db: ElasticsearchDatabase, files: list[LogFile])`**
    - **Description**: Efficiently inserts large log files using bulk operations, supporting appends.
    - **Parameters**: Same as `insert_logs_to_db`.
    - **Usage**: Preferred for large logs; processes in batches of 1000 lines.
  - **`_get_last_line_read(self, log_file: LogFile, db: Database) -> int`**
    - **Description**: Retrieves the last line read for a log file.
    - **Parameters**:
      - `log_file` (LogFile): Log file object.
      - `db` (Database): Database instance.
    - **Returns**: Last line number or 0 if not found.
    - **Usage**: Ensures incremental processing.
  - **`_save_last_line_read(self, log_file: LogFile, db: Database, line_number: int)`**
    - **Description**: Saves the last line read to the database.
    - **Parameters**:
      - `log_file` (LogFile): Log file object.
      - `db` (Database): Database instance.
      - `line_number` (int): Line number to save.
    - **Usage**: Updates tracking information.

---

## File: `rag_manager.py`

### Class: `RAGManager`
- **Purpose**: Manages Retrieval-Augmented Generation (RAG) for document context.
- **Key Methods**:
  - **`__init__(self, name: str, db: ElasticsearchDatabase, embeddings, model: LLMModel, multi_threading: bool = False)`**
    - **Description**: Initializes RAG with a vector store in Elasticsearch.
    - **Parameters**:
      - `name` (str): Identifier for this RAG instance.
      - `db` (ElasticsearchDatabase): Database instance.
      - `embeddings`: Embedding model.
      - `model` (LLMModel): Language model.
      - `multi_threading` (bool): Enable multi-threaded loading.
    - **Usage**: `rag = RAGManager("docs", db, embeddings, model)`
  - **`retrieve(self, prompt: str) -> str`**
    - **Description**: Retrieves relevant documents and constructs a contextual prompt.
    - **Parameters**:
      - `prompt` (str): Query to retrieve context for.
    - **Returns**: Contextual prompt string.
    - **Usage**: `rag.retrieve("What is AI?")` returns prompt with relevant context.
  - **`update_rag_from_directory(self, directory: str, db: ElasticsearchDatabase, file_extension: str = "md")`**
    - **Description**: Updates the vector store with documents from a directory.
    - **Parameters**:
      - `directory` (str): Directory path.
      - `db` (ElasticsearchDatabase): Database instance.
      - `file_extension` (str): File type to load (default "md").
    - **Usage**: `rag.update_rag_from_directory("./docs/", db)` loads markdown files.

---

## Usage Notes
- **Dependencies**: Ensure Elasticsearch, Docker, and required Python libraries (`langchain`, `tiktoken`, etc.) are installed.
- **Configuration**: Adjust `config.py` settings (e.g., API keys, paths) before running.
- **Scalability**: Use `insert_very_large_logs_into_db` for large logs to avoid memory issues.
- **Error Handling**: Most methods include logging and exit on critical errors; handle exceptions as needed in production.
