# src/logllm/agents/static_grok_parser/__init__.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph

# Removed: import string - no longer needed here


try:
    from ...config import config as cfg
    from ...utils.database import ElasticsearchDatabase
    from ...utils.logger import Logger
except ImportError:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from utils.database import ElasticsearchDatabase
    from utils.logger import Logger
    from config import config as cfg

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
        self.derived_field_processor = DerivedFieldProcessor(
            logger=self._logger
        )  # INITIALIZE

        self.graph: CompiledGraph = self._build_orchestrator_graph()

    # --- Helper to prepare ES actions ---
    def _format_es_action(self, index_name: str, doc_id: str, doc_source: Dict) -> Dict:
        return {
            "_op_type": "index",
            "_index": index_name,
            "_id": doc_id,
            "_source": doc_source,
        }

    def _prepare_parsed_doc_source(
        self,
        original_es_hit_source: Dict,
        group_name: str,
        processed_grok_fields: Dict,  # Renamed from parsed_grok_fields
    ) -> Dict:
        doc_id = original_es_hit_source.get("id")
        line_num = original_es_hit_source.get("line_number")

        # `processed_grok_fields` now already includes derived fields
        parsed_doc_source = {
            **processed_grok_fields,
            "original_log_file_id": doc_id,
            "original_log_file_name": original_es_hit_source.get("name"),
            "original_line_number": line_num,
            "original_content": original_es_hit_source.get("content"),
            "parsed_by_agent": "StaticGrokParserAgent_LG",
            "grok_pattern_group": group_name,
        }
        if "ingestion_timestamp" in original_es_hit_source:
            parsed_doc_source["original_ingestion_timestamp"] = original_es_hit_source[
                "ingestion_timestamp"
            ]

        return parsed_doc_source

    def _prepare_unparsed_doc_source(
        self, original_es_hit_source: Dict, group_name: str, reason: str
    ) -> Dict:
        doc_id = original_es_hit_source.get("id")
        line_num = original_es_hit_source.get("line_number")

        unparsed_doc = {
            "original_log_file_id": doc_id,
            "original_log_file_name": original_es_hit_source.get("name"),
            "original_line_number": line_num,
            "original_content": original_es_hit_source.get("content"),
            "reason_unparsed": reason,
            "grok_pattern_group_attempted": group_name,
            "parser_agent": "StaticGrokParserAgent_LG",
        }
        if "ingestion_timestamp" in original_es_hit_source:
            unparsed_doc["original_ingestion_timestamp"] = original_es_hit_source[
                "ingestion_timestamp"
            ]
        return unparsed_doc

    # --- Orchestrator Graph Nodes ---
    # ... (_orchestrator_start_node, _orchestrator_initialize_group_processing_node are unchanged)
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

        current_group_data = state["overall_group_results"].get(group_name)
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
        if not grok_instance:  # Should be caught by init, but double check
            msg = f"Group '{group_name}': Critical - Grok instance unavailable for pattern '{grok_pattern_for_group}' during file processing."
            self._logger.error(msg)
            current_group_data["group_status"] = "failed_pattern_compile"  # type: ignore
            current_group_data["group_error_messages"].append(msg)  # type: ignore
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

        all_files_in_this_group = current_group_data.get(  # type: ignore
            "all_log_file_ids_in_group", []
        )
        for file_idx_in_group_loop, log_file_id in enumerate(all_files_in_this_group):
            self._logger.debug(
                f"Group '{group_name}': File {file_idx_in_group_loop+1}/{len(all_files_in_this_group)} - ID '{log_file_id}'"
            )

            file_run_state = current_group_data.get(  # type: ignore
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

            file_run_state["last_line_parsed_by_grok"] = persistent_grok_status[  # type: ignore
                "last_line_parsed_by_grok"
            ]
            file_run_state["current_total_lines_by_collector"] = collector_total_lines  # type: ignore
            file_run_state["max_line_processed_this_session"] = persistent_grok_status[  # type: ignore
                "last_line_parsed_by_grok"
            ]

            if (
                file_run_state["last_line_parsed_by_grok"] >= collector_total_lines  # type: ignore
                and collector_total_lines > 0
            ):
                self._logger.info(
                    f"File '{log_file_id}' (Group '{group_name}'): Already parsed up to collector line {collector_total_lines}. Updating persistent status and skipping scan."
                )
                self.es_service.save_grok_parse_status_for_file(
                    log_file_id,
                    file_run_state["last_line_parsed_by_grok"],  # type: ignore
                    collector_total_lines,
                )
                file_run_state["status_this_session"] = "skipped_up_to_date"  # type: ignore
                current_group_data.setdefault("files_processed_summary_this_run", {})[  # type: ignore
                    log_file_id
                ] = file_run_state
                continue

            if (
                collector_total_lines == 0
                and file_run_state["last_line_parsed_by_grok"] > 0  # type: ignore
            ):
                self._logger.warning(
                    f"File '{log_file_id}' (Group '{group_name}'): Collector reports 0 lines, but Grok previously parsed {file_run_state['last_line_parsed_by_grok']}. Resetting Grok's line count for this file."  # type: ignore
                )
                file_run_state["last_line_parsed_by_grok"] = 0  # type: ignore
                file_run_state["max_line_processed_this_session"] = 0  # type: ignore

            def scroll_callback_for_file(hits_batch: List[Dict[str, Any]]) -> bool:
                nonlocal file_run_state
                if not hits_batch:
                    return True
                num_parsed_in_batch = 0
                num_unparsed_in_batch = 0

                for hit_item in hits_batch:
                    hit_source = hit_item.get("_source", {})
                    content = hit_source.get("content", "")
                    line_num = hit_source.get("line_number")

                    if line_num is None:
                        self._logger.warning(
                            f"File '{log_file_id}', Group '{group_name}': Hit missing line_number, skipping hit: {hit_item.get('_id')}"
                        )
                        continue

                    file_run_state["max_line_processed_this_session"] = max(  # type: ignore
                        file_run_state["max_line_processed_this_session"], line_num  # type: ignore
                    )

                    # Initial Grok parsing
                    parsed_grok_fields_initial = self.grok_parsing_service.parse_line(
                        content, grok_instance  # type: ignore
                    )
                    doc_id_for_target = f"{log_file_id}_{line_num}"

                    if parsed_grok_fields_initial:
                        # Process derived fields using the new service
                        context_for_derivation = {
                            "log_file_id": log_file_id,
                            "line_num": line_num,
                            "group_name": group_name,
                        }
                        # The process_derived_fields modifies parsed_grok_fields_initial in place
                        final_parsed_fields = self.derived_field_processor.process_derived_fields(
                            parsed_grok_fields_initial.copy(),  # Pass a copy to avoid modifying original if needed later
                            derived_field_definitions,
                            context_info=context_for_derivation,
                        )

                        doc_src = self._prepare_parsed_doc_source(
                            hit_source,
                            group_name,
                            final_parsed_fields,  # Use the final fields
                        )
                        file_run_state["parsed_actions_batch"].append(  # type: ignore
                            self._format_es_action(
                                current_group_data["parsed_log_index"],  # type: ignore
                                doc_id_for_target,
                                doc_src,
                            )
                        )
                        num_parsed_in_batch += 1
                        self._logger.debug(
                            f"File '{log_file_id}' L{line_num} PARSED (Group '{group_name}', Pattern '{grok_pattern_for_group}')"
                        )
                    else:  # Grok parsing failed
                        doc_src = self._prepare_unparsed_doc_source(
                            hit_source, group_name, "grok_mismatch"
                        )
                        file_run_state["unparsed_actions_batch"].append(  # type: ignore
                            self._format_es_action(
                                current_group_data["unparsed_log_index"],  # type: ignore
                                doc_id_for_target,
                                doc_src,
                            )
                        )
                        num_unparsed_in_batch += 1
                        self._logger.debug(
                            f"File '{log_file_id}' L{line_num} UNPARSED (Group '{group_name}', Pattern '{grok_pattern_for_group}')"
                        )

                if num_parsed_in_batch > 0 or num_unparsed_in_batch > 0:
                    self._logger.info(
                        f"File '{log_file_id}' (Group '{group_name}'): Batch processed. Parsed: {num_parsed_in_batch}, Unparsed: {num_unparsed_in_batch}. Pattern: '{grok_pattern_for_group}'"
                    )

                if (
                    len(file_run_state["parsed_actions_batch"])  # type: ignore
                    >= FILE_PROCESSING_BULK_INDEX_BATCH_SIZE
                ):
                    self._logger.debug(
                        f"File '{log_file_id}': Flushing {len(file_run_state['parsed_actions_batch'])} parsed actions during scroll."  # type: ignore
                    )
                    self.es_service.bulk_index_formatted_actions(
                        file_run_state["parsed_actions_batch"]  # type: ignore
                    )
                    file_run_state["parsed_actions_batch"].clear()  # type: ignore

                if (
                    len(file_run_state["unparsed_actions_batch"])  # type: ignore
                    >= FILE_PROCESSING_BULK_INDEX_BATCH_SIZE
                ):
                    self._logger.debug(
                        f"File '{log_file_id}': Flushing {len(file_run_state['unparsed_actions_batch'])} unparsed actions during scroll."  # type: ignore
                    )
                    self.es_service.bulk_index_formatted_actions(
                        file_run_state["unparsed_actions_batch"]  # type: ignore
                    )
                    file_run_state["unparsed_actions_batch"].clear()  # type: ignore
                return True

            scrolled_lines_for_file, _ = (
                self.es_service.scroll_and_process_raw_log_lines(
                    source_index=current_group_data["source_log_index"],  # type: ignore
                    log_file_id=log_file_id,
                    start_line_number_exclusive=file_run_state[  # type: ignore
                        "last_line_parsed_by_grok"
                    ],
                    scroll_batch_size=FILE_PROCESSING_SCROLL_BATCH_SIZE,
                    process_batch_callback=scroll_callback_for_file,
                )
            )
            file_run_state["new_lines_scanned_this_session"] = scrolled_lines_for_file  # type: ignore

            parsed_count_this_file_session = 0
            unparsed_count_this_file_session = 0

            if file_run_state["parsed_actions_batch"]:  # type: ignore
                parsed_count_this_file_session = len(
                    file_run_state["parsed_actions_batch"]  # type: ignore
                )
                self.es_service.bulk_index_formatted_actions(
                    file_run_state["parsed_actions_batch"]  # type: ignore
                )
                file_run_state["parsed_actions_batch"].clear()  # type: ignore
            if file_run_state["unparsed_actions_batch"]:  # type: ignore
                unparsed_count_this_file_session = len(
                    file_run_state["unparsed_actions_batch"]  # type: ignore
                )
                self.es_service.bulk_index_formatted_actions(
                    file_run_state["unparsed_actions_batch"]  # type: ignore
                )
                file_run_state["unparsed_actions_batch"].clear()  # type: ignore

            if scrolled_lines_for_file > 0:
                file_run_state["status_this_session"] = "completed_new_data"  # type: ignore
            else:
                file_run_state["status_this_session"] = "completed_no_new_data"  # type: ignore

            self.es_service.save_grok_parse_status_for_file(
                log_file_id,
                file_run_state["max_line_processed_this_session"],  # type: ignore
                collector_total_lines,
            )
            current_group_data.setdefault("files_processed_summary_this_run", {})[  # type: ignore
                log_file_id
            ] = file_run_state
            self._logger.info(
                f"File '{log_file_id}' (Group '{group_name}'): Processing complete. "
                f"Status: {file_run_state['status_this_session']}. "  # type: ignore
                f"New lines scanned this session: {scrolled_lines_for_file}. "
                f"Final batch indexed - Parsed: {parsed_count_this_file_session}, Unparsed: {unparsed_count_this_file_session}. "
                f"Max line number processed in this session: {file_run_state['max_line_processed_this_session']}. "  # type: ignore
                f"Pattern used: '{grok_pattern_for_group}'"
            )

        current_group_data["group_status"] = "completed"  # type: ignore
        self._logger.info(
            f"Orchestrator: Finished processing all files for Group '{group_name}'. Pattern used for group: '{grok_pattern_for_group}'"
        )

        updated_overall_results = state["overall_group_results"].copy()
        updated_overall_results[group_name] = current_group_data  # type: ignore
        return {"overall_group_results": updated_overall_results}

    # ... (_orchestrator_advance_group_node, conditional edges, _build_orchestrator_graph, run are unchanged)
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

    # --- Orchestrator Conditional Edges ---
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

    # --- Build Orchestrator Graph ---
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

    def run(self) -> StaticGrokParserOrchestratorState:
        self._logger.info(
            "StaticGrokParserAgent (LangGraph Orchestrator): Initiating agent run..."
        )
        initial_orchestrator_state: StaticGrokParserOrchestratorState = {  # type: ignore
            "all_group_names_from_db": [],
            "current_group_processing_index": 0,
            "overall_group_results": {},
            "orchestrator_status": "pending",
            "orchestrator_error_messages": [],
        }

        final_state: StaticGrokParserOrchestratorState = self.graph.invoke(initial_orchestrator_state)  # type: ignore

        self._logger.info(
            f"StaticGrokParserAgent (LangGraph Orchestrator): Run finished. Final orchestrator status: {final_state.get('orchestrator_status')}"  # type: ignore
        )

        self._logger.info("--- Agent Run Final Summary ---")
        for group_name, group_data in final_state.get(  # type: ignore
            "overall_group_results", {}
        ).items():
            group_status = group_data.get("group_status", "unknown")
            group_errors = group_data.get("group_error_messages", [])
            grok_pattern_used_for_group = group_data.get("grok_pattern_string", "N/A")

            files_summary = group_data.get("files_processed_summary_this_run", {})
            total_new_lines_scanned_in_group = 0
            total_files_with_new_data_in_group = 0

            for file_id, file_detail in files_summary.items():
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
