from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from .common_models import MessageResponse  # For task initiation response


class EsParseRunRequest(BaseModel):
    group_name: Optional[str] = Field(
        None,
        description="Specify a single group name to parse. If None, all groups are processed.",
    )
    field_to_parse: str = Field(
        "content",
        description="Source field in Elasticsearch documents containing the raw log line to parse.",
    )
    copy_fields: Optional[List[str]] = Field(
        None,
        description="Additional source fields to copy to the target parsed document.",
    )
    batch_size: int = Field(
        1000, description="Number of documents to process and index per batch."
    )
    sample_size_generation: int = Field(
        20, description="Number of log lines to sample for LLM Grok pattern generation."
    )
    validation_sample_size: int = Field(
        10, description="Number of lines for validating a generated Grok pattern."
    )
    validation_threshold: float = Field(
        0.5,
        description="Minimum success rate (0.0-1.0) on validation sample to accept a Grok pattern.",
    )
    max_retries: int = Field(
        2,
        description="Maximum number of times to retry Grok pattern generation if validation fails (0 means 1 attempt).",
    )
    threads: int = Field(
        1,
        description="Number of parallel workers for processing all groups (ignored if group_name is specified).",
    )
    pattern: Optional[str] = Field(
        None,
        description="Provide a specific Grok pattern string to use (only for single group parsing).",
    )
    keep_unparsed_index: bool = Field(
        False,
        description="If true, do not delete the unparsed log index before running a new parse.",
    )


class EsParseResultItem(BaseModel):
    group_name: str
    parsing_status: str
    grok_pattern_used: Optional[str] = None
    timestamp: str  # ISO format string of when the parsing run was recorded
    processed_count: int
    successful_count: int
    failed_count: int  # Docs sent to unparsed/failed index
    parse_error_count: int  # Grok mismatches during parsing run
    index_error_count: int  # Bulk indexing errors during ES write
    agent_error_count: int  # Errors/warnings from the agent's logic
    target_index: str
    unparsed_index: str
    success_percentage: Optional[float] = None
    error_messages_summary: Optional[List[str]] = None  # Key error messages from agent


class EsParseListResponse(BaseModel):
    results: List[EsParseResultItem]
    total: int


class EsParseGroupListResponse(BaseModel):
    groups: List[str]
    total: int


# Re-using TaskStatusResponse from collect_router for simplicity,
# or it could be defined in common_models.py
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress_detail: Optional[str] = None
    completed: bool
    error: Optional[str] = None
    last_updated: Optional[str] = None
    # Optional field to store structured results if the task is completed
    result_summary: Optional[Dict[str, Any]] = None
