# Error Analysis and Summarization Pipeline Overview

This document provides a high-level overview of the error log analysis and summarization pipeline within the `logLLM` project. This pipeline is designed to process filtered error logs from Elasticsearch, group similar errors, sample them, and then use a Large Language Model (LLM) to generate concise, structured summaries of these errors. These summaries are then stored back in Elasticsearch for review.

The primary orchestrator for this pipeline is the `ErrorAnalysisPipelineAgent`, which uses LangGraph to manage the multi-step workflow. It leverages specialized atomic agents for clustering (`ErrorClustererAgent`) and LLM-based summarization (`ErrorSummarizerAgent`).

**Pipeline Workflow:** Filter -> Cluster (Optional) -> Sample -> Summarize with LLM -> Store Summary.

## Detailed Agent Documentation

For detailed information on each agent involved in this pipeline, please refer to their individual documentation pages:

- **Orchestrator:** [`ErrorAnalysisPipelineAgent`](./agents/error_analysis_pipeline_agent.md)
- **Clustering:** [`ErrorClustererAgent`](./agents/error_clusterer_agent.md)
- **Summarization:** [`ErrorSummarizerAgent`](./agents/error_summarizer_agent.md)

---

## Configuration (from `src/logllm/config/config.py`)

The following configuration variables from `src/logllm/config/config.py` are particularly relevant to this pipeline. For full details on all configurations, see [../configurable.md](../configurable.md).

- **`INDEX_ERROR_SUMMARIES`**:

  - **Type**: `str`
  - **Default Value**: `"log_error_summaries"`
  - **Purpose**: The Elasticsearch index where LLM-generated error summaries are stored.

- **`DEFAULT_CLUSTERING_EMBEDDING_MODEL`**:

  - **Type**: `str`
  - **Default Value**: `"models/text-embedding-004"` (or similar, as used by `LLMModel.embedding`)
  - **Purpose**: The embedding model used by `ErrorClustererAgent` to convert log messages into vectors for clustering. This is typically accessed via the `LLMModel` instance passed to the agent.

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

- **`get_normalized_parsed_log_storage_index(group_name: str) -> str`**:
  - **Purpose**: This function from `config.py` defines the source index from which error logs are typically fetched (e.g., `normalized_parsed_log_<group_name>`). This index should contain logs that have been parsed and had their timestamps normalized.

---

## Data Structures (from `src/logllm/data_schemas/error_analysis.py`)

These data structures, defined in `src/logllm/data_schemas/error_analysis.py`, facilitate the flow of information between different stages of the pipeline.

### `LogDocument(TypedDict)`

- **Purpose**: Represents a single log document retrieved from Elasticsearch, typically from an index like `normalized_parsed_log_<group_name>` or the temporary `temp_error_analysis_<group_name>`.
- **Fields**:
  - `_id` (str): The document ID from Elasticsearch.
  - `_source` (Dict[str, Any]): The actual content of the log document. Expected to contain fields crucial for error analysis, such as:
    - `message` (str): The primary log message text.
    - `@timestamp` (str): The normalized ISO 8601 timestamp.
    - `level` (str) or `log_level` (str): The severity level of the log (e.g., "ERROR", "CRITICAL"). The exact field name depends on the parsing (Grok) pattern used.
    - Other parsed fields like `class_name`, `thread_name`, etc., can also be present and useful.

### `ClusterResult(TypedDict)`

- **Purpose**: Represents the output of the `ErrorClustererAgent` for a single identified cluster of error logs.
- **Fields**:
  - `cluster_id` (int): The ID assigned to the cluster by the clustering algorithm (e.g., DBSCAN labels, where -1 often indicates noise/outliers).
  - `representative_message` (str): A sample log message chosen to represent the theme of this cluster.
  - `count` (int): The number of log documents belonging to this cluster.
  - `example_log_docs` (List[LogDocument]): A small list of full `LogDocument` objects from this cluster, used as samples for the `ErrorSummarizerAgent`. The number of examples is typically controlled by `cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY`.
  - `all_log_ids_in_cluster` (List[str]): A list of all document IDs (`_id`) belonging to this cluster, allowing for further operations on the full cluster if needed.
  - `first_occurrence_ts` (Optional[str]): ISO timestamp of the earliest log in this cluster, derived from the `@timestamp` field of the documents in the cluster.
  - `last_occurrence_ts` (Optional[str]): ISO timestamp of the latest log in this cluster.

### `ErrorSummarySchema(BaseModel)`

- **Purpose**: A Pydantic model defining the structured JSON output expected from the LLM when it summarizes a set of error logs. This schema is used by the `ErrorSummarizerAgent` to guide the LLM's response and validate it.
- **Fields**:
  - `error_category` (str): A short, descriptive category or title for the error type (e.g., "NullPointerException in PaymentService").
  - `concise_description` (str): A brief (1-2 sentence) summary of what the error is about.
  - `potential_root_causes` (List[str]): A list of 1-3 likely root causes or contributing factors.
  - `estimated_impact` (str): The potential impact of this error (e.g., "User transaction failure," "Data processing delay").
  - `suggested_keywords` (List[str]): A few keywords for searching or categorizing this error.
  - `num_examples_in_summary_input` (int): The number of log examples that were provided as input to the LLM to generate this specific summary. This is populated by the `ErrorSummarizerAgent`.
  - `original_cluster_count` (Optional[int]): If the summary was for a cluster, this field holds the total count of logs in that original cluster. Populated by the `ErrorSummarizerAgent`.
  - `first_occurrence_in_input` (Optional[str]): Timestamp of the earliest log example provided as input to the LLM. Populated by the `ErrorSummarizerAgent`.
  - `last_occurrence_in_input` (Optional[str]): Timestamp of the latest log example provided as input. Populated by the `ErrorSummarizerAgent`.
  - `group_name` (str): The log group to which these errors belong. Populated by the `ErrorSummarizerAgent`.
  - `analysis_timestamp` (str): ISO timestamp indicating when this summary was generated (defaults to `datetime.now().isoformat()`).

### `ErrorAnalysisPipelineState(TypedDict)`

- **Purpose**: Defines the state managed by the LangGraph workflow within the `ErrorAnalysisPipelineAgent`.
- **Details**: See the [`ErrorAnalysisPipelineAgent` documentation](./agents/error_analysis_pipeline_agent.md) for a detailed breakdown of its fields.
