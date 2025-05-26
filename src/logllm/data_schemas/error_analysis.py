# src/logllm/data_schemas/error_analysis.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class LogDocument(TypedDict):
    _id: str
    _source: Dict[str, Any]  # Contains 'message', '@timestamp', etc.


class ClusterResult(TypedDict):
    cluster_id: int  # -1 for noise/outliers
    representative_message: str
    count: int
    example_log_docs: List[LogDocument]  # A few full example documents
    all_log_ids_in_cluster: List[str]  # All IDs for further processing
    first_occurrence_ts: Optional[str]
    last_occurrence_ts: Optional[str]


class ErrorSummarySchema(BaseModel):
    """Pydantic schema for structured LLM summary of an error cluster/batch."""

    error_category: str = Field(
        description="A short, descriptive category or title for this type of error (e.g., 'NullPointerException in PaymentService', 'Database Connection Timeout')."
    )
    concise_description: str = Field(
        description="A brief (1-2 sentence) summary of what the error is about."
    )
    potential_root_causes: List[str] = Field(
        description="A list of 1-3 likely root causes or contributing factors."
    )
    estimated_impact: str = Field(
        description="The potential impact of this error (e.g., 'User transaction failure', 'Data processing delay', 'Minor UI glitch')."
    )
    suggested_keywords: List[str] = Field(
        description="A few keywords for searching or categorizing this error."
    )
    num_examples_in_summary_input: int = Field(
        description="Number of log examples provided to the LLM for this summary."
    )
    original_cluster_count: Optional[int] = Field(
        None, description="Total count of logs in the original cluster, if applicable."
    )
    first_occurrence_in_input: Optional[str] = Field(
        None, description="Timestamp of the earliest log example provided in the input."
    )
    last_occurrence_in_input: Optional[str] = Field(
        None, description="Timestamp of the latest log example provided in the input."
    )
    group_name: str  # Added for context in storage
    analysis_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# State for the orchestrator agent if using LangGraph
class ErrorAnalysisPipelineState(TypedDict):
    # Inputs
    group_name: str
    es_query_for_errors: Dict[str, Any]  # Query to fetch initial error logs
    clustering_params: Dict[
        str, Any
    ]  # e.g., {'method': 'embedding_dbscan', 'eps': 0.5, ...}
    sampling_params: Dict[str, Any]  # e.g., {'max_samples_per_cluster': 5}
    error_log_docs: List[LogDocument]  # Populated by initial fetch node

    # Intermediate
    clusters: Optional[List[ClusterResult]]  # Output of clustering
    current_cluster_index: int  # For iterating through clusters
    current_samples_for_summary: List[LogDocument]

    # Outputs
    generated_summaries: List[ErrorSummarySchema]
    status_messages: List[str]
