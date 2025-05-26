# src/logllm/api/models/analyze_errors_models.py
from datetime import datetime  # For ISO timestamp validation
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from ...agents.error_summarizer.states import (
    ErrorSummarizerAgentState,  # For the full state
)
from ...agents.error_summarizer.states import (
    LogClusterSummaryOutput,  # For result_summary type hint; For individual cluster summary
)
from ...config import config as cfg  # For default values


def validate_iso_format(value: str) -> str:
    try:
        # Attempt to parse to validate format, handles 'Z' for UTC correctly.
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        raise ValueError(
            f"Invalid ISO 8601 timestamp format: {value}. Expected e.g., YYYY-MM-DDTHH:MM:SSZ"
        )


class AnalyzeErrorsRunParams(BaseModel):
    group_name: str = Field(..., description="The log group to analyze.")
    start_time_iso: str = Field(
        ..., description="Start of the time window in ISO 8601 format (UTC)."
    )
    end_time_iso: str = Field(
        ..., description="End of the time window in ISO 8601 format (UTC)."
    )

    error_log_levels: Optional[List[str]] = Field(
        default_factory=lambda: list(
            cfg.DEFAULT_ERROR_LEVELS
        ),  # Use lowercase defaults
        description="Comma-separated list of log levels to analyze (e.g., ['error', 'warn']).",
    )
    max_logs_to_process: int = Field(
        default=cfg.DEFAULT_MAX_LOGS_FOR_SUMMARY,
        description="Maximum number of logs to fetch and process for this run.",
    )
    embedding_model_name: str = Field(
        default=cfg.DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY,
        description="Name of the embedding model to use (local or API).",
    )
    llm_model_for_summary: str = Field(
        default=cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION,
        description="Name of the LLM to use for generating summaries.",
    )
    dbscan_eps: float = Field(
        default=cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY,
        description="DBSCAN epsilon parameter for clustering.",
    )
    dbscan_min_samples: int = Field(
        default=cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY,
        description="DBSCAN min_samples parameter.",
    )
    max_samples_per_cluster: int = Field(
        default=cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY,
        description="Max samples from each cluster for LLM input.",
    )
    max_samples_unclustered: int = Field(
        default=cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY,
        description="Max samples from unclustered logs for LLM input.",
    )
    target_summary_index: str = Field(
        default=cfg.INDEX_ERROR_SUMMARIES,
        description="Elasticsearch index to store the generated summaries.",
    )

    _validate_start_time = validator("start_time_iso", allow_reuse=True)(
        validate_iso_format
    )
    _validate_end_time = validator("end_time_iso", allow_reuse=True)(
        validate_iso_format
    )

    @validator("error_log_levels", pre=True, always=True)
    def ensure_error_levels_are_list_and_lowercase(cls, v):
        if isinstance(v, str):
            return [level.strip().lower() for level in v.split(",") if level.strip()]
        if isinstance(v, list):
            return [str(level).strip().lower() for level in v if str(level).strip()]
        return list(cfg.DEFAULT_ERROR_LEVELS)  # Fallback to lowercase defaults


class AnalyzeErrorsTaskStatusResponse(BaseModel):
    task_id: str
    status: str  # e.g., Pending, Initializing, Fetching Logs, Embedding, Clustering, Summarizing, Completed, Failed
    progress_detail: Optional[str] = None
    completed: bool
    error: Optional[str] = None
    last_updated: Optional[str] = None
    # Use a simplified summary for the API response, or the full agent state if needed.
    # For now, let's define a structure for what the UI might want to show from the results.

    # This will hold the 'processed_cluster_details' part from ErrorSummarizerAgentState
    # and potentially other high-level stats from the agent's final state.
    result_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of the analysis run, including processed cluster details and overall status.",
    )
    # Example of a more structured result_summary if needed:
    # result_summary: Optional[ErrorSummarizerAgentState] = None
    # But ErrorSummarizerAgentState might be too verbose for direct API response.


class TaskInitiationResponse(BaseModel):
    task_id: str
    message: str


# Model for listing summaries (placeholder for now)
class ErrorSummaryListItem(BaseModel):
    summary_id: str = Field(..., alias="_id")  # Assuming ES _id is used
    group_name: str
    cluster_id: str
    summary_text: str
    potential_cause_text: Optional[str] = None
    keywords: List[str] = []
    generation_timestamp: str
    analysis_start_time: str
    analysis_end_time: str
    llm_model_used: str
    sample_log_count: int
    total_logs_in_cluster: int

    class Config:
        populate_by_name = True  # Allows using alias _id


class ListErrorSummariesResponse(BaseModel):
    summaries: List[ErrorSummaryListItem]
    total: int
    offset: int
    limit: int
