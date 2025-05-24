# src/logllm/agents/static_grok_parser/__init__.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph

try:
    from ...config import config as cfg
    from ...utils.database import ElasticsearchDatabase
    from ...utils.logger import Logger
except ImportError:
    import os
    import sys

    # Adjust path for potential direct execution or specific test setups
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_guess = os.path.abspath(
        os.path.join(current_dir, "..", "..", "..", "..")
    )
    sys.path.insert(0, project_root_guess)
    from src.logllm.config import config as cfg  # type: ignore
    from src.logllm.utils.database import ElasticsearchDatabase  # type: ignore
    from src.logllm.utils.logger import Logger  # type: ignore

from .api.derived_field_processor import DerivedFieldProcessor
from .api.es_data_service import ElasticsearchDataService
from .api.grok_parsing_service import GrokParsingService
from .api.grok_pattern_service import GrokPatternService
from .states import (
    LogFileProcessingState,
    StaticGrokParserGroupState,
    StaticGrokParserOrchestratorState,
)

# Constants for batch sizes within the agent's processing logic
FILE_PROCESSING_SCROLL_BATCH_SIZE = 5000
FILE_PROCESSING_BULK_INDEX_BATCH_SIZE = 2500


class StaticGrokParserAgent:
    def __init__(
        self,
        db: ElasticsearchDatabase,
        grok_patterns_yaml_path: str = "grok_patterns.yaml",
    ):
        self._logger = Logger()
        # Services
        self.es_service = ElasticsearchDataService(db)
        self.grok_pattern_service = GrokPatternService(grok_patterns_yaml_path)
        self.grok_parsing_service = GrokParsingService()
        self.derived_field_processor = DerivedFieldProcessor(logger=self._logger)

        self.graph: CompiledGraph = self._build_orchestrator_graph()

    def _format_es_action(self, index_name: str, doc_id: str, doc_source: Dict) -> Dict:
        return {
            "_op_type": "index",
            "_index": index_name,
            "_id": doc_id,
            "_source": doc_source,
        }

    def _prepare_parsed_doc_source(
        self, original_es_hit_source: Dict, group_name: str, processed_grok_fields: Dict
    ) -> Dict:
        doc_id = original_es_hit_source.get("id")
        line_num = original_es_hit_source.get("line_number")

        parsed_doc_source = {
            **processed_grok_fields,
            "original_log_file_id": doc_id,
            "original_log_file_name": original_es_hit_source.get(
                "name"
            ),  # This is relative path
            "original_line_number": line_num,
            "original_content": original_es_hit_source.get("content"),
            "parsed_by_agent": "StaticGrokParserAgent_LG",
            "grok_pattern_group": group_name,
        }
        # 'original_ingestion_timestamp' might not exist from collector if removed
        # if "ingestion_timestamp" in original_es_hit_source:
        #      parsed_doc_source["original_ingestion_timestamp"] = original_es_hit_source["ingestion_timestamp"]
        return parsed_doc_source

    def _prepare_unparsed_doc_source(
        self, original_es_hit_source: Dict, group_name: str, reason: str
    ) -> Dict:
        doc_id = original_es_hit_source.get("id")
        line_num = original_es_hit_source.get("line_number")

        unparsed_doc = {
            "original_log_file_id": doc_id,
            "original_log_file_name": original_es_hit_source.get(
                "name"
            ),  # This is relative path
            "original_line_number": line_num,
            "original_content": original_es_hit_source.get("content"),
            "reason_unparsed": reason,
            "grok_pattern_group_attempted": group_name,
            "parser_agent": "StaticGrokParserAgent_LG",
        }
        # if "ingestion_timestamp" in original_es_hit_source:
        #      unparsed_doc["original_ingestion_timestamp"] = original_es_hit_source["ingestion_timestamp"]
        return unparsed_doc

    def _orchestrator_start_node(
        self, state: StaticGrokParserOrchestratorState
    ) -> Dict[str, Any]:
        self._logger.info("Orchestrator: Starting Static Grok Parsing run.")
        all_group_names = self.es_service.get_all_log_group_names()

        if not all_group_names:
            self._logger.warning(
                "Orchestrator: No log groups found in DB. Nothing to process."
            )
            return {
                "all_group_names_from_db": [],
                "current_group_processing_index": 0,
                "orchestrator_status": "completed_no_groups",
                "overall_group_results": {},
            }

        self._logger.info(
            f"Orchestrator: Found {len(all_group_names)} groups to process: {all_group_names}"
        )
        return {
            "all_group_names_from_db": all_group_names,
            "current_group_processing_index": 0,
            "orchestrator_status": "processing_groups",
            "overall_group_results": {},
        }

    def _orchestrator_initialize_group_processing_node(
        self, state: StaticGrokParserOrchestratorState
    ) -> Dict[str, Any]:
        idx = state["current_group_processing_index"]
        group_name = state["all_group_names_from_db"][idx]
        self._logger.info(
            f"Orchestrator: Initializing processing for Group '{group_name}' (index {idx})."
        )

        group_state_update: Dict[str, Any] = {
            "group_name": group_name,
            "source_log_index": cfg.get_log_storage_index(group_name),
            "parsed_log_index": cfg.get_parsed_log_storage_index(group_name),
            "unparsed_log_index": cfg.get_unparsed_log_storage_index(group_name),
            "grok_pattern_string": None,
            "all_log_file_ids_in_group": [],
            "current_log_file_index_in_group": 0,
            "files_processed_summary_this_run": {},
            "group_status": "initializing",
            "group_error_messages": [],
        }

        pattern_str = self.grok_pattern_service.get_grok_pattern_string_for_group(
            group_name
        )
        if not pattern_str:
            msg = f"Group '{group_name}': No Grok pattern string found in YAML. Cannot process."
            self._logger.warning(msg)
            group_state_update["group_status"] = "failed_no_pattern"
            group_state_update["group_error_messages"].append(msg)
            updated_overall_results = state.get("overall_group_results", {}).copy()
            updated_overall_results[group_name] = group_state_update
            return {"overall_group_results": updated_overall_results}

        group_state_update["grok_pattern_string"] = pattern_str

        compiled_grok = self.grok_pattern_service.get_compiled_grok_instance(
            group_name, pattern_str
        )
        if not compiled_grok:
            msg = f"Group '{group_name}': Failed to compile Grok pattern '{pattern_str}'. Cannot process."
            self._logger.error(msg)
            group_state_update["group_status"] = "failed_pattern_compile"
            group_state_update["group_error_messages"].append(msg)
            updated_overall_results = state.get("overall_group_results", {}).copy()
            updated_overall_results[group_name] = group_state_update
            return {"overall_group_results": updated_overall_results}

        log_file_ids = self.es_service.get_log_file_ids_for_group(group_name)
        if not log_file_ids:
            self._logger.info(
                f"Group '{group_name}': No log files (IDs) found in its source index. Marking as completed."
            )
            group_state_update["group_status"] = "completed_no_files"
        else:
            group_state_update["all_log_file_ids_in_group"] = log_file_ids
            group_state_update["group_status"] = "processing_files"
            self._logger.info(
                f"Group '{group_name}': Found {len(log_file_ids)} files to process. Pattern to be used: '{pattern_str}'"
            )

        updated_overall_results = state.get("overall_group_results", {}).copy()
        updated_overall_results[group_name] = group_state_update
        return {"overall_group_results": updated_overall_results}

    def _orchestrator_process_files_for_group_node(
        self, state: StaticGrokParserOrchestratorState
    ) -> Dict[str, Any]:
        idx = state["current_group_processing_index"]
        group_name = state["all_group_names_from_db"][idx]

        current_group_data = state["overall_group_results"].get(group_name)  # type: ignore
        if not current_group_data or current_group_data.get("group_status") not in [
            "processing_files"
        ]:
            self._logger.warning(
                f"Group '{group_name}' not in a state to process files (status: {current_group_data.get('group_status')}). Advancing group."
            )
            return {}

        grok_pattern_for_group = current_group_data.get(
            "grok_pattern_string", "PATTERN_NOT_SET_IN_GROUP_DATA"
        )
        self._logger.info(
            f"Orchestrator: Processing files for Group '{group_name}'. Using Grok pattern: '{grok_pattern_for_group}'"
        )

        grok_instance = self.grok_pattern_service.get_compiled_grok_instance(
            group_name, grok_pattern_for_group
        )
        if not grok_instance:
            msg = f"Group '{group_name}': Critical - Grok instance unavailable for pattern '{grok_pattern_for_group}' during file processing."
            self._logger.error(msg)
            current_group_data["group_status"] = "failed_pattern_compile"
            current_group_data["group_error_messages"].append(msg)
            return {
                "overall_group_results": {
                    **state["overall_group_results"],
                    group_name: current_group_data,
                }
            }

        derived_field_definitions = (
            self.grok_pattern_service.get_derived_field_definitions_for_group(
                group_name
            )
        )

        all_files_in_this_group = current_group_data.get(
            "all_log_file_ids_in_group", []
        )
        for file_idx_in_group_loop, log_file_id in enumerate(all_files_in_this_group):
            self._logger.debug(
                f"Group '{group_name}': File {file_idx_in_group_loop+1}/{len(all_files_in_this_group)} - ID '{log_file_id}'"
            )

            file_run_state = current_group_data.get(
                "files_processed_summary_this_run", {}
            ).get(log_file_id, {})
            if not file_run_state:
                file_run_state = LogFileProcessingState(  # type: ignore
                    log_file_id=log_file_id,
                    group_name=group_name,
                    grok_pattern_string=grok_pattern_for_group,
                    last_line_parsed_by_grok=0,
                    current_total_lines_by_collector=0,
                    max_line_processed_this_session=0,
                    new_lines_scanned_this_session=0,
                    parsed_actions_batch=[],
                    unparsed_actions_batch=[],
                    status_this_session="pending",
                    error_message_this_session=None,
                )

            persistent_grok_status = self.es_service.get_grok_parse_status_for_file(
                log_file_id
            )
            collector_total_lines = self.es_service.get_collector_status_for_file(
                log_file_id
            )

            file_run_state["last_line_parsed_by_grok"] = persistent_grok_status[
                "last_line_parsed_by_grok"
            ]
            file_run_state["current_total_lines_by_collector"] = collector_total_lines
            file_run_state["max_line_processed_this_session"] = persistent_grok_status[
                "last_line_parsed_by_grok"
            ]

            if (
                file_run_state["last_line_parsed_by_grok"] >= collector_total_lines
                and collector_total_lines > 0
            ):
                self._logger.info(
                    f"File '{log_file_id}' (Group '{group_name}'): Already parsed up to collector line {collector_total_lines}. Skipping scan."
                )
                # Update status to ensure it reflects current collector state
                self.es_service.save_grok_parse_status_for_file(
                    log_file_id=log_file_id,
                    group_name=group_name,  # Pass group_name
                    log_file_relative_path=persistent_grok_status.get(
                        "log_file_relative_path", "N/A_path_in_agent"
                    ),  # Use existing or placeholder
                    last_line_parsed_by_grok=file_run_state["last_line_parsed_by_grok"],
                    current_total_lines_by_collector=collector_total_lines,
                    last_parse_status_str="skipped_up_to_date",
                )
                file_run_state["status_this_session"] = "skipped_up_to_date"
                current_group_data.setdefault("files_processed_summary_this_run", {})[
                    log_file_id
                ] = file_run_state
                continue

            if (
                collector_total_lines == 0
                and file_run_state["last_line_parsed_by_grok"] > 0
            ):
                self._logger.warning(
                    f"File '{log_file_id}' (Group '{group_name}'): Collector reports 0 lines, but Grok previously parsed {file_run_state['last_line_parsed_by_grok']}. Resetting Grok's line count for this file."
                )
                file_run_state["last_line_parsed_by_grok"] = 0
                file_run_state["max_line_processed_this_session"] = 0

            # Store the relative path from the first hit for this file
            # to be used when saving the final status for this file.
            # It's a bit of a workaround as we get it per-hit but only need one for the file status.
            # Initialize file_relative_path_for_status here
            file_relative_path_for_status = persistent_grok_status.get(
                "log_file_relative_path", "N/A_path_not_found_yet"
            )

            def scroll_callback_for_file(hits_batch: List[Dict[str, Any]]) -> bool:
                nonlocal file_run_state, file_relative_path_for_status
                if not hits_batch:
                    return True
                num_parsed_in_batch = 0
                num_unparsed_in_batch = 0

                for hit_item_idx, hit_item in enumerate(hits_batch):
                    hit_source = hit_item.get("_source", {})

                    # Capture relative path from the first hit in the first batch
                    if (
                        hit_item_idx == 0
                        and file_relative_path_for_status == "N/A_path_not_found_yet"
                    ):
                        path_from_hit = hit_source.get(
                            "name"
                        )  # 'name' is the relative path from collector
                        if path_from_hit:
                            file_relative_path_for_status = path_from_hit

                    content = hit_source.get("content", "")
                    line_num = hit_source.get("line_number")

                    if line_num is None:
                        self._logger.warning(
                            f"File '{log_file_id}', Group '{group_name}': Hit missing line_number, skipping hit: {hit_item.get('_id')}"
                        )
                        continue

                    file_run_state["max_line_processed_this_session"] = max(
                        file_run_state["max_line_processed_this_session"], line_num
                    )

                    parsed_grok_fields_initial = self.grok_parsing_service.parse_line(
                        content, grok_instance
                    )
                    doc_id_for_target = f"{log_file_id}_{line_num}"

                    if parsed_grok_fields_initial:
                        context_for_derivation = {
                            "log_file_id": log_file_id,
                            "line_num": line_num,
                            "group_name": group_name,
                        }
                        final_parsed_fields = (
                            self.derived_field_processor.process_derived_fields(
                                parsed_grok_fields_initial.copy(),
                                derived_field_definitions,
                                context_info=context_for_derivation,
                            )
                        )

                        doc_src = self._prepare_parsed_doc_source(
                            hit_source, group_name, final_parsed_fields
                        )
                        file_run_state["parsed_actions_batch"].append(
                            self._format_es_action(
                                current_group_data["parsed_log_index"],
                                doc_id_for_target,
                                doc_src,
                            )
                        )
                        num_parsed_in_batch += 1
                    else:
                        doc_src = self._prepare_unparsed_doc_source(
                            hit_source, group_name, "grok_mismatch"
                        )
                        file_run_state["unparsed_actions_batch"].append(
                            self._format_es_action(
                                current_group_data["unparsed_log_index"],
                                doc_id_for_target,
                                doc_src,
                            )
                        )
                        num_unparsed_in_batch += 1

                # Logging and batch flushing logic (remains the same)
                if num_parsed_in_batch > 0 or num_unparsed_in_batch > 0:
                    self._logger.info(
                        f"File '{log_file_id}' (Group '{group_name}'): Batch processed. Parsed: {num_parsed_in_batch}, Unparsed: {num_unparsed_in_batch}. Pattern: '{grok_pattern_for_group}'"
                    )

                if (
                    len(file_run_state["parsed_actions_batch"])
                    >= FILE_PROCESSING_BULK_INDEX_BATCH_SIZE
                ):
                    self._logger.debug(
                        f"File '{log_file_id}': Flushing {len(file_run_state['parsed_actions_batch'])} parsed actions during scroll."
                    )
                    self.es_service.bulk_index_formatted_actions(
                        file_run_state["parsed_actions_batch"]
                    )
                    file_run_state["parsed_actions_batch"].clear()

                if (
                    len(file_run_state["unparsed_actions_batch"])
                    >= FILE_PROCESSING_BULK_INDEX_BATCH_SIZE
                ):
                    self._logger.debug(
                        f"File '{log_file_id}': Flushing {len(file_run_state['unparsed_actions_batch'])} unparsed actions during scroll."
                    )
                    self.es_service.bulk_index_formatted_actions(
                        file_run_state["unparsed_actions_batch"]
                    )
                    file_run_state["unparsed_actions_batch"].clear()
                return True

            scrolled_lines_for_file, _ = (
                self.es_service.scroll_and_process_raw_log_lines(
                    source_index=current_group_data["source_log_index"],
                    log_file_id=log_file_id,
                    start_line_number_exclusive=file_run_state[
                        "last_line_parsed_by_grok"
                    ],
                    scroll_batch_size=FILE_PROCESSING_SCROLL_BATCH_SIZE,
                    process_batch_callback=scroll_callback_for_file,
                )
            )
            file_run_state["new_lines_scanned_this_session"] = scrolled_lines_for_file

            parsed_count_this_file_session = 0
            unparsed_count_this_file_session = 0

            if file_run_state["parsed_actions_batch"]:
                parsed_count_this_file_session = len(
                    file_run_state["parsed_actions_batch"]
                )
                self.es_service.bulk_index_formatted_actions(
                    file_run_state["parsed_actions_batch"]
                )
                file_run_state["parsed_actions_batch"].clear()
            if file_run_state["unparsed_actions_batch"]:
                unparsed_count_this_file_session = len(
                    file_run_state["unparsed_actions_batch"]
                )
                self.es_service.bulk_index_formatted_actions(
                    file_run_state["unparsed_actions_batch"]
                )
                file_run_state["unparsed_actions_batch"].clear()

            current_file_status_str = ""
            if scrolled_lines_for_file > 0:
                file_run_state["status_this_session"] = "completed_new_data"
                current_file_status_str = "completed_new_data"
            else:
                file_run_state["status_this_session"] = "completed_no_new_data"
                current_file_status_str = "completed_no_new_data"

            # If file_relative_path_for_status is still the placeholder, it means no lines were scrolled for this file
            # or the 'name' field was missing in all scrolled hits.
            if file_relative_path_for_status == "N/A_path_not_found_yet":
                # Attempt to get it from existing status, or mark as unknown
                file_relative_path_for_status = persistent_grok_status.get(
                    "log_file_relative_path", "UnknownRelativePath"
                )

            self.es_service.save_grok_parse_status_for_file(
                log_file_id=log_file_id,
                group_name=group_name,
                log_file_relative_path=file_relative_path_for_status,
                last_line_parsed_by_grok=file_run_state[
                    "max_line_processed_this_session"
                ],
                current_total_lines_by_collector=collector_total_lines,
                last_parse_status_str=current_file_status_str,
            )
            current_group_data.setdefault("files_processed_summary_this_run", {})[
                log_file_id
            ] = file_run_state
            self._logger.info(
                f"File '{log_file_id}' (Group '{group_name}', Path '{file_relative_path_for_status}'): Processing complete. "
                f"Status: {file_run_state['status_this_session']}. "
                f"New lines scanned this session: {scrolled_lines_for_file}. "
                f"Final batch indexed - Parsed: {parsed_count_this_file_session}, Unparsed: {unparsed_count_this_file_session}. "
                f"Max line number processed in this session: {file_run_state['max_line_processed_this_session']}. "
                f"Pattern used: '{grok_pattern_for_group}'"
            )

        current_group_data["group_status"] = "completed"
        self._logger.info(
            f"Orchestrator: Finished processing all files for Group '{group_name}'. Pattern used for group: '{grok_pattern_for_group}'"
        )

        updated_overall_results = state["overall_group_results"].copy()
        updated_overall_results[group_name] = current_group_data
        return {"overall_group_results": updated_overall_results}

    def _orchestrator_advance_group_node(
        self, state: StaticGrokParserOrchestratorState
    ) -> Dict[str, Any]:
        new_index = state["current_group_processing_index"] + 1
        if new_index < len(state["all_group_names_from_db"]):
            self._logger.debug(
                f"Orchestrator: Advancing to next group index {new_index}."
            )
            return {"current_group_processing_index": new_index}
        else:
            self._logger.info("Orchestrator: All groups have been processed.")
            return {
                "current_group_processing_index": new_index,
                "orchestrator_status": "completed",
            }

    def _orchestrator_should_process_more_groups(
        self, state: StaticGrokParserOrchestratorState
    ) -> str:
        if state["orchestrator_status"] == "completed_no_groups":
            return END

        current_idx = state["current_group_processing_index"]
        if current_idx < len(state["all_group_names_from_db"]):
            return "initialize_group_processing"
        else:
            self._logger.info("Orchestrator: Decision - No more groups to process.")
            return END

    def _orchestrator_check_group_initialization_status(
        self, state: StaticGrokParserOrchestratorState
    ) -> str:
        idx = state["current_group_processing_index"]
        group_name = state["all_group_names_from_db"][idx]
        group_data = state["overall_group_results"].get(group_name)

        if not group_data:
            self._logger.error(
                f"Orchestrator: Critical - No data for group '{group_name}' after initialization attempt. Advancing."
            )
            return "advance_group_processing"

        group_status = group_data.get("group_status")
        if group_status in [
            "failed_no_pattern",
            "failed_pattern_compile",
            "completed_no_files",
        ]:
            self._logger.info(
                f"Orchestrator: Group '{group_name}' initialization resulted in status '{group_status}'. Skipping file processing for this group."
            )
            return "advance_group_processing"
        elif group_status == "processing_files":
            self._logger.info(
                f"Orchestrator: Group '{group_name}' initialized successfully. Proceeding to process its files."
            )
            return "process_files_for_group"
        else:
            self._logger.warning(
                f"Orchestrator: Group '{group_name}' has unexpected status '{group_status}' after initialization. Advancing."
            )
            return "advance_group_processing"

    def _build_orchestrator_graph(self) -> CompiledGraph:
        graph = StateGraph(StaticGrokParserOrchestratorState)

        graph.add_node("start_orchestration", self._orchestrator_start_node)
        graph.add_node(
            "initialize_group_processing",
            self._orchestrator_initialize_group_processing_node,
        )
        graph.add_node(
            "process_files_for_group", self._orchestrator_process_files_for_group_node
        )
        graph.add_node(
            "advance_group_processing", self._orchestrator_advance_group_node
        )

        graph.set_entry_point("start_orchestration")

        graph.add_conditional_edges(
            "start_orchestration",
            self._orchestrator_should_process_more_groups,
            {"initialize_group_processing": "initialize_group_processing", END: END},
        )

        graph.add_conditional_edges(
            "initialize_group_processing",
            self._orchestrator_check_group_initialization_status,
            {
                "process_files_for_group": "process_files_for_group",
                "advance_group_processing": "advance_group_processing",
            },
        )

        graph.add_edge("process_files_for_group", "advance_group_processing")

        graph.add_conditional_edges(
            "advance_group_processing",
            self._orchestrator_should_process_more_groups,
            {"initialize_group_processing": "initialize_group_processing", END: END},
        )

        return graph.compile()

    def run(
        self,  # Added optional parameter to clear records
        clear_records_for_groups: Optional[
            List[str]
        ] = None,  # List of group names to clear
        clear_all_group_records: bool = False,  # Flag to clear all
    ) -> StaticGrokParserOrchestratorState:
        self._logger.info(
            "StaticGrokParserAgent (LangGraph Orchestrator): Initiating agent run..."
        )

        # --- PRE-RUN: Clear records if requested ---
        groups_to_clear_actually = []
        if clear_all_group_records:
            self._logger.warning(
                "Flag --clear-all-groups is set. Will attempt to clear records for ALL known groups."
            )
            # Fetch all groups if not explicitly provided for clearing
            # This is a bit redundant if agent fetches them again, but ensures we clear before state init.
            # Alternatively, the agent's start node could determine groups, then we clear.
            # For safety, let's assume we need to know groups to clear *before* agent.run() fully populates its own list.
            # This might mean an extra DB call if 'clear_records_for_groups' is not also 'all'.
            all_db_groups = self.es_service.get_all_log_group_names()
            if not all_db_groups:
                self._logger.info(
                    "No groups found in DB to clear for --clear-all-groups."
                )
            groups_to_clear_actually.extend(all_db_groups)

        elif clear_records_for_groups:
            self._logger.info(
                f"Will attempt to clear records for specified groups: {clear_records_for_groups}"
            )
            groups_to_clear_actually.extend(clear_records_for_groups)

        if groups_to_clear_actually:
            unique_groups_to_clear = list(set(groups_to_clear_actually))  # Deduplicate
            self._logger.info(
                f"Proceeding to clear data for groups: {unique_groups_to_clear}"
            )
            for group_name_to_clear in unique_groups_to_clear:
                self._clear_group_data(group_name_to_clear)
        # --- END PRE-RUN CLEAR ---

        initial_orchestrator_state: StaticGrokParserOrchestratorState = {  # type: ignore
            "all_group_names_from_db": [],
            "current_group_processing_index": 0,
            "overall_group_results": {},
            "orchestrator_status": "pending",
            "orchestrator_error_messages": [],
        }

        final_state: StaticGrokParserOrchestratorState = self.graph.invoke(initial_orchestrator_state)  # type: ignore

        self._logger.info(
            f"StaticGrokParserAgent (LangGraph Orchestrator): Run finished. Final orchestrator status: {final_state.get('orchestrator_status')}"
        )

        self._logger.info("--- Agent Run Final Summary ---")
        for group_name, group_data in final_state.get(
            "overall_group_results", {}
        ).items():
            group_status = group_data.get("group_status", "unknown")
            group_errors = group_data.get("group_error_messages", [])
            grok_pattern_used_for_group = group_data.get("grok_pattern_string", "N/A")

            files_summary = group_data.get("files_processed_summary_this_run", {})
            total_new_lines_scanned_in_group = 0
            total_files_with_new_data_in_group = 0

            for _file_id, file_detail in files_summary.items():
                if file_detail.get("status_this_session") == "completed_new_data":
                    total_files_with_new_data_in_group += 1
                    total_new_lines_scanned_in_group += file_detail.get(
                        "new_lines_scanned_this_session", 0
                    )

            self._logger.info(
                f"  Group '{group_name}': Final Status='{group_status}', Pattern Used='{grok_pattern_used_for_group}'. "
                f"Files with new data this run: {total_files_with_new_data_in_group}. "
                f"Total new lines parsed/unparsed in group this run: {total_new_lines_scanned_in_group}. "
                f"Group Errors: {group_errors if group_errors else 'None'}"
            )
        self._logger.info("--- End of Agent Run Final Summary ---")

        return final_state  # type: ignore

    def _clear_group_data(self, group_name: str):
        """Helper to clear parsed indices and status entries for a group."""
        self._logger.warning(
            f"Clearing previously parsed data and status for group: {group_name}"
        )

        parsed_idx = cfg.get_parsed_log_storage_index(group_name)
        unparsed_idx = cfg.get_unparsed_log_storage_index(group_name)

        self.es_service.delete_index_if_exists(parsed_idx)
        self.es_service.delete_index_if_exists(unparsed_idx)

        log_file_ids_in_group = self.es_service.get_log_file_ids_for_group(group_name)
        if log_file_ids_in_group:
            s_count, e_count = self.es_service.delete_status_entries_for_file_ids(
                log_file_ids_in_group
            )
            self._logger.info(
                f"Deleted {s_count} status entries for group '{group_name}' (errors: {e_count})."
            )
        else:
            self._logger.info(
                f"No log file IDs found for group '{group_name}' to clear from status index, or source index itself is missing."
            )
