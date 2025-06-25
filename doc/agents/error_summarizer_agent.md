# Error Summarizer Agent (`error_summarizer_agent.py`)

## File: `src/logllm/agents/error_summarizer/__init__.py`

### Overview

The `ErrorSummarizerAgent` is a LangGraph-based agent designed to analyze error logs from Elasticsearch. It orchestrates a pipeline that includes fetching error logs based on specified criteria, generating embeddings for these logs, clustering them to identify common error types, sampling representative logs from each cluster (or from unclustered data), and finally, using a Large Language Model (LLM) to generate structured summaries for these error groups. The summaries are then stored in a designated Elasticsearch index.

For a general overview of the error analysis pipeline, related configurations, and shared data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

### State Definition: `ErrorSummarizerAgentState(TypedDict)`

This `TypedDict` defines the state managed by the LangGraph workflow within the `ErrorSummarizerAgent`.

- **Key Input Fields**:

  - `group_name` (str): The log group to analyze (e.g., "apache", "system").
  - `start_time_iso` (str): Start of the time window for log fetching (ISO 8601 format).
  - `end_time_iso` (str): End of the time window for log fetching (ISO 8601 format).
  - `error_log_levels` (List[str]): List of log levels to consider as errors (e.g., `["error", "warn"]`).
  - `max_logs_to_process` (int): Maximum number of logs to fetch and process.
  - `embedding_model_name` (str): Name of the embedding model (local or API-based, e.g., `"sentence-transformers/all-MiniLM-L6-v2"` or `"models/text-embedding-004"`).
  - `llm_model_for_summary` (str): Name of the LLM for generating summaries (e.g., `"gemini-1.5-flash-latest"`).
  - `clustering_params` (Dict[str, Any]): Parameters for DBSCAN clustering (e.g., `{"eps": 0.3, "min_samples": 2}`).
  - `sampling_params` (Dict[str, int]): Parameters for sampling logs for LLM input (e.g., `{"max_samples_per_cluster": 5, "max_samples_unclustered": 10}`).
  - `target_summary_index` (str): Elasticsearch index to store the generated summaries (e.g., `cfg.INDEX_ERROR_SUMMARIES`).

- **Key Intermediate/Dynamic Fields**:

  - `parsed_log_index_name` (str): Name of the Elasticsearch index to query for logs (e.g., `parsed_log_<group_name>`).
  - `raw_error_logs` (List[Dict[str, Any]]): Full log documents fetched from Elasticsearch.
  - `error_log_messages` (List[str]): Extracted 'message' content from `raw_error_logs`.
  - `error_log_timestamps` (List[str]): Extracted '@timestamp' content from `raw_error_logs`.
  - `log_embeddings` (Optional[List[List[float]]]): Embeddings generated for `error_log_messages`.
  - `cluster_assignments` (Optional[List[int]]): Cluster labels for each log after clustering.

- **Key Output Fields**:
  - `agent_status` (str): Overall status of the agent run (e.g., "completed", "failed_embedding", "completed_no_logs").
  - `final_summary_ids` (List[str]): Elasticsearch document IDs of the stored summaries.
  - `processed_cluster_details` (List[Dict[str, Any]]): Detailed information about each processed cluster, including its summary.
  - `error_messages` (List[str]): Accumulated error or warning messages during the run.

### Core Workflow (LangGraph Nodes and Edges)

1.  **`_start_analysis_node` (Node)**

    - **Action**: Initializes the agent state, checks for the existence of the `parsed_log_index_name` and required fields (`loglevel`, `@timestamp`, `message`) in its mapping.
    - **Next**: Conditional edge `_check_initialization_status`.

2.  **`_check_initialization_status` (Conditional Edge)**

    - **Logic**: If initialization failed (index not found, missing fields), routes to `END`. Otherwise, routes to `fetch_logs_node`.

3.  **`_fetch_error_logs_node` (Node)**

    - **Action**: Fetches error logs from `parsed_log_index_name` based on `start_time_iso`, `end_time_iso`, `error_log_levels`, and `max_logs_to_process` using `ErrorSummarizerESDataService`. Populates `raw_error_logs`, `error_log_messages`, and `error_log_timestamps`.
    - **Next**: Conditional edge `_check_fetch_status`.

4.  **`_check_fetch_status` (Conditional Edge)**

    - **Logic**: If no logs are found, routes to `END`. Otherwise, routes to `embed_logs_node`.

5.  **`_embed_logs_node` (Node)**

    - **Action**: Generates embeddings for `error_log_messages` using the specified `embedding_model_name`. Handles both API-based (Gemini) and local (Sentence Transformer via `LocalSentenceTransformerEmbedder`) models. Filters out logs that result in empty or invalid embeddings and updates related state fields (`raw_error_logs`, `error_log_messages`, `error_log_timestamps`) to maintain alignment.
    - **Output**: Populates `log_embeddings`.
    - **Next**: Conditional edge `_check_embedding_status`.

6.  **`_check_embedding_status` (Conditional Edge)**

    - **Logic**: If embedding fails critically or no valid embeddings are produced, routes to `END`. Otherwise, routes to `cluster_logs_node`.

7.  **`_cluster_logs_node` (Node)**

    - **Action**: If valid `log_embeddings` exist, performs DBSCAN clustering using `LogClusteringService` and `clustering_params`.
    - **Output**: Populates `cluster_assignments`.
    - **Next**: Conditional edge `_check_clustering_status`.

8.  **`_check_clustering_status` (Conditional Edge)**

    - **Logic**: If clustering fails critically (rare), routes to `END`. Otherwise, routes to `summarize_and_store_node`. (Note: Even if no clusters are found, i.e., all noise, it proceeds to summarize the "unclustered" group).

9.  **`_summarize_and_store_node` (Node)**
    - **Action**:
      - Iterates through unique cluster IDs (including -1 for unclustered/noise).
      - For each cluster/group:
        - Gathers corresponding logs, messages, and timestamps.
        - Uses `LogSamplingService.get_cluster_metadata_and_samples` to get metadata and sample log lines based on `sampling_params`.
        - Uses `LLMService.generate_structured_summary` (which internally calls the LLM specified by `llm_model_for_summary`) to produce a `LogClusterSummaryOutput`.
        - Stores the structured summary in the `target_summary_index` using `ErrorSummarizerESDataService.store_error_summary`.
      - Populates `processed_cluster_details` with results for each cluster and `final_summary_ids` with ES document IDs of stored summaries.
    - **Next**: `END`.

### Key Internal Services

- **`ErrorSummarizerESDataService`**: Handles Elasticsearch interactions like checking field mappings, fetching error logs, and storing summaries.
- **`LogClusteringService`**: Performs DBSCAN clustering on log embeddings.
- **`LogSamplingService`**: Extracts metadata and samples logs from clusters for LLM input.
- **`LLMService`**: Manages interaction with the LLM for generating structured summaries.
- **`LocalSentenceTransformerEmbedder`**: Used internally by `_embed_logs_node` if a local embedding model is specified.

### Key Methods

- **`__init__(self, db: ElasticsearchDatabase, llm_model_instance: Optional[LLMModel] = None)`**
  - Initializes the agent, its services, and compiles the LangGraph workflow by calling `_build_graph()`.
  - `llm_model_instance` is optional; if not provided, `LLMService` will create a default `GeminiModel` based on `cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION`.
- **`run(self, group_name: str, start_time_iso: str, ..., target_summary_index: str) -> ErrorSummarizerAgentState`**
  - The main entry point for executing the error summarization pipeline.
  - Takes various parameters to configure the run, which are used to initialize the `ErrorSummarizerAgentState`.
  - Invokes the compiled LangGraph with the initial state.
  - Returns the final `ErrorSummarizerAgentState` containing the results and status of the run.
- **`_get_llm_service(self, model_name_override: Optional[str] = None) -> LLMService`**:
  - Manages the `LLMService` instance, ensuring it uses the correct LLM model (either a pre-configured instance, a default, or an overridden one).
- **Node Methods** (e.g., `_start_analysis_node`, `_fetch_error_logs_node`, etc.): Implement the logic for each step (node) in the LangGraph.
- **Conditional Edge Methods** (e.g., `_check_initialization_status`, etc.): Implement the decision logic for routing the workflow.
- **`_build_graph(self) -> CompiledGraph`**: Defines the LangGraph structure.
