# src/logllm/agents/error_summarizer/states.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- Pydantic model for structured LLM summary output ---
class LogClusterSummaryOutput(BaseModel):
    summary: str = Field(description="Concise summary of the primary error or issue.")
    potential_cause: Optional[str] = Field(
        default=None, description="Suggested potential root cause, if discernible."
    )
    keywords: List[str] = Field(
        default_factory=list, description="List of 3-5 relevant keywords or tags."
    )
    representative_log_line: Optional[str] = Field(
        default=None,
        description="One highly representative log line from the samples provided.",
    )


# --- TypedDict for agent's internal state ---
class ErrorSummarizerAgentState(TypedDict):
    # Inputs
    group_name: str
    start_time_iso: str  # ISO format string
    end_time_iso: str  # ISO format string
    error_log_levels: List[str]
    max_logs_to_process: int
    embedding_model_name: str
    llm_model_for_summary: str
    clustering_params: Dict[str, Any]  # e.g., {"eps": 0.5, "min_samples": 3}
    sampling_params: Dict[
        str, int
    ]  # e.g., {"max_samples_per_cluster": 5, "max_samples_unclustered": 10}
    target_summary_index: str  # ES index to store summaries

    # Intermediate data
    parsed_log_index_name: str  # Name of the index to query
    raw_error_logs: List[Dict[str, Any]]  # Full documents from ES
    error_log_messages: List[str]  # Extracted messages for embedding
    error_log_timestamps: List[str]  # Extracted timestamps
    log_embeddings: Optional[List[List[float]]]
    # Cluster labels: index corresponds to raw_error_logs. -1 for outliers.
    cluster_assignments: Optional[List[int]]

    # Outputs
    processed_cluster_details: List[
        Dict[str, Any]
    ]  # Info about each cluster (id, size, time_range, samples, summary_doc)
    agent_status: str  # e.g., "pending", "fetching_logs", "clustering", "summarizing", "completed", "failed"
    final_summary_ids: List[str]  # IDs of summary documents stored in ES
    error_messages: List[str]
