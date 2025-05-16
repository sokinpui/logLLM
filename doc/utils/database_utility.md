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
  - **`scroll_search(self, query: dict, index: str)`**: Retrieves _all_ documents matching a query using the Elasticsearch Scroll API, handling pagination automatically.
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
  - **`get_sample_lines(...) -> List[str]`**: Retrieves a random sample of values from a _specific field_ within documents matching an optional query. Uses `function_score`.
