# Scroll Grok Parser Agent (`es_parser_agent.py`)

## File: `src/logllm/agents/es_parser_agent.py`

### Overview

This document describes the `ScrollGrokParserAgent` and its state, which is a lower-level agent focused on parsing log data from Elasticsearch using Grok patterns and bulk indexing.

### Class: `ScrollGrokParserState(TypedDict)`

- **Purpose**: Defines the configuration and result structure for the `ScrollGrokParserAgent`, which performs the actual data processing and indexing within Elasticsearch.
- **Fields**:
  - `source_index` (str): The ES index containing the raw log documents to be parsed.
  - `target_index` (str): The ES index where successfully parsed/structured documents will be written.
  - `failed_index` (str): The ES index where documents that failed parsing (or all documents during fallback) will be written.
  - `grok_pattern` (str): The Grok pattern string to be applied to the source documents.
  - `field_to_parse` (str): The name of the field within the source documents that contains the raw log line text (e.g., "content").
  - `source_query` (Optional[Dict]): An optional Elasticsearch query DSL dictionary to filter which documents from the `source_index` should be processed. Defaults to `match_all`.
  - `fields_to_copy` (Optional[List[str]]): An optional list of field names to copy directly from the source document to the target/failed document if they don't already exist after parsing.
  - `batch_size` (int): The number of documents to process and index in each bulk request.
  - `is_fallback_run` (bool): A flag indicating whether this agent run is operating in "fallback" mode (using a generic pattern and writing all source docs to `failed_index`) or "parse" mode (using the provided `grok_pattern` and writing successes to `target_index`, failures to `failed_index`).
  - _Result Fields (Populated by the agent's `run` method)_:
    - `processed_count` (int): Total number of documents scrolled from the source index.
    - `successfully_indexed_count` (int): Number of documents successfully parsed and indexed into the `target_index`.
    - `failed_indexed_count` (int): Number of documents that failed parsing or were part of a fallback run, successfully indexed into the `failed_index`.
    - `parse_error_count` (int): Number of documents that failed the Grok pattern match during a non-fallback run.
    - `index_error_count` (int): Number of errors encountered during Elasticsearch bulk indexing operations (for both target and failed indices).
    - `status` (str): The final status of the agent run ('completed', 'failed').

### Class: `ScrollGrokParserAgent`

- **Purpose**: A lower-level agent responsible for the core task of iterating through documents in a source Elasticsearch index, applying a given Grok pattern (or handling fallback), and indexing the results into appropriate target or failed indices using efficient bulk operations.
- **Key Methods**:
  - **`__init__(self, db: ElasticsearchDatabase)`**
    - **Description**: Initializes the agent with an `ElasticsearchDatabase` instance.
  - **`run(self, state: ScrollGrokParserState) -> ScrollGrokParserState`**
    - **Description**: The main execution method. It takes the configuration state, initializes internal counters and batches, compiles the Grok pattern (if not a fallback run), then uses `db.scroll_and_process_batches` to iterate through source documents. The `_process_batch` method is used as the callback. Finally, it flushes any remaining documents in the internal batches and returns the state updated with processing counts and status.
    - **Parameters**: `state` (ScrollGrokParserState): The configuration defining the source/target indices, pattern, batch size, etc.
    - **Returns**: (ScrollGrokParserState): The input state updated with the results (`processed_count`, `successfully_indexed_count`, `failed_indexed_count`, `parse_error_count`, `index_error_count`, `status`).
  - **`_initialize_grok(self, pattern: str) -> bool`**:
    - **Description**: Attempts to compile the provided Grok pattern string using `pygrok.Grok`. Stores the compiled instance internally.
    - **Returns**: (bool): `True` if compilation succeeds, `False` otherwise.
  - **`_process_single_hit(self, hit: Dict[str, Any], state: ScrollGrokParserState) -> Literal["success", "parse_failed", "skip"]`**:
    - **Description**: Processes a single document (`hit`) retrieved from Elasticsearch. If `is_fallback_run` is True, it immediately adds the original document to the failed batch. Otherwise, it attempts to match the `field_to_parse` against the compiled Grok pattern. If successful, it prepares the parsed document (copying extra fields if needed) and adds it to the success batch. If it fails, it adds the original document to the failed batch.
    - **Returns**: (`Literal["success", "parse_failed", "skip"]`): Status indicating the outcome for this hit.
  - **`_process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool`**:
    - **Description**: Callback function used by `db.scroll_and_process_batches`. It iterates through the provided list of `hits`, calling `_process_single_hit` for each. It updates the agent's internal `_parse_error_count`. If the internal success or failed batches reach the configured `batch_size`, it triggers the corresponding `_flush_..._batch` method.
    - **Returns**: (bool): Always returns `True` to signal that scrolling should continue.
  - **`_flush_success_batch(self, target_index: str)`**:
    - **Description**: Takes the documents accumulated in the internal success batch, formats them as Elasticsearch "update" actions (with `doc_as_upsert: True`), and performs a bulk operation to index them into the `target_index`. Updates `_successfully_indexed_count` and `_index_error_count`. Clears the internal success batch.
  - **`_flush_failed_batch(self, failed_index: str)`**:
    - **Description**: Takes the documents accumulated in the internal failed/fallback batch, formats them as Elasticsearch "index" actions (preserving the original document structure under `original_source` and adding a `failure_reason`), and performs a bulk operation to index them into the `failed_index`. Updates `_failed_indexed_count` and `_index_error_count`. Clears the internal failed batch.
