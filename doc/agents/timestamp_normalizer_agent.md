# Timestamp Normalizer Agent (`timestamp_normalizer_agent.py`)

## File: `src/logllm/agents/timestamp_normalizer/__init__.py`

### Overview

The `TimestampNormalizerAgent` is a LangGraph-based agent designed to process parsed log data stored in Elasticsearch (`parsed_log_<group_name>` indices). Its primary functions are to:

1.  **Normalize Timestamps**: Identify, parse, and convert various timestamp formats found in log data into a standardized UTC ISO 8601 format, storing this in the `@timestamp` field.
2.  **Remove Timestamp Field**: Optionally, remove the `@timestamp` field from documents.

This agent operates directly on the `parsed_log_<group_name>` indices, modifying them in-place for the "normalize" action or field removal.

### State Definitions

- **`TimestampNormalizerGroupState(TypedDict)`**: Tracks the state for processing a single group.

  - `group_name` (str): Name of the group being processed.
  - `parsed_log_index` (str): The `parsed_log_<group_name>` index.
  - `status_this_run` (str): Status for this group (e.g., "pending", "normalizing", "completed").
  - `error_message_this_run` (Optional[str]): Any error encountered for this group.
  - `documents_scanned_this_run` (int): Number of documents considered for processing.
  - `documents_updated_this_run` (int): Number of documents successfully updated (normalized or field removed).
  - `timestamp_normalization_errors_this_run` (int): Count of errors during timestamp parsing/normalization attempts (for "normalize" action).

- **`TimestampNormalizerOrchestratorState(TypedDict)`**: Defines the overall state for the orchestrator.
  - `action_to_perform` (str): `"normalize"` or `"remove_field"`.
  - `target_group_names` (Optional[List[str]]): Specific groups to process; `None` means all groups.
  - `limit_per_group` (Optional[int]): Max documents to process per group (for testing).
  - `batch_size` (int): Batch size for Elasticsearch operations.
  - `all_group_names_from_db` (List[str]): All groups found if `target_group_names` is `None`.
  - `groups_to_process_resolved` (List[str]): The actual list of groups the agent will iterate over.
  - `current_group_processing_index` (int): Iterator for groups.
  - `overall_group_results` (Dict[str, TimestampNormalizerGroupState]): Final state of each processed group.
  - `orchestrator_status` (str): Overall status (e.g., "pending", "completed").
  - `orchestrator_error_messages` (List[str]): Orchestrator-level errors.

### Core Workflow (LangGraph Orchestrator Nodes and Edges)

1.  **`_orchestrator_start_node` (Node)**

    - **Action**: Determines the list of `groups_to_process_resolved` based on `target_group_names` (if provided) or by fetching all group names from `group_infos` index (if `target_group_names` is `None`). Initializes orchestrator state.
    - **Next**: Conditional edge `_orchestrator_should_continue_processing_groups`.

2.  **`_orchestrator_should_continue_processing_groups` (Conditional Edge)**

    - **Logic**: If no groups to process, routes to `END`. If `current_group_processing_index` is less than total resolved groups, routes to `initialize_group`. Otherwise, routes to `END`.

3.  **`_orchestrator_initialize_group_node` (Node)**

    - **Action**: For the current group:
      - Determines the `parsed_log_index` (e.g., `parsed_log_<group_name>`).
      - Checks if this index exists. If not, sets group status to "failed_index_not_found".
      - Initializes a `TimestampNormalizerGroupState` for this group within `overall_group_results`.
    - **Next**: Conditional edge `_check_group_initialization_status`.

4.  **`_check_group_initialization_status` (Conditional Edge)**

    - **Logic**: If group initialization failed (e.g., index not found), routes to `advance_group`. Otherwise, routes to `process_group_action`.

5.  **`_process_group_node` (Node)**

    - **Action**: Processes the current group based on `action_to_perform`.
      - Uses `TimestampESDataService.scroll_and_process_documents` to iterate through documents in the `parsed_log_index` for the current group.
      - A `batch_callback` function is defined within this node:
        - If `action == "normalize"`:
          - For each document, it retrieves the value from the original timestamp field (default: "timestamp").
          - Uses `TimestampNormalizationService.normalize_timestamp_value` to parse and convert it to a UTC ISO 8601 string.
          - If successful and different from existing `@timestamp` (or `@timestamp` doesn't exist), an update action is prepared to set the `@timestamp` field.
          - Tracks normalization errors.
        - If `action == "remove_field"`:
          - For each document, if the target field (`@timestamp`) exists, an update action (using ES script) is prepared to remove it.
        - Collected update actions are sent to Elasticsearch in batches via `TimestampESDataService.bulk_update_documents`.
      - Updates the group's state (`documents_scanned_this_run`, `documents_updated_this_run`, `timestamp_normalization_errors_this_run`, `status_this_run`) in `overall_group_results`.
    - **Next**: `advance_group`.

6.  **`_orchestrator_advance_group_node` (Node)**
    - **Action**: Increments `current_group_processing_index`. If all groups processed, sets `orchestrator_status` to "completed".
    - **Next**: Conditional edge `_orchestrator_should_continue_processing_groups` (to loop or end).

### Key Internal Services

- **`TimestampESDataService`**: Handles Elasticsearch interactions: fetching group names, checking index existence, scrolling documents, and bulk updating documents.
- **`TimestampNormalizationService`**: Contains the core logic for parsing various timestamp formats (string, epoch int/float) and converting them to a standardized UTC ISO 8601 string using `dateutil.parser`.

### Key Methods

- **`__init__(self, db: ElasticsearchDatabase)`**
  - Initializes the agent, its services, and compiles the LangGraph orchestrator workflow by calling `_build_graph()`.
- **`run(self, action: str, target_groups: Optional[List[str]] = None, limit_per_group: Optional[int] = None, batch_size: int = DEFAULT_BATCH_SIZE_NORMALIZER) -> TimestampNormalizerOrchestratorState`**
  - The main entry point for executing the timestamp normalization or field removal process.
  - `action`: Must be "normalize" or "remove_field".
  - `target_groups`: List of specific group names to process. If `None`, all groups are processed.
  - `limit_per_group`: Optional limit on documents processed per group.
  - `batch_size`: Batch size for Elasticsearch operations.
  - Invokes the compiled LangGraph with an initial state derived from these parameters.
  - Returns the final `TimestampNormalizerOrchestratorState` containing results for each group and overall status.
- **Node Methods** (e.g., `_orchestrator_start_node`, `_process_group_node`, etc.): Implement the logic for each step (node) in the LangGraph.
- **Conditional Edge Methods** (e.g., `_orchestrator_should_continue_processing_groups`, etc.): Implement the decision logic for routing the workflow.
- **`_build_graph(self) -> CompiledGraph`**: Defines the LangGraph structure.
