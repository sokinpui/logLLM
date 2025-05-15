# Error Analysis and Summarization Agents & Data Structures

This document details the agents, data structures, and configurations used for the error log analysis and summarization pipeline within the `logLLM` project. This pipeline follows the workflow: Filter -> Cluster -> Sample -> Summarize with LLM -> Store Summary.

---

## Overview

The error analysis pipeline is designed to process filtered error logs from Elasticsearch, group similar errors, sample them, and then use a Large Language Model (LLM) to generate concise, structured summaries of these errors. These summaries are then stored back in Elasticsearch for review.

The primary orchestrator for this pipeline is the `ErrorAnalysisPipelineAgent`, which uses LangGraph to manage the multi-step workflow. It leverages specialized atomic agents for clustering (`ErrorClustererAgent`) and LLM-based summarization (`ErrorSummarizerAgent`).

---

## Configuration (from `src/logllm/config/config.py`)

The following configuration variables are relevant to this pipeline:

- **`INDEX_ERROR_SUMMARIES`**:

  - **Type**: `str`
  - **Default Value**: `"log_error_summaries"`
  - **Purpose**: The Elasticsearch index where LLM-generated error summaries are stored.

- **`DEFAULT_CLUSTERING_EMBEDDING_MODEL`**:

  - **Type**: `str`
  - **Default Value**: `"models/text-embedding-004"` (or similar)
  - **Purpose**: The embedding model used by `ErrorClustererAgent` to convert log messages into vectors for clustering.

- **`DEFAULT_DBSCAN_EPS`**:

  - **Type**: `float`
  - **Default Value**: `0.5`
  - **Purpose**: The epsilon (maximum distance between samples for one to be considered as in the neighborhood of the other) parameter for the DBSCAN clustering algorithm used in `ErrorClustererAgent`. This value might need tuning based on the embedding space and desired cluster granularity.

- **`DEFAULT_DBSCAN_MIN_SAMPLES`**:

  - **Type**: `int`
  - **Default Value**: `3`
  - **Purpose**: The minimum number of samples in a neighborhood for a point to be considered as a core point in DBSCAN. This influences the minimum size of a cluster.

- **`DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `5`
  - **Purpose**: The default maximum number of example log lines to take from each identified error cluster to feed into the `ErrorSummarizerAgent` for generating a summary.

- **`DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY`**:

  - **Type**: `int`
  - **Default Value**: `20`
  - **Purpose**: If clustering is skipped or results in no distinct clusters (only noise), this is the default maximum number of error logs to sample from the overall filtered set to feed into the `ErrorSummarizerAgent`.

- **`get_error_analysis_working_index(group_name: str) -> str`**:
  - **Purpose**: A utility function that generates the name for a temporary Elasticsearch index (e.g., `"temp_error_analysis_<group_name>"`) used by the `ErrorAnalysisPipelineAgent`. This index stores the initially filtered error logs for the duration of a single analysis run and is deleted at the beginning of the next run for that group.

---

## Data Structures (from `src/logllm/data_schemas/error_analysis.py`)

These data structures define the information passed between different stages of the pipeline.

### `LogDocument(TypedDict)`

- **Purpose**: Represents a single log document retrieved from Elasticsearch.
- **Fields**:
  - `_id` (str): The document ID from Elasticsearch.
  - `_source` (Dict[str, Any]): The actual content of the log document, expected to contain fields like `message`, `@timestamp`, `level` (or `log_level`), etc.

### `ClusterResult(TypedDict)`

- **Purpose**: Represents the output of the `ErrorClustererAgent` for a single identified cluster of error logs.
- **Fields**:
  - `cluster_id` (int): The ID assigned to the cluster by the clustering algorithm (e.g., DBSCAN labels, where -1 often indicates noise/outliers).
  - `representative_message` (str): A sample log message chosen to represent the theme of this cluster.
  - `count` (int): The number of log documents belonging to this cluster.
  - `example_log_docs` (List[LogDocument]): A small list of full `LogDocument` objects from this cluster, used as samples for the LLM summarizer.
  - `all_log_ids_in_cluster` (List[str]): A list of all document IDs (`_id`) belonging to this cluster.
  - `first_occurrence_ts` (Optional[str]): ISO timestamp of the earliest log in this cluster.
  - `last_occurrence_ts` (Optional[str]): ISO timestamp of the latest log in this cluster.

### `ErrorSummarySchema(BaseModel)`

- **Purpose**: A Pydantic model defining the structured JSON output expected from the LLM when it summarizes a set of error logs. This schema is used by the `ErrorSummarizerAgent`.
- **Fields**:
  - `error_category` (str): A short, descriptive category or title for the error type.
  - `concise_description` (str): A brief (1-2 sentence) summary of the error.
  - `potential_root_causes` (List[str]): Likely root causes or contributing factors.
  - `estimated_impact` (str): The potential impact of this error.
  - `suggested_keywords` (List[str]): Keywords for searching or categorizing.
  - `num_examples_in_summary_input` (int): Number of log examples provided to the LLM for this summary.
  - `original_cluster_count` (Optional[int]): Total count of logs in the original cluster (if applicable).
  - `first_occurrence_in_input` (Optional[str]): Timestamp of the earliest log example provided as input to the LLM.
  - `last_occurrence_in_input` (Optional[str]): Timestamp of the latest log example provided as input.
  - `group_name` (str): The log group to which these errors belong.
  - `analysis_timestamp` (str): ISO timestamp indicating when this summary was generated.

### `ErrorAnalysisPipelineState(TypedDict)`

- **Purpose**: Defines the state managed by the LangGraph workflow within the `ErrorAnalysisPipelineAgent`. It holds configuration, input data, intermediate results, and final outputs.
- **Key Fields**:
  - _Inputs_: `group_name`, `es_query_for_errors`, `clustering_params`, `sampling_params`.
  - _Intermediate_: `error_log_docs` (initially fetched errors), `clusters` (output of clustering), `current_cluster_index` (for looping), `current_samples_for_summary`.
  - _Outputs_: `generated_summaries` (list of `ErrorSummarySchema` objects), `status_messages` (log of pipeline actions).

---

## Atomic Agents

These agents perform specific, singular tasks within the broader pipeline.

### 1. `ErrorClustererAgent`

- **File**: `src/logllm/agents/error_clusterer_agent.py`
- **Purpose**: Takes a list of filtered `LogDocument` objects and groups them into clusters based on the similarity of their error messages.
- **Core Logic**:
  1.  Extracts the `message` field from each log document.
  2.  Uses an embedding model (provided via `LLMModel` instance, e.g., `models/text-embedding-004`) to generate vector embeddings for each message.
  3.  Applies the DBSCAN clustering algorithm to these embeddings to group similar messages. It uses `eps` (epsilon for neighborhood distance) and `min_samples` (minimum points to form a cluster) as parameters, configurable via `config.py` defaults or CLI arguments.
  4.  For each identified cluster (and for noise points), it produces a `ClusterResult` object.
- **Key Methods**:
  - `__init__(self, embedding_model: LLMModel)`: Initializes with an LLM model capable of providing embeddings.
  - `run(self, error_log_docs: List[LogDocument], eps: float, min_samples: int, max_docs_for_clustering: int) -> List[ClusterResult]`: Executes the clustering process. It includes a limit (`max_docs_for_clustering`) on the number of documents processed to manage resource usage for embedding generation.
  - `_get_embeddings(self, messages: List[str]) -> Optional[np.ndarray]`: Internal helper to get embeddings.
  - `_get_cluster_stats(self, cluster_docs: List[LogDocument]) -> Dict[str, Any]`: Helper to find first/last occurrence timestamps for a cluster.

### 2. `ErrorSummarizerAgent`

- **File**: `src/logllm/agents/error_summarizer_agent.py`
- **Purpose**: Takes a list of sampled `LogDocument` objects (typically representing a single error cluster or a batch of unclustered errors) and uses an LLM to generate a structured summary based on the `ErrorSummarySchema`.
- **Core Logic**:
  1.  Formats the provided log samples into a text block suitable for an LLM prompt.
  2.  Constructs a detailed prompt using templates managed by `PromptsManager`. The prompt includes the formatted log samples, the number of samples, and contextual information (like original cluster count, representative message if from a cluster, group name, and time occurrences). Different prompts can be used for clustered vs. unclustered inputs.
  3.  Calls the `generate` method of the provided `LLMModel` (e.g., `GeminiModel`), instructing it to use the `ErrorSummarySchema` for structured output.
  4.  If the LLM returns a valid, Pydantic-validated `ErrorSummarySchema` object, it augments this object with some non-LLM-generated metadata (like the `group_name`, actual number of input examples, etc.) and returns it.
- **Key Methods**:
  - `__init__(self, llm_model: LLMModel, prompts_manager: PromptsManager)`: Initializes with an LLM model for generation and a `PromptsManager`.
  - `run(self, group_name: str, log_samples_docs: List[LogDocument], cluster_context: Optional[Dict[str, Any]] = None) -> Optional[ErrorSummarySchema]`: Executes the summarization. `cluster_context` provides additional information if the samples came from a distinct cluster.
  - `_format_log_samples_for_prompt(self, log_docs: List[LogDocument]) -> str`: Helper to prepare log samples for the prompt.

---

## Orchestrator Agent (LangGraph-based)

### `ErrorAnalysisPipelineAgent`

- **File**: `src/logllm/agents/error_analysis_pipeline_agent.py`
- **Purpose**: Orchestrates the entire error analysis and summarization workflow using a graph-based structure (LangGraph). It manages the flow of data between the atomic agents and handles decision-making.
- **Workflow (Nodes and Edges)**:
  1.  **`fetch_initial_errors` (Node)**:
      - Input: `group_name`, `es_query_for_errors` from the pipeline state.
      - Action:
        - Determines the temporary working index name (e.g., `temp_error_analysis_<group>`) using `cfg.get_error_analysis_working_index()`.
        - Deletes this working index if it exists.
        - Queries the primary log data index (e.g., `normalized_parsed_log_<group>`) using `es_query_for_errors`.
        - Bulk-indexes the fetched raw error logs into the (new) temporary working index.
        - Populates `error_log_docs` in the pipeline state with the fetched documents.
      - Next: `cluster_errors`.
  2.  **`cluster_errors` (Node)**:
      - Input: `error_log_docs`, `clustering_params` from state.
      - Action: Calls `ErrorClustererAgent.run()` to cluster the logs.
      - Output: Populates `clusters` and initializes `current_cluster_index` in state.
      - Next: Conditional edge `_decide_clustering_outcome`.
  3.  **`_decide_clustering_outcome` (Conditional Edge)**:
      - Logic: Checks if clustering produced meaningful clusters (e.g., not all noise, or any clusters at all).
      - Path 1 ("check_cluster_loop_condition"): If good clusters exist, proceed to loop through them.
      - Path 2 ("summarize_unclustered_fallback"): If clustering failed or was ineffective, proceed to summarize a general sample of unclustered logs.
  4.  **`check_cluster_loop_condition` (Node & Conditional Edge)**:
      - Node: A simple pass-through node.
      - Edge (`_check_cluster_loop_condition_node`):
        - Logic: Checks if `current_cluster_index` is less than the total number of `clusters`.
        - Path 1 ("process_this_cluster"): If more clusters to process, go to `sample_and_summarize_cluster`.
        - Path 2 ("finish_cluster_processing"): If all clusters processed, go to `store_summaries`.
  5.  **`sample_and_summarize_cluster` (Node)**:
      - Input: `clusters[current_cluster_index]`, `group_name`, `sampling_params` from state.
      - Action:
        - Takes example logs from the current cluster (already sampled by `ErrorClustererAgent` or further sampled here if needed).
        - Calls `ErrorSummarizerAgent.run()` with these samples and cluster context (representative message, count, etc.).
        - Appends the returned `ErrorSummarySchema` object to `generated_summaries` in state.
        - Increments `current_cluster_index` in state.
      - Next: `check_cluster_loop_condition` (to loop back).
  6.  **`summarize_unclustered_fallback_node` (Node)**:
      - Input: `error_log_docs`, `group_name`, `sampling_params` from state.
      - Action:
        - Takes a random sample from all `error_log_docs`.
        - Calls `ErrorSummarizerAgent.run()` with these samples (no specific cluster context).
        - Appends the summary to `generated_summaries`.
      - Next: `store_summaries`.
  7.  **`store_summaries` (Node)**:
      - Input: `generated_summaries` from state.
      - Action: Iterates through the `ErrorSummarySchema` objects and inserts each (as a dictionary) into the `cfg.INDEX_ERROR_SUMMARIES` Elasticsearch index.
      - Next: `END` (pipeline finishes).
- **Key Methods**:
  - `__init__(self, db: ElasticsearchDatabase, llm_model: LLMModel, prompts_manager: PromptsManager)`: Initializes with dependencies and builds the LangGraph.
  - `run(self, initial_state_input: Dict[str, Any]) -> ErrorAnalysisPipelineState`: Executes the compiled LangGraph with the initial state.
  - Node methods (e.g., `_fetch_initial_errors_node`, `_cluster_errors_node`, etc.): Implement the logic for each step in the graph.
  - Conditional edge methods (e.g., `_decide_clustering_outcome`, `_check_cluster_loop_condition_node`): Implement the decision logic for routing within the graph.
  - `_build_graph(self) -> CompiledGraph`: Defines the LangGraph structure, nodes, and edges.
