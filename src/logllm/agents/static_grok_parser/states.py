# src/logllm/agents/static_grok_parser/states.py
from typing import Any, Dict, List, Optional, TypedDict

# from pygrok import Grok # Avoid importing Grok here if state needs to be pickled for multiprocessing


# --- State for processing a single log file ---
class LogFileProcessingState(TypedDict):
    log_file_id: str
    group_name: str  # For context
    grok_pattern_string: str  # The actual pattern to use for this file

    # Status from previous runs or this run's start
    last_line_parsed_by_grok: int
    current_total_lines_by_collector: int

    # Accumulators for the current processing of this file
    max_line_processed_this_session: (
        int  # Tracks highest line number seen in current fetch
    )
    new_lines_scanned_this_session: int
    parsed_actions_batch: List[Dict[str, Any]]  # For ES bulk index
    unparsed_actions_batch: List[Dict[str, Any]]  # For ES bulk index

    # Outcome of processing this file in the current run
    status_this_session: str  # e.g., "pending", "processing", "completed_new_data", "completed_no_new_data", "failed_fetching_lines", "skipped_up_to_date"
    error_message_this_session: Optional[str]


# --- State for processing a single group (iterating through its files) ---
class StaticGrokParserGroupState(TypedDict):
    group_name: str
    source_log_index: str
    parsed_log_index: str
    unparsed_log_index: str

    grok_pattern_string: Optional[str]  # Loaded from YAML for this group
    # grok_instance: Optional[Any] # Avoid complex objects in state if possible, recompile from string

    all_log_file_ids_in_group: List[str]
    current_log_file_index_in_group: int  # Iterator for files within this group

    # Stores the outcome of processing each file in this group during the current agent run
    files_processed_summary_this_run: Dict[str, LogFileProcessingState]

    group_status: str  # "pending", "initializing", "processing_files", "completed", "failed_no_pattern", "failed_pattern_compile", "failed_fetching_file_ids"
    group_error_messages: List[str]


# --- State for the main orchestrator (iterating through groups) ---
class StaticGrokParserOrchestratorState(TypedDict):
    all_group_names_from_db: List[str]
    current_group_processing_index: int  # Iterator for groups

    # Holds the final summary state of each group after it's processed
    # The value could be StaticGrokParserGroupState or a more summarized version
    overall_group_results: Dict[
        str, Dict[str, Any]
    ]  # Key: group_name, Value: summary of group processing

    orchestrator_status: (
        str  # "pending", "fetching_groups", "processing_groups", "completed", "failed"
    )
    orchestrator_error_messages: List[str]
