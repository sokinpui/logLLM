# src/logllm/agents/timestamp_normalizer/__init__.py
from typing import Any, Dict, List, Optional, Tuple

from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph

from ...config import config as cfg
from ...utils.database import ElasticsearchDatabase
from ...utils.logger import Logger
from .api.es_data_service import TimestampESDataService
from .api.timestamp_normalization_service import TimestampNormalizationService
from .states import (
    TimestampNormalizerGroupState,
    TimestampNormalizerOrchestratorState,
)

DEFAULT_BATCH_SIZE_NORMALIZER = 5000


class TimestampNormalizerAgent:
    """
    A LangGraph-based agent to orchestrate timestamp normalization or
    field removal across multiple log groups.
    """

    def __init__(self, db: ElasticsearchDatabase):
        self._logger = Logger()
        # Initialize services
        self.es_service = TimestampESDataService(db, logger=self._logger)
        self.normalization_service = TimestampNormalizationService(logger=self._logger)
        self.graph: CompiledGraph = self._build_graph()

    # --- Graph Node Implementations ---

    def _orchestrator_start_node(
        self, state: TimestampNormalizerOrchestratorState
    ) -> Dict[str, Any]:
        self._logger.info(
            f"Orchestrator: Starting Timestamp Normalizer run. Action: '{state['action_to_perform']}'."
        )

        all_db_groups: List[str] = []
        if state["target_group_names"] is None:  # Process all groups if none specified
            all_db_groups = self.es_service.get_all_log_group_names()
            if not all_db_groups:
                self._logger.warning(
                    "Orchestrator: No log groups found in DB and no specific groups targeted. Nothing to process."
                )
                return {
                    "groups_to_process_resolved": [],
                    "current_group_processing_index": 0,
                    "orchestrator_status": "completed_no_groups",
                    "overall_group_results": {},
                }
            state["all_group_names_from_db"] = all_db_groups
            state["groups_to_process_resolved"] = all_db_groups
        else:
            state["groups_to_process_resolved"] = state["target_group_names"]
            self._logger.info(
                f"Orchestrator: Targeting specific groups: {state['target_group_names']}"
            )

        self._logger.info(
            f"Orchestrator: Will process {len(state['groups_to_process_resolved'])} groups: {state['groups_to_process_resolved']}"
        )
        return {
            "current_group_processing_index": 0,
            "orchestrator_status": "processing_groups",
            "overall_group_results": {},
            "groups_to_process_resolved": state["groups_to_process_resolved"],
            "all_group_names_from_db": state.get("all_group_names_from_db", []),
        }

    def _orchestrator_initialize_group_node(
        self, state: TimestampNormalizerOrchestratorState
    ) -> Dict[str, Any]:
        idx = state["current_group_processing_index"]
        group_name = state["groups_to_process_resolved"][idx]
        self._logger.info(
            f"Orchestrator: Initializing processing for Group '{group_name}' (index {idx}). Action: {state['action_to_perform']}"
        )

        parsed_log_index = cfg.get_parsed_log_storage_index(group_name)

        group_run_state = TimestampNormalizerGroupState(
            group_name=group_name,
            parsed_log_index=parsed_log_index,
            status_this_run="pending",
            error_message_this_run=None,
            documents_scanned_this_run=0,
            documents_updated_this_run=0,
            timestamp_normalization_errors_this_run=0,
        )

        if not self.es_service.check_index_exists(parsed_log_index):
            msg = f"Index '{parsed_log_index}' for group '{group_name}' does not exist. Cannot process."
            self._logger.warning(msg)
            group_run_state["status_this_run"] = "failed_index_not_found"
            group_run_state["error_message_this_run"] = msg

        updated_overall_results = state.get("overall_group_results", {}).copy()
        updated_overall_results[group_name] = group_run_state
        return {"overall_group_results": updated_overall_results}

    def _process_group_node(
        self, state: TimestampNormalizerOrchestratorState
    ) -> Dict[str, Any]:
        idx = state["current_group_processing_index"]
        group_name = state["groups_to_process_resolved"][idx]

        current_group_data: TimestampNormalizerGroupState = state["overall_group_results"][group_name]  # type: ignore

        if current_group_data["status_this_run"] == "failed_index_not_found":
            self._logger.info(
                f"Group '{group_name}': Skipping processing due to missing index."
            )
            return {}

        action = state["action_to_perform"]
        parsed_log_index = current_group_data["parsed_log_index"]
        batch_size = state["batch_size"]
        limit = state.get("limit_per_group")

        self._logger.info(
            f"Group '{group_name}': Starting action '{action}' on index '{parsed_log_index}'."
        )
        current_group_data["status_this_run"] = (
            "normalizing" if action == "normalize" else "removing_field"
        )

        docs_updated_this_group = 0
        norm_errors_this_group = 0

        def batch_callback(hits_batch: List[Dict[str, Any]]) -> bool:
            nonlocal docs_updated_this_group, norm_errors_this_group

            if not hits_batch:
                return True

            update_actions: List[Dict[str, Any]] = []

            if action == "normalize":
                for hit in hits_batch:
                    doc_id = hit.get("_id")
                    source = hit.get("_source")
                    if not doc_id or source is None:
                        continue

                    original_ts_value = source.get(
                        self.normalization_service.original_timestamp_field_name
                    )
                    if original_ts_value is None:
                        continue

                    # Check if already ISO8601 UTC before full normalization attempt
                    if isinstance(
                        original_ts_value, str
                    ) and self.normalization_service.is_already_iso8601_utc(
                        original_ts_value
                    ):
                        # If it is, and target field is different or not present, update
                        if (
                            self.normalization_service.target_timestamp_field_name
                            != self.normalization_service.original_timestamp_field_name
                            or self.normalization_service.target_timestamp_field_name
                            not in source
                            or source.get(
                                self.normalization_service.target_timestamp_field_name
                            )
                            != original_ts_value
                        ):
                            update_actions.append(
                                {
                                    "_op_type": "update",
                                    "_index": parsed_log_index,
                                    "_id": doc_id,
                                    "doc": {
                                        self.normalization_service.target_timestamp_field_name: original_ts_value
                                    },
                                }
                            )
                        # else: field is same, value is same, no update needed
                        continue  # Skip full normalization

                    normalized_iso_ts = (
                        self.normalization_service.normalize_timestamp_value(
                            original_ts_value
                        )
                    )
                    if normalized_iso_ts:
                        # Only update if the normalized value is different from existing @timestamp or @timestamp doesn't exist
                        if (
                            self.normalization_service.target_timestamp_field_name
                            not in source
                            or source.get(
                                self.normalization_service.target_timestamp_field_name
                            )
                            != normalized_iso_ts
                        ):
                            update_actions.append(
                                {
                                    "_op_type": "update",
                                    "_index": parsed_log_index,
                                    "_id": doc_id,
                                    "doc": {
                                        self.normalization_service.target_timestamp_field_name: normalized_iso_ts
                                    },
                                }
                            )
                    else:
                        norm_errors_this_group += 1

            elif action == "remove_field":
                for hit in hits_batch:
                    doc_id = hit.get("_id")
                    if not doc_id:
                        continue
                    # Only add action if the field actually exists in the source to avoid unnecessary updates
                    if (
                        self.normalization_service.target_timestamp_field_name
                        in hit.get("_source", {})
                    ):
                        update_actions.append(
                            {
                                "_op_type": "update",
                                "_index": parsed_log_index,
                                "_id": doc_id,
                                "script": {
                                    "source": f"ctx._source.remove('{self.normalization_service.target_timestamp_field_name}')",
                                    "lang": "painless",
                                },
                            }
                        )

            if update_actions:
                success_count, _ = self.es_service.bulk_update_documents(update_actions)
                docs_updated_this_group += success_count

            return True

        query_body: Dict[str, Any]
        source_fields_needed: Optional[List[str]] = None

        if action == "normalize":
            # We need to fetch docs even if @timestamp exists to check if original `timestamp` field needs re-normalization
            # or if `timestamp` is already ISO and just needs copying.
            query_body = {
                "query": {
                    "exists": {
                        "field": self.normalization_service.original_timestamp_field_name
                    }
                }
            }
            # Fetch both original and target to compare if already ISO
            source_fields_needed = [
                self.normalization_service.original_timestamp_field_name,
                self.normalization_service.target_timestamp_field_name,  # Fetch target to see if update is needed
            ]
        elif action == "remove_field":
            query_body = {
                "query": {
                    "exists": {
                        "field": self.normalization_service.target_timestamp_field_name
                    }
                }
            }
            source_fields_needed = [
                "_id",
                self.normalization_service.target_timestamp_field_name,
            ]  # Fetch target to confirm removal
        else:
            current_group_data["status_this_run"] = "failed_unknown_action"
            current_group_data["error_message_this_run"] = f"Unknown action: {action}"
            self._logger.error(f"Group '{group_name}': Unknown action '{action}'.")
            updated_overall_results = state.get("overall_group_results", {}).copy()
            updated_overall_results[group_name] = current_group_data
            return {"overall_group_results": updated_overall_results}

        # docs_scanned_this_group will be the count of docs matching the query (e.g., having 'timestamp' field)
        # and considered by the callback up to the limit.
        _, docs_scanned_this_group = self.es_service.scroll_and_process_documents(
            index_name=parsed_log_index,
            query_body=query_body,
            batch_size=batch_size,
            process_batch_callback=batch_callback,
            source_fields=source_fields_needed,
            limit=limit,
        )

        current_group_data["documents_scanned_this_run"] = docs_scanned_this_group
        current_group_data["documents_updated_this_run"] = docs_updated_this_group
        if action == "normalize":
            current_group_data["timestamp_normalization_errors_this_run"] = (
                norm_errors_this_group
            )
        current_group_data["status_this_run"] = "completed"

        self._logger.info(
            f"Group '{group_name}': Action '{action}' completed. "
            f"Scanned (matching query): {docs_scanned_this_group}, Docs Updated: {docs_updated_this_group}"
            f"{f', Norm Errors: {norm_errors_this_group}' if action == 'normalize' else ''}."
        )

        updated_overall_results = state.get("overall_group_results", {}).copy()
        updated_overall_results[group_name] = current_group_data
        return {"overall_group_results": updated_overall_results}

    def _orchestrator_advance_group_node(
        self, state: TimestampNormalizerOrchestratorState
    ) -> Dict[str, Any]:
        new_index = state["current_group_processing_index"] + 1
        if new_index < len(state["groups_to_process_resolved"]):
            self._logger.debug(
                f"Orchestrator: Advancing to next group index {new_index}."
            )
            return {"current_group_processing_index": new_index}
        else:
            self._logger.info("Orchestrator: All targeted groups have been processed.")
            return {
                "current_group_processing_index": new_index,
                "orchestrator_status": "completed",
            }

    # --- Conditional Edge Functions ---

    def _orchestrator_should_continue_processing_groups(
        self, state: TimestampNormalizerOrchestratorState
    ) -> str:
        if state["orchestrator_status"] == "completed_no_groups":
            return END
        current_idx = state["current_group_processing_index"]
        if current_idx < len(state["groups_to_process_resolved"]):
            return "initialize_group"
        else:
            return END

    def _check_group_initialization_status(
        self, state: TimestampNormalizerOrchestratorState
    ) -> str:
        idx = state["current_group_processing_index"]
        group_name = state["groups_to_process_resolved"][idx]
        group_data = state["overall_group_results"].get(group_name)

        if not group_data or group_data["status_this_run"] == "failed_index_not_found":
            self._logger.warning(
                f"Orchestrator: Group '{group_name}' either not initialized or index not found. Skipping actual processing."
            )
            return "advance_group"
        return "process_group_action"

    def _build_graph(self) -> CompiledGraph:
        graph_builder = StateGraph(TimestampNormalizerOrchestratorState)

        graph_builder.add_node("start_orchestration", self._orchestrator_start_node)
        graph_builder.add_node(
            "initialize_group", self._orchestrator_initialize_group_node
        )
        graph_builder.add_node("process_group_action", self._process_group_node)
        graph_builder.add_node("advance_group", self._orchestrator_advance_group_node)

        graph_builder.set_entry_point("start_orchestration")

        graph_builder.add_conditional_edges(
            "start_orchestration",
            self._orchestrator_should_continue_processing_groups,
            {"initialize_group": "initialize_group", END: END},
        )
        graph_builder.add_conditional_edges(
            "initialize_group",
            self._check_group_initialization_status,
            {
                "process_group_action": "process_group_action",
                "advance_group": "advance_group",
            },
        )
        graph_builder.add_edge("process_group_action", "advance_group")
        graph_builder.add_conditional_edges(
            "advance_group",
            self._orchestrator_should_continue_processing_groups,
            {"initialize_group": "initialize_group", END: END},
        )
        return graph_builder.compile()

    def run(
        self,
        action: str,
        target_groups: Optional[List[str]] = None,
        limit_per_group: Optional[int] = None,
        batch_size: int = DEFAULT_BATCH_SIZE_NORMALIZER,  # Use defined default
    ) -> TimestampNormalizerOrchestratorState:

        if action not in ["normalize", "remove_field"]:
            self._logger.error(
                f"Invalid action specified for TimestampNormalizerAgent: {action}"
            )
            return TimestampNormalizerOrchestratorState(
                action_to_perform=action,
                target_group_names=target_groups,
                limit_per_group=limit_per_group,
                batch_size=batch_size,
                all_group_names_from_db=[],
                groups_to_process_resolved=[],
                current_group_processing_index=0,
                overall_group_results={},
                orchestrator_status="failed_invalid_action",
                orchestrator_error_messages=[f"Invalid action: {action}"],
            )  # type: ignore

        self._logger.info(
            f"TimestampNormalizerAgent: Initiating run for action '{action}'. Target groups: {target_groups or 'ALL'}."
        )
        initial_state: TimestampNormalizerOrchestratorState = {
            "action_to_perform": action,
            "target_group_names": target_groups,
            "limit_per_group": limit_per_group,
            "batch_size": batch_size,
            "all_group_names_from_db": [],
            "groups_to_process_resolved": [],
            "current_group_processing_index": 0,
            "overall_group_results": {},
            "orchestrator_status": "pending",
            "orchestrator_error_messages": [],
        }  # type: ignore

        final_state: TimestampNormalizerOrchestratorState = self.graph.invoke(initial_state)  # type: ignore

        self._logger.info(
            f"TimestampNormalizerAgent: Run finished. Final orchestrator status: {final_state.get('orchestrator_status')}"
        )
        for group_name, group_data in final_state.get(
            "overall_group_results", {}
        ).items():
            norm_errors_str = (
                f", NormErrors={group_data.get('timestamp_normalization_errors_this_run',0)}"
                if action == "normalize"
                else ""
            )
            self._logger.info(
                f"  Group '{group_name}': Status='{group_data.get('status_this_run', 'N/A')}', "
                f"Scanned={group_data.get('documents_scanned_this_run', 0)}, "
                f"Updated={group_data.get('documents_updated_this_run', 0)}"
                f"{norm_errors_str}"
            )
        return final_state
