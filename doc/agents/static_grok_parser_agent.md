# Static Grok Parser Agent (`static_grok_parser_agent.py`)

## File: `src/logllm/agents/static_grok_parser/__init__.py`

### Overview

The `StaticGrokParserAgent` is a LangGraph-based agent responsible for orchestrating the parsing of multiple log groups within Elasticsearch. It uses predefined Grok patterns from a YAML file to structure raw log data. This agent manages the entire workflow for all discovered log groups, processing each file within those groups incrementally.

### State Definitions

- **`LogFileProcessingState(TypedDict)`**: Tracks the state for processing a single log file during a run.
  - `log_file_id`, `group_name`, `grok_pattern_string`
  - `last_line_parsed_by_grok`, `current_total_lines_by_collector` (from persistent status)
  - `max_line_processed_this_session`, `new_lines_scanned_this_session`
  - `parsed_actions_batch`, `unparsed_actions_batch` (for ES bulk indexing)
  - `status_this_session`, `error_message_this_session`
- **`StaticGrokParserOrchestratorState(TypedDict)`**: Defines the overall state for the orchestrator agent.
  - `all_group_names_from_db`: List of all group names found in `group_infos`.
  - `current_group_processing_index`: Iterator for processing groups.
  - `overall_group_results`: A dictionary where keys are group names. Each value is a dictionary representing the summarized state for that group after processing, including its status, pattern used, and a summary of files processed (which contains `LogFileProcessingState` for each file).
  - `orchestrator_status`: Overall status of the agent run (e.g., "pending", "processing_groups", "completed").
  - `orchestrator_error_messages`: List of any orchestrator-level errors.

### Core Workflow (LangGraph Orchestrator Nodes and Edges)

1.  **`_orchestrator_start_node` (Node)**

    - **Action**: Fetches all log group names from the `group_infos` index using `ElasticsearchDataService`. Initializes orchestrator state.
    - **Next**: Conditional edge `_orchestrator_should_process_more_groups`.

2.  **`_orchestrator_should_process_more_groups` (Conditional Edge)**

    - **Logic**: If no groups were found, routes to `END`. If `current_group_processing_index` is less than total groups, routes to `initialize_group_processing`. Otherwise, routes to `END`.

3.  **`_orchestrator_initialize_group_processing_node` (Node)**

    - **Action**: For the current group:
      - Determines source, parsed, and unparsed index names using `cfg` utility functions.
      - Fetches the Grok pattern string for the group from the YAML file via `GrokPatternService`.
      - Attempts to compile the Grok pattern.
      - Fetches all log file IDs within this group from its source index.
      - Initializes a sub-state for this group within `overall_group_results`. Sets group status (e.g., "failed_no_pattern", "failed_pattern_compile", "completed_no_files", "processing_files").
    - **Next**: Conditional edge `_orchestrator_check_group_initialization_status`.

4.  **`_orchestrator_check_group_initialization_status` (Conditional Edge)**

    - **Logic**: Based on the `group_status` set in the previous node:
      - If status indicates failure (no pattern, compile error) or no files, routes to `advance_group_processing`.
      - If status is "processing_files", routes to `process_files_for_group`.

5.  **`_orchestrator_process_files_for_group_node` (Node)**

    - **Action**: This is the main workhorse node for a single group.
      - Retrieves the compiled Grok pattern and derived field definitions for the group.
      - Iterates through each `log_file_id` belonging to the current group:
        - Fetches persistent Grok parse status and collector status for the file.
        - Skips the file if already parsed up to the collector's reported line count.
        - Resets Grok's line count if collector reports 0 lines but Grok parsed previously.
        - Uses `ElasticsearchDataService.scroll_and_process_raw_log_lines` to fetch new log lines from the raw log index (`log_<group_name>`) for the current file, starting after `last_line_parsed_by_grok`.
        - The `scroll_callback_for_file` (defined within this node) is executed for each batch of scrolled lines:
          - For each log line:
            - Attempts parsing using `GrokParsingService.parse_line`.
            - If successful, processes derived fields using `DerivedFieldProcessor`.
            - Prepares and adds the parsed document to a batch for `parsed_log_<group_name>`.
            - If parsing fails, prepares and adds the original document to a batch for `unparsed_log_<group_name>`.
          - Flushes parsed/unparsed batches to Elasticsearch via `ElasticsearchDataService.bulk_index_formatted_actions` if batch size is reached.
        - Flushes any remaining documents in batches after scrolling for the file is complete.
        - Saves the updated Grok parse status for the file (max line processed, collector total, etc.) using `ElasticsearchDataService.save_grok_parse_status_for_file`.
        - Updates the `LogFileProcessingState` for this file within the group's summary in `overall_group_results`.
      - Sets the current group's status to "completed".
    - **Next**: `advance_group_processing`.

6.  **`_orchestrator_advance_group_node` (Node)**
    - **Action**: Increments `current_group_processing_index`. If all groups processed, sets `orchestrator_status` to "completed".
    - **Next**: Conditional edge `_orchestrator_should_process_more_groups` (to loop or end).

### Key Internal Services

- **`ElasticsearchDataService`**: Handles all Elasticsearch interactions: fetching group info, file IDs, raw log lines, status documents, and bulk indexing parsed/unparsed data and status updates.
- **`GrokPatternService`**: Loads Grok patterns and derived field definitions from the specified YAML file and provides compiled Grok instances.
- **`GrokParsingService`**: Performs the Grok pattern matching on individual log lines.
- **`DerivedFieldProcessor`**: Processes fields extracted by Grok to create new derived fields based on format string definitions in the YAML file.

### Key Methods

- **`__init__(self, db: ElasticsearchDatabase, grok_patterns_yaml_path: str)`**
  - Initializes the agent, its services, and compiles the LangGraph orchestrator workflow by calling `_build_orchestrator_graph()`.
- **`run(self, clear_records_for_groups: Optional[List[str]] = None, clear_all_group_records: bool = False) -> StaticGrokParserOrchestratorState`**
  - The main entry point for executing the static Grok parsing for all groups.
  - Optionally clears previously parsed data and status entries for specified groups or all groups before starting the parsing run by calling `_clear_group_data`.
  - Invokes the compiled LangGraph with an initial orchestrator state.
  - Returns the final `StaticGrokParserOrchestratorState` containing detailed results for each group and overall status.
- **`_clear_group_data(self, group_name: str)`**:
  - Helper method to delete `parsed_log_<group_name>`, `unparsed_log_<group_name>` indices and all `static_grok_parse_status` entries for a given group.
- **Node Methods** (e.g., `_orchestrator_start_node`, `_orchestrator_process_files_for_group_node`, etc.): Implement the logic for each step (node) in the LangGraph.
- **Conditional Edge Methods** (e.g., `_orchestrator_should_process_more_groups`, etc.): Implement the decision logic for routing the workflow.
- **`_build_orchestrator_graph(self) -> CompiledGraph`**: Defines the LangGraph structure.
