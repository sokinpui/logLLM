# Error Analysis Pipeline Agent (`error_analysis_pipeline_agent.py`)

## File: `src/logllm/agents/error_analysis_pipeline_agent.py`

### Overview

The `ErrorAnalysisPipelineAgent` is a LangGraph-based orchestrator for the entire error analysis and summarization workflow. It manages the flow of data between various atomic agents (`ErrorClustererAgent`, `ErrorSummarizerAgent`) and handles decision-making within the pipeline.

For a general overview of the error analysis pipeline, related configurations, and data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

### State Definition: `ErrorAnalysisPipelineState(TypedDict)`

This `TypedDict` defines the state managed by the LangGraph workflow within the `ErrorAnalysisPipelineAgent`. It holds configuration, input data, intermediate results, and final outputs.

- **Key Input Fields**:
  - `group_name` (str): The log group being analyzed.
  - `es_query_for_errors` (Dict[str, Any]): Elasticsearch query to fetch initial error logs (e.g., from `normalized_parsed_log_<group_name>`).
  - `clustering_params` (Dict[str, Any]): Parameters for the `ErrorClustererAgent` (e.g., `method`, `eps`, `min_samples`).
  - `sampling_params` (Dict[str, Any]): Parameters for sampling logs for summarization (e.g., `max_samples_per_cluster`, `max_samples_unclustered`).
- **Key Intermediate/Dynamic Fields**:
  - `error_log_docs` (List[LogDocument]): Initially fetched error logs. These are stored in a temporary working index (e.g., `temp_error_analysis_<group_name>`) for the duration of the run.
  - `clusters` (Optional[List[ClusterResult]]): Output from the `ErrorClustererAgent`.
  - `current_cluster_index` (int): Used for iterating through clusters if clustering is active.
  - `current_samples_for_summary` (List[LogDocument]): Samples prepared for the `ErrorSummarizerAgent`.
- **Key Output Fields**:
  - `generated_summaries` (List[ErrorSummarySchema]): List of Pydantic `ErrorSummarySchema` objects produced by the `ErrorSummarizerAgent`.
  - `status_messages` (List[str]): A log of actions and messages accumulated during the pipeline's execution.

### Core Workflow (LangGraph Nodes and Edges)

1.  **`fetch_initial_errors_node` (Node)**

    - **Action**:
      - Determines the temporary working Elasticsearch index name (e.g., `temp_error_analysis_<group_name>`) using `cfg.get_error_analysis_working_index()`.
      - **Deletes this working index if it exists** to ensure a clean run.
      - Queries the primary _normalized parsed_ log data index (e.g., `normalized_parsed_log_<group_name>`) using the `es_query_for_errors` from the pipeline state. This query includes filters for log levels, time window, and a maximum number of initial errors.
      - Bulk-indexes the fetched raw error logs into the (new) temporary working index.
      - Populates `error_log_docs` in the pipeline state with the fetched documents.
    - **Next**: `cluster_errors_node`.

2.  **`cluster_errors_node` (Node)**

    - **Action**: If `error_log_docs` is not empty, calls `ErrorClustererAgent.run()` with the fetched logs and `clustering_params` from the state.
    - **Output**: Populates `clusters` (list of `ClusterResult`) and initializes `current_cluster_index` in the state.
    - **Next**: Conditional edge `_decide_clustering_outcome`.

3.  **`_decide_clustering_outcome` (Conditional Edge)**

    - **Logic**:
      - Checks if the `clustering_params['method']` is 'none'. If so, or if `clusters` is empty or contains only noise (all cluster_id = -1), it routes to `summarize_unclustered_fallback_node`.
      - Otherwise (meaningful clusters exist), it routes to `check_cluster_loop_condition`.

4.  **`check_cluster_loop_condition` (Node & Conditional Edge)**

    - **Node**: A simple pass-through node that doesn't modify state.
    - **Edge Logic (`_check_cluster_loop_condition_node`)**:
      - Checks if `current_cluster_index` is less than the total number of `clusters`.
      - If true (more clusters to process), routes to `sample_and_summarize_cluster_node`.
      - If false (all clusters processed), routes to `store_summaries_node`.

5.  **`sample_and_summarize_cluster_node` (Node)**

    - **Action**:
      - Retrieves the current cluster data using `clusters[current_cluster_index]`.
      - Takes example logs from `cluster['example_log_docs']` (already sampled by `ErrorClustererAgent`, possibly further limited by `sampling_params['max_samples_per_cluster']`).
      - Calls `ErrorSummarizerAgent.run()` with these samples and relevant `cluster_context` (representative message, count, timestamps from the `ClusterResult`).
      - Appends the returned `ErrorSummarySchema` object (if any) to `generated_summaries` in the state.
      - Increments `current_cluster_index`.
    - **Next**: `check_cluster_loop_condition` (to loop back or finish).

6.  **`summarize_unclustered_fallback_node` (Node)**

    - **Action**:
      - If `error_log_docs` is not empty, takes a random sample from all `error_log_docs` (limited by `sampling_params['max_samples_unclustered']`).
      - Calls `ErrorSummarizerAgent.run()` with these samples (no specific `cluster_context`).
      - Appends the returned `ErrorSummarySchema` object (if any) to `generated_summaries`.
    - **Next**: `store_summaries_node`.

7.  **`store_summaries_node` (Node)**
    - **Action**: Iterates through the `ErrorSummarySchema` objects in `generated_summaries` and inserts each (as a Pydantic model dumped to a dictionary) into the `cfg.INDEX_ERROR_SUMMARIES` Elasticsearch index.
    - **Next**: `END` (pipeline finishes).

### Key Methods

- **`__init__(self, db: ElasticsearchDatabase, llm_model: LLMModel, prompts_manager: PromptsManager)`**

  - Initializes the pipeline agent with its dependencies:
    - `db`: An `ElasticsearchDatabase` instance.
    - `llm_model`: An `LLMModel` instance (used by sub-agents for embeddings and generation).
    - `prompts_manager`: A `PromptsManager` instance (used by `ErrorSummarizerAgent`).
  - Instantiates `ErrorClustererAgent` and `ErrorSummarizerAgent`.
  - Calls `_build_graph()` to compile the internal LangGraph workflow.

- **`run(self, initial_state_input: Dict[str, Any]) -> ErrorAnalysisPipelineState`**

  - **Description**: The main entry point for executing the error analysis pipeline.
  - **Parameters**: `initial_state_input` (Dict[str, Any]): A dictionary containing the initial configuration for the pipeline, matching the structure of `ErrorAnalysisPipelineState`.
  - **Returns**: (ErrorAnalysisPipelineState): The final state of the graph after execution, including status messages and generated summaries.

- **Node Methods** (e.g., `_fetch_initial_errors_node`, `_cluster_errors_node`, etc.)

  - These private methods implement the logic for each step (node) in the LangGraph.

- **Conditional Edge Methods** (e.g., `_decide_clustering_outcome`, `_check_cluster_loop_condition_node`)

  - These private methods implement the decision logic for routing the workflow between nodes based on the current state.

- **`_build_graph(self) -> CompiledGraph`**
  - Defines the LangGraph structure by adding nodes and edges (including conditional edges) as described in the "Core Workflow" section.
  - Returns the compiled LangGraph.
