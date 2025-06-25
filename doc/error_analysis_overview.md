# Error Analysis and Summarization Pipeline Overview

This document provides a high-level overview of the error log analysis and summarization pipeline within the `logLLM` project. This pipeline is designed to process filtered error logs from Elasticsearch, group similar errors, sample them, and then use a Large Language Model (LLM) to generate concise, structured summaries of these errors. These summaries are then stored back in Elasticsearch for review.

The primary orchestrator for this pipeline is the `ErrorSummarizerAgent`, which uses LangGraph to manage the multi-step workflow.

**Pipeline Workflow:** Initialize -> Fetch Logs -> Embed Logs -> Cluster Logs (Optional based on embeddings) -> Sample & Summarize with LLM -> Store Summary.

## Detailed Agent Documentation

For detailed information on the `ErrorSummarizerAgent` which orchestrates this pipeline, please refer to its documentation page:

- **Orchestrator & Core Logic:** [`ErrorSummarizerAgent`](./agents/error_summarizer_agent.md)

---

## Configuration (from `src/logllm/config/config.py`)

The following configuration variables from `src/logllm/config/config.py` are particularly relevant to this pipeline. For full details on all configurations, see [../configurable.md](../configurable.md).

- **`INDEX_ERROR_SUMMARIES`**:

  - **Type**: `str`
  - **Default Value**: `"log_error_summaries"`
  - **Purpose**: The Elasticsearch index where LLM-generated error summaries are stored.

- **`DEFAULT_ERROR_LEVELS`**:

  - **Type**: `List[str]`
  - **Default Value**: `["error", "critical", "fatal", "warn"]` (all lowercase)
  - **Purpose**: Default log levels to consider as errors when fetching logs.

- **`DEFAULT_MAX_LOGS_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `5000`
  - **Purpose**: Maximum number of logs to fetch from Elasticsearch for a single analysis run.

- **`DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY`**:

  - **Type**: `str`
  - **Default Value**: `"sentence-transformers/all-MiniLM-L6-v2"`
  - **Purpose**: The default embedding model used by `ErrorSummarizerAgent` to convert log messages into vectors. Can be a local Sentence Transformer model path or a Google API model identifier (e.g., `"models/text-embedding-004"`).

- **`DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION`**:

  - **Type**: `str`
  - **Default Value**: `cfg.GEMINI_LLM_MODEL` (e.g., `"gemini-1.5-flash-latest"`)
  - **Purpose**: The default LLM used by the `LLMService` (within `ErrorSummarizerAgent`) for generating structured summaries.

- **`DEFAULT_DBSCAN_EPS_FOR_SUMMARY`**:

  - **Type**: `float`
  - **Default Value**: `0.3`
  - **Purpose**: The epsilon (maximum distance between samples for one to be considered as in the neighborhood of the other) parameter for the DBSCAN clustering algorithm.

- **`DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `2`
  - **Purpose**: The minimum number of samples in a neighborhood for a point to be considered as a core point in DBSCAN.

- **`DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `5`
  - **Purpose**: The default maximum number of example log lines to take from each identified error cluster to feed into the LLM for summarization.

- **`DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `10`
  - **Purpose**: If clustering is skipped or results in no distinct clusters (only noise), this is the default maximum number of error logs to sample from the overall filtered set to feed into the LLM.

- **`get_parsed_log_storage_index(group_name: str) -> str`**:
  - **Purpose**: This function from `config.py` defines the source index from which error logs are typically fetched (e.g., `parsed_log_<group_name>`). This index should contain logs that have been parsed.

---

## Data Structures (from `src/logllm/agents/error_summarizer/states.py`)

These data structures define the information passed between different stages of the pipeline and the final output.

### `LogClusterSummaryOutput(BaseModel)`

- **Purpose**: A Pydantic model defining the structured JSON output expected from the LLM when it summarizes a set of error logs. This schema is used by the `LLMService` within the `ErrorSummarizerAgent`.
- **Fields**:
  - `summary` (str): Concise summary of the primary error or issue.
  - `potential_cause` (Optional[str]): Suggested potential root cause, if discernible.
  - `keywords` (List[str]): List of 3-5 relevant keywords or tags.
  - `representative_log_line` (Optional[str]): One highly representative log line from the samples provided.

### `ErrorSummarizerAgentState(TypedDict)`

- **Purpose**: Defines the state managed by the LangGraph workflow within the `ErrorSummarizerAgent`.
- **Key Input Fields**:
  - `group_name` (str): The log group being analyzed.
  - `start_time_iso`, `end_time_iso` (str): Time window for fetching logs.
  - `error_log_levels` (List[str]): Log levels to filter.
  - `max_logs_to_process` (int): Max logs to fetch.
  - `embedding_model_name` (str): Embedding model identifier.
  - `llm_model_for_summary` (str): LLM identifier for summaries.
  - `clustering_params` (Dict[str, Any]): DBSCAN parameters.
  - `sampling_params` (Dict[str, int]): Sampling parameters for LLM input.
  - `target_summary_index` (str): ES index for storing summaries.
- **Key Intermediate Fields**:
  - `parsed_log_index_name` (str): Source index for logs.
  - `raw_error_logs` (List[Dict[str, Any]]): Fetched log documents.
  - `error_log_messages` (List[str]): Extracted messages.
  - `error_log_timestamps` (List[str]): Extracted timestamps.
  - `log_embeddings` (Optional[List[List[float]]]): Generated embeddings.
  - `cluster_assignments` (Optional[List[int]]): Cluster labels for logs.
- **Key Output Fields**:
  - `agent_status` (str): Final status of the agent run.
  - `final_summary_ids` (List[str]): ES IDs of stored summaries.
  - `processed_cluster_details` (List[Dict[str, Any]]): Information about each cluster, including:
    - `cluster_id_internal`, `cluster_label`
    - `total_logs_in_cluster`, `unique_messages_in_cluster`
    - `cluster_time_range_start`, `cluster_time_range_end`
    - `sampled_log_messages_used`
    - `summary_generated` (bool)
    - `summary_document_id_es` (Optional[str])
    - `summary_output` (Optional `LogClusterSummaryOutput` as dict)
  - `error_messages` (List[str]): Accumulated errors during the run.
