# src/logllm/agents/timestamp_normalizer/states.py
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict  # MODIFIED


class TimestampNormalizerGroupState(TypedDict):
    """State for processing a single group for timestamp normalization or field removal."""

    group_name: str
    parsed_log_index: str  # The 'parsed_log_<group>' index to work on

    # Action specific status for this group
    status_this_run: str  # e.g., "pending", "normalizing", "removing_field", "completed", "failed_index_not_found", "failed_processing"
    error_message_this_run: Optional[str]

    # Metrics for the current run on this group
    documents_scanned_this_run: int
    documents_updated_this_run: int  # For both normalization and field removal
    timestamp_normalization_errors_this_run: int  # Specific to normalization action


class TimestampNormalizerOrchestratorState(TypedDict):
    """State for the main orchestrator iterating through groups."""

    # Inputs for the run
    action_to_perform: str  # "normalize" or "remove_field"
    # Optional list of specific groups to process; if None, all groups from DB are processed.
    target_group_names: Optional[List[str]]
    limit_per_group: Optional[int]  # Optional limit of documents to process per group
    batch_size: int  # Batch size for ES operations

    # Dynamically populated
    all_group_names_from_db: List[str]  # All groups found if target_group_names is None
    groups_to_process_resolved: List[
        str
    ]  # The actual list of groups the orchestrator will iterate over
    current_group_processing_index: int

    # Aggregated results
    overall_group_results: Dict[
        str, TimestampNormalizerGroupState
    ]  # Stores the final state of each processed group

    # Orchestrator status
    orchestrator_status: (
        str  # "pending", "fetching_groups", "processing_groups", "completed", "failed"
    )
    orchestrator_error_messages: List[str]
