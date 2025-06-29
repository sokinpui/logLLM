# Database Utility (`database.py`)

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
  - **`scroll_search(self, query: dict, index: str) -> list`**:
    - Retrieves _all_ documents matching a query using the Elasticsearch Scroll API, handling pagination automatically.
    - The `query` dictionary should contain the desired `size` for the initial batch.
    - Clears the scroll context upon completion or error.
  - **`update(self, id: str, data: dict, index: str)`**: Updates an existing document by its ID.
  - **`delete(self, id: str, index: str)`**: Deletes a document by its ID.
  - **`set_vector_store(self, embeddings, index) -> ElasticsearchStore`**: Configures and returns a `langchain_elasticsearch.ElasticsearchStore` instance for vector similarity searches.
  - **`random_sample(self, index: str, size: int)`**: Retrieves a random sample of documents using `function_score` with `random_score`.
  - **`add_alias(self, index: str, alias: str, filter: dict = None)`**: Adds an alias to an index, optionally with a filter, and returns the count of documents matching the filter.
  - **`count_docs(self, index: str, filter: dict = None)`**: Returns the count of documents in an index, optionally matching a filter.
  - **`get_unique_values_composite(self, index: str, field: str, page_size=1000, sort_order="asc") -> list`**: Retrieves all unique values from a field using composite aggregation (handles pagination for large cardinality fields).
  - **`get_unique_values(self, index: str, field: str, size=1000, sort_order="asc") -> list`**: Retrieves unique values using terms aggregation (simpler but potentially limited by `size`).
  - **`scroll_and_process_batches(self, index: str, query: Dict[str, Any], batch_size: int, process_batch_func: Callable[[List[Dict[str, Any]]], bool], source_fields: Optional[List[str]] = None, scroll_context_time: str = "5m") -> Tuple[int, int]`**:
    - Scrolls through documents matching a query and processes them in batches using a provided callback function (`process_batch_func`).
    - The callback should return `True` to continue scrolling, `False` to stop early.
    - `source_fields` can specify which fields to retrieve.
    - Returns a tuple: `(total_documents_processed_by_callback, estimated_total_hits_matching_query)`.
  - **`bulk_operation(self, actions: List[Dict[str, Any]], raise_on_error: bool = False, **kwargs) -> Tuple[int, List[Dict[str, Any]]]`\*\*:
    - Performs a bulk operation (index, update, delete) using pre-formatted actions following the Elasticsearch bulk API syntax.
    - Uses `elasticsearch.helpers.bulk`.
    - `kwargs` can include `request_timeout` (defaults to 120s).
    - Returns a tuple: `(number_of_successes, list_of_errors)`.
  - **`bulk_index(self, actions: List[Dict[str, Any]], index: str, raise_on_error: bool = False) -> Tuple[int, List[Dict[str, Any]]]`**:
    - [DEPRECATED - Use `bulk_operation` for more flexibility] Simple bulk indexing wrapper.
  - **`get_sample_lines(self, index: str, field: str, sample_size: int, query: Optional[Dict[str, Any]] = None) -> List[str]`**:
    - Retrieves a random sample of values from a _specific field_ within documents, optionally matching a `query`.
    - Uses `function_score` with `random_score` for sampling.
    - Returns a list of string values from the specified field.
