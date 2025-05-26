# src/logllm/api/models/normalize_ts_models.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ...agents.timestamp_normalizer import (
    DEFAULT_BATCH_SIZE_NORMALIZER,
)
from ...agents.timestamp_normalizer.states import (
    TimestampNormalizerGroupState,
)
from .common_models import MessageResponse  # For task initiation response


class NormalizeTsRunRequest(BaseModel):
    action: str = Field(
        ..., description="Action to perform: 'normalize' or 'remove_field'."
    )
    group_name: Optional[str] = Field(
        None,
        description="Specify a single group name. If None and all_groups is false, it's an error. If None and all_groups is true, all groups are processed.",
    )
    all_groups: bool = Field(
        False,
        description="Process all groups found in the system. Overrides group_name if true.",
    )
    limit_per_group: Optional[int] = Field(
        None,
        description="For 'normalize' action: Limit the number of documents processed per group. For testing.",
    )
    batch_size: int = Field(
        DEFAULT_BATCH_SIZE_NORMALIZER,
        description=f"Number of documents to process in each bulk ES request (default: {DEFAULT_BATCH_SIZE_NORMALIZER}).",
    )
    confirm_delete: Optional[bool] = Field(
        False,
        description="For 'remove_field' action: Confirms the deletion without frontend prompt. UI should handle prompting.",
    )


class NormalizeTsTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress_detail: Optional[str] = None
    completed: bool
    error: Optional[str] = None
    last_updated: Optional[str] = None
    result_summary: Optional[Dict[str, TimestampNormalizerGroupState]] = Field(
        None,
        description="Summary of the normalization/deletion process, mapping group names to their results.",
    )


# Using MessageResponse from common_models for task initiation response
class TaskInfoResponse(BaseModel):
    task_id: str
    message: str
