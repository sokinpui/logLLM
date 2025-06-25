# src/logllm/agents/error_summarizer/__init__.py
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph

from ...config import config as cfg
from ...utils.database import ElasticsearchDatabase
from ...utils.llm.gemini_model import GeminiModel, LLMModel
from ...utils.local_embedder import LocalSentenceTransformerEmbedder
from ...utils.logger import Logger
from .api import (
    ErrorSummarizerESDataService,
    LLMService,
    LogClusteringService,
    LogSamplingService,
)
from .states import ErrorSummarizerAgentState, LogClusterSummaryOutput


class ErrorSummarizerAgent:
    def __init__(
        self,
        db: ElasticsearchDatabase,
        llm_model_instance: Optional[LLMModel] = None,
    ):
        self._logger = Logger()
        self.db = db

        self.es_service = ErrorSummarizerESDataService(db, logger=self._logger)
        self.clustering_service = LogClusteringService(logger=self._logger)
        self.sampling_service = LogSamplingService(logger=self._logger)

        self.default_llm_model_name = cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION
        self._llm_model_instance = llm_model_instance

        self.llm_service: Optional[LLMService] = None
        self._local_embedder_cache: Dict[str, LocalSentenceTransformerEmbedder] = (
            {}
        )  # Cache for local embedders

        self.graph: CompiledGraph = self._build_graph()
        self._logger.info("ErrorSummarizerAgent initialized.")

    def _get_llm_service(self, model_name_override: Optional[str] = None) -> LLMService:
        # ... (this method remains the same)
        target_model_name = model_name_override or self.default_llm_model_name

        if self.llm_service and hasattr(self.llm_service.llm_model, "model_name") and self.llm_service.llm_model.model_name == target_model_name:  # type: ignore
            return self.llm_service

        if model_name_override:
            current_llm_instance = GeminiModel(model_name=model_name_override)
            self._logger.info(
                f"LLMService: Using overridden model '{model_name_override}'."
            )
        elif self._llm_model_instance:
            current_llm_instance = self._llm_model_instance
            target_model_name = getattr(
                current_llm_instance, "model_name", self.default_llm_model_name
            )
            self._logger.info(
                f"LLMService: Using pre-configured LLM instance for model '{target_model_name}'."
            )
        else:
            current_llm_instance = GeminiModel(model_name=self.default_llm_model_name)
            self._logger.info(
                f"LLMService: Using default model '{self.default_llm_model_name}'."
            )

        self.llm_service = LLMService(current_llm_instance, logger=self._logger)
        return self.llm_service

    # ... (_start_analysis_node, _fetch_error_logs_node remain the same) ...
    def _start_analysis_node(self, state: ErrorSummarizerAgentState) -> Dict[str, Any]:
        self._logger.info(
            f"Starting error summary analysis for group: {state['group_name']} "
            f"from {state['start_time_iso']} to {state['end_time_iso']}."
        )
        state["agent_status"] = "initializing"
        state["error_messages"] = []
        state["final_summary_ids"] = []
        state["processed_cluster_details"] = []
        state["raw_error_logs"] = []
        state["error_log_messages"] = []
        state["error_log_timestamps"] = []
        state["log_embeddings"] = None
        state["cluster_assignments"] = None

        parsed_log_idx = cfg.get_parsed_log_storage_index(state["group_name"])
        state["parsed_log_index_name"] = parsed_log_idx

        if not self.db.instance or not self.db.instance.indices.exists(
            index=parsed_log_idx
        ):
            msg = f"Parsed log index '{parsed_log_idx}' for group '{state['group_name']}' does not exist."
            self._logger.error(msg)
            state["error_messages"].append(msg)
            state["agent_status"] = "failed_initialization_index_not_found"
            return {
                "agent_status": state["agent_status"],
                "error_messages": state["error_messages"],
                "parsed_log_index_name": parsed_log_idx,
            }

        required_fields = {
            "loglevel": "loglevel",
            "@timestamp": "@timestamp",
            "message": "message",
        }
        missing_mapping_fields = []
        for field_key, field_name in required_fields.items():
            if not self.es_service.check_field_exists_in_mapping(
                parsed_log_idx, field_name
            ):
                missing_mapping_fields.append(field_name)

        if missing_mapping_fields:
            msg = f"Required fields {missing_mapping_fields} not found in mapping for index '{parsed_log_idx}'. Cannot perform error analysis."
            self._logger.error(msg)
            state["error_messages"].append(msg)
            state["agent_status"] = "failed_initialization_missing_fields"
            return {
                "agent_status": state["agent_status"],
                "error_messages": state["error_messages"],
                "parsed_log_index_name": parsed_log_idx,
            }

        state["agent_status"] = "fetching_logs"
        return {
            "agent_status": state["agent_status"],
            "parsed_log_index_name": parsed_log_idx,
            "error_messages": state["error_messages"],
        }

    def _fetch_error_logs_node(
        self, state: ErrorSummarizerAgentState
    ) -> Dict[str, Any]:
        self._logger.info(f"Fetching error logs for group '{state['group_name']}'.")
        raw_logs = self.es_service.fetch_error_logs_in_time_window(
            index_name=state["parsed_log_index_name"],
            start_time_iso=state["start_time_iso"],
            end_time_iso=state["end_time_iso"],
            error_levels=state["error_log_levels"],
            timestamp_field="@timestamp",
            loglevel_field="loglevel",
            content_field="message",
            max_logs=state["max_logs_to_process"],
        )

        if not raw_logs:
            self._logger.info(
                f"No error logs found for group '{state['group_name']}' matching criteria."
            )
            state["agent_status"] = "completed_no_logs"
            return {
                "raw_error_logs": [],
                "error_log_messages": [],
                "error_log_timestamps": [],
                "agent_status": state["agent_status"],
            }

        state["raw_error_logs"] = raw_logs
        state["error_log_messages"] = [log.get("message", "") or "" for log in raw_logs]
        state["error_log_timestamps"] = [
            log.get("@timestamp", "") or "" for log in raw_logs
        ]
        state["agent_status"] = "embedding_logs"
        self._logger.info(
            f"Fetched {len(raw_logs)} error logs. Proceeding to embedding."
        )
        return {
            "raw_error_logs": raw_logs,
            "error_log_messages": state["error_log_messages"],
            "error_log_timestamps": state["error_log_timestamps"],
            "agent_status": state["agent_status"],
        }

    def _embed_logs_node(self, state: ErrorSummarizerAgentState) -> Dict[str, Any]:
        log_messages_to_embed = state.get("error_log_messages")
        if not log_messages_to_embed:
            self._logger.info("No log messages to embed.")
            state["agent_status"] = "clustering_logs"
            return {"log_embeddings": [], "agent_status": state["agent_status"]}

        embedding_model_name = state["embedding_model_name"]
        self._logger.info(
            f"Generating embeddings for {len(log_messages_to_embed)} log messages using '{embedding_model_name}'."
        )

        embeddings: Optional[List[List[float]]] = None
        try:
            # Decide whether to use local or API-based embedder
            if embedding_model_name.startswith("models/") or embedding_model_name in [
                "text-embedding-004",
                "embedding-001",
            ]:  # Heuristic for Google API models
                self._logger.debug(
                    f"Using GeminiModel API for embeddings with model: {embedding_model_name}"
                )
                llm_service_for_api_embeddings = self._get_llm_service(
                    state["llm_model_for_summary"]
                )  # Needs an LLM service instance
                embeddings = (
                    llm_service_for_api_embeddings.llm_model.generate_embeddings(
                        contents=log_messages_to_embed,
                        embedding_model_name=embedding_model_name,
                        task_type="CLUSTERING",
                    )
                )
            else:  # Assume it's a local Sentence Transformer model
                self._logger.debug(
                    f"Using LocalSentenceTransformerEmbedder for model: {embedding_model_name}"
                )
                if embedding_model_name not in self._local_embedder_cache:
                    self._local_embedder_cache[embedding_model_name] = (
                        LocalSentenceTransformerEmbedder(
                            model_name_or_path=embedding_model_name, logger=self._logger
                        )
                    )
                local_embedder = self._local_embedder_cache[embedding_model_name]
                # Batching is handled well by sentence-transformers, default batch_size in embedder is 32
                # You can make this configurable if needed.
                embeddings = local_embedder.generate_embeddings(
                    contents=log_messages_to_embed,
                    batch_size=128,
                    show_progress_bar=True,
                )

            if embeddings is None:  # Should not happen if exceptions are caught
                raise ValueError("Embedding generation returned None unexpectedly.")

            original_indices_for_valid_embeddings = []
            filtered_log_embeddings = []
            for i, emb in enumerate(embeddings):
                if (
                    emb and isinstance(emb, list) and len(emb) > 0
                ):  # Check if the embedding list is not empty and valid
                    filtered_log_embeddings.append(emb)
                    original_indices_for_valid_embeddings.append(i)
                else:
                    self._logger.warning(
                        f"Log message at index {i} ('{log_messages_to_embed[i][:50]}...') resulted in an empty or invalid embedding. It will be excluded."
                    )

            if not filtered_log_embeddings:
                self._logger.warning(
                    "No valid embeddings were generated for any log messages. Skipping clustering."
                )
                state["log_embeddings"] = []
                state["cluster_assignments"] = []  # Ensure this is set
                state["agent_status"] = "summarizing_logs"
                # Update raw_error_logs etc. to be empty as well if no valid embeddings
                state["raw_error_logs"] = []
                state["error_log_messages"] = []
                state["error_log_timestamps"] = []
                return {
                    "log_embeddings": [],
                    "cluster_assignments": [],
                    "agent_status": state["agent_status"],
                    "raw_error_logs": [],
                    "error_log_messages": [],
                    "error_log_timestamps": [],
                }

            state["log_embeddings"] = filtered_log_embeddings

            # Re-align raw_error_logs, error_log_messages, error_log_timestamps to only include those that were successfully embedded
            state["raw_error_logs"] = [
                state["raw_error_logs"][i]
                for i in original_indices_for_valid_embeddings
            ]
            state["error_log_messages"] = [
                log_messages_to_embed[i] for i in original_indices_for_valid_embeddings
            ]
            state["error_log_timestamps"] = [
                state["error_log_timestamps"][i]
                for i in original_indices_for_valid_embeddings
            ]

            state["agent_status"] = "clustering_logs"
            self._logger.info(
                f"Successfully generated and filtered {len(state['log_embeddings'])} valid embeddings."
            )

        except Exception as e:
            self._logger.error(
                f"Error during log embedding with model '{embedding_model_name}': {e}",
                exc_info=True,
            )
            state["error_messages"].append(
                f"Embedding failed for model {embedding_model_name}: {e}"
            )
            state["agent_status"] = "failed_embedding"
            state["log_embeddings"] = []  # Ensure it's an empty list on failure
            state["raw_error_logs"] = []
            state["error_log_messages"] = []
            state["error_log_timestamps"] = []

        return {
            "log_embeddings": state.get("log_embeddings"),
            "agent_status": state["agent_status"],
            "error_messages": state["error_messages"],
            "raw_error_logs": state["raw_error_logs"],
            "error_log_messages": state["error_log_messages"],
            "error_log_timestamps": state["error_log_timestamps"],
        }

    def _cluster_logs_node(self, state: ErrorSummarizerAgentState) -> Dict[str, Any]:
        log_embeddings = state.get("log_embeddings")
        if (
            not log_embeddings
            or not isinstance(log_embeddings, list)
            or not all(isinstance(e, list) for e in log_embeddings)
        ):
            self._logger.info(
                "No valid embeddings available for clustering or embeddings are not in expected format."
            )
            state["agent_status"] = "summarizing_logs"
            return {"cluster_assignments": [], "agent_status": state["agent_status"]}

        self._logger.info(f"Clustering {len(log_embeddings)} log embeddings.")
        cluster_params = state["clustering_params"]
        cluster_labels = self.clustering_service.cluster_logs_dbscan(
            log_embeddings=log_embeddings,
            eps=cluster_params.get("eps", cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY),
            min_samples=cluster_params.get(
                "min_samples", cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY
            ),
        )
        state["cluster_assignments"] = cluster_labels
        state["agent_status"] = "summarizing_logs"
        if cluster_labels:
            self._logger.info(
                f"Clustering complete. Assignments overview: {Counter(cluster_labels).most_common()}"
            )
        else:
            self._logger.info(
                "Clustering complete, but no cluster labels generated (possibly due to no input embeddings)."
            )

        return {
            "cluster_assignments": cluster_labels,
            "agent_status": state["agent_status"],
        }

    def _summarize_and_store_node(
        self, state: ErrorSummarizerAgentState
    ) -> Dict[str, Any]:
        self._logger.info("Starting summarization and storage process.")
        cluster_assignments = state.get("cluster_assignments")
        raw_logs = state.get("raw_error_logs", [])
        log_messages = state.get("error_log_messages", [])
        log_timestamps = state.get("error_log_timestamps", [])

        if not raw_logs:
            self._logger.info(
                "No logs available for summarization after embedding/filtering. Ending."
            )
            state["agent_status"] = "completed_no_logs_for_summary"
            return {
                "agent_status": state["agent_status"],
                "processed_cluster_details": [],
                "final_summary_ids": [],
            }

        if cluster_assignments is None or len(cluster_assignments) != len(raw_logs):
            self._logger.warning(
                f"Cluster assignments are missing or length mismatch (assignments: {len(cluster_assignments) if cluster_assignments else 'None'}, logs: {len(raw_logs)}). "
                "Attempting to summarize all logs as a single 'unclustered' group."
            )
            cluster_assignments = [-1] * len(raw_logs)

        unique_cluster_ids = sorted(list(set(cluster_assignments)))
        processed_clusters_output: List[Dict[str, Any]] = []

        content_field_for_sampling = "message"
        llm_service = self._get_llm_service(state["llm_model_for_summary"])

        for cluster_id_val in unique_cluster_ids:
            current_cluster_raw_logs: List[Dict[str, Any]] = []
            current_cluster_messages: List[str] = []
            current_cluster_timestamps: List[str] = []

            for i, log_cluster_id_assigned in enumerate(cluster_assignments):
                if log_cluster_id_assigned == cluster_id_val:
                    if (
                        i < len(raw_logs)
                        and i < len(log_messages)
                        and i < len(log_timestamps)
                    ):
                        current_cluster_raw_logs.append(raw_logs[i])
                        current_cluster_messages.append(log_messages[i])
                        current_cluster_timestamps.append(log_timestamps[i])
                    else:
                        self._logger.warning(
                            f"Index {i} out of bounds for log lists when processing cluster {cluster_id_val}. Skipping this log entry."
                        )

            if not current_cluster_raw_logs:
                self._logger.info(
                    f"No logs found for cluster ID {cluster_id_val} after filtering. Skipping."
                )
                continue

            cluster_label_for_user = (
                "unclustered" if cluster_id_val == -1 else f"cluster_{cluster_id_val}"
            )
            self._logger.info(
                f"Processing {cluster_label_for_user} with {len(current_cluster_raw_logs)} logs."
            )

            sampling_max = state["sampling_params"]["max_samples_per_cluster"]
            if cluster_id_val == -1:
                sampling_max = state["sampling_params"]["max_samples_unclustered"]

            cluster_data_for_llm = (
                self.sampling_service.get_cluster_metadata_and_samples(
                    logs_in_cluster=current_cluster_raw_logs,
                    log_messages_in_cluster=current_cluster_messages,
                    log_timestamps_in_cluster=current_cluster_timestamps,
                    max_samples=sampling_max,
                    content_field=content_field_for_sampling,
                )
            )

            if not cluster_data_for_llm.get("sampled_logs_content"):
                self._logger.warning(
                    f"No samples generated for {cluster_label_for_user}. Skipping summarization."
                )
                continue

            self._logger.info(
                f"Generating summary for {cluster_label_for_user} using {len(cluster_data_for_llm['sampled_logs_content'])} samples."
            )

            structured_summary: Optional[LogClusterSummaryOutput] = (
                llm_service.generate_structured_summary(
                    cluster_info=cluster_data_for_llm,
                    group_name=state["group_name"],
                )
            )

            cluster_detail_entry: Dict[str, Any] = {
                "cluster_id_internal": cluster_id_val,
                "cluster_label": cluster_label_for_user,
                "total_logs_in_cluster": cluster_data_for_llm.get("size", 0),
                "unique_messages_in_cluster": cluster_data_for_llm.get(
                    "unique_message_count", 0
                ),
                "cluster_time_range_start": cluster_data_for_llm.get(
                    "time_range_start"
                ),
                "cluster_time_range_end": cluster_data_for_llm.get("time_range_end"),
                "sampled_log_messages_used": cluster_data_for_llm.get(
                    "sampled_logs_content", []
                ),
                "summary_generated": False,
                "summary_document_id_es": None,
                "summary_output": None,
            }

            if structured_summary:
                summary_doc_to_store = {
                    "group_name": state["group_name"],
                    "analysis_start_time": state["start_time_iso"],
                    "analysis_end_time": state["end_time_iso"],
                    "log_level_filter": state["error_log_levels"],
                    "cluster_id": cluster_label_for_user,
                    "summary_text": structured_summary.summary,
                    "potential_cause_text": structured_summary.potential_cause,
                    "keywords": structured_summary.keywords,
                    "representative_log_line_text": structured_summary.representative_log_line,
                    "sample_log_count": len(
                        cluster_data_for_llm.get("sampled_logs_content", [])
                    ),
                    "total_logs_in_cluster": cluster_data_for_llm.get("size", 0),
                    "cluster_time_range_start": cluster_data_for_llm.get(
                        "time_range_start"
                    ),
                    "cluster_time_range_end": cluster_data_for_llm.get(
                        "time_range_end"
                    ),
                    "generation_timestamp": datetime.utcnow().isoformat() + "Z",
                    "llm_model_used": llm_service.llm_model.model_name,
                    "embedding_model_used": state["embedding_model_name"],
                }
                summary_es_id = self.es_service.store_error_summary(
                    summary_doc=summary_doc_to_store,
                    target_index=state["target_summary_index"],
                )
                if summary_es_id:
                    state["final_summary_ids"].append(summary_es_id)
                    cluster_detail_entry["summary_generated"] = True
                    cluster_detail_entry["summary_document_id_es"] = summary_es_id
                    cluster_detail_entry["summary_output"] = (
                        structured_summary.model_dump()
                    )
                else:
                    self._logger.error(
                        f"Failed to store summary for {cluster_label_for_user}."
                    )
                    state["error_messages"].append(
                        f"Storage failed for {cluster_label_for_user}"
                    )
            else:
                self._logger.warning(
                    f"LLM did not return a valid structured summary for {cluster_label_for_user}."
                )
                state["error_messages"].append(
                    f"LLM summary generation failed for {cluster_label_for_user}"
                )

            processed_clusters_output.append(cluster_detail_entry)

        state["processed_cluster_details"] = processed_clusters_output
        state["agent_status"] = "completed"
        if state.get("error_messages"):
            state["agent_status"] = "completed_with_errors"

        self._logger.info("Summarization and storage process finished.")
        return {
            "agent_status": state["agent_status"],
            "final_summary_ids": state["final_summary_ids"],
            "processed_cluster_details": state["processed_cluster_details"],
            "error_messages": state["error_messages"],
        }

    def _check_initialization_status(self, state: ErrorSummarizerAgentState) -> str:
        status = state.get("agent_status", "unknown")
        if status.startswith("failed_initialization"):
            self._logger.error(
                f"Initialization failed: {state.get('error_messages')}. Ending run."
            )
            return END
        self._logger.debug(
            f"Initialization check passed, status: {status}. Proceeding to fetch logs."
        )
        return "fetch_logs_node"

    def _check_fetch_status(self, state: ErrorSummarizerAgentState) -> str:
        status = state.get("agent_status", "unknown")
        if status == "completed_no_logs":
            self._logger.info("No logs fetched. Ending run.")
            return END
        if not state.get("raw_error_logs"):
            self._logger.warning(
                "No raw error logs after fetch node, but status not 'completed_no_logs'. This might indicate an issue. Ending."
            )
            state["agent_status"] = "failed_fetch_unexpected_empty"
            return END
        self._logger.debug(
            f"Fetch check passed, status: {status}. Proceeding to embed logs."
        )
        return "embed_logs_node"

    def _check_embedding_status(self, state: ErrorSummarizerAgentState) -> str:
        status = state.get("agent_status", "unknown")
        if status == "failed_embedding":
            self._logger.error(
                f"Embedding failed: {state.get('error_messages')}. Ending run."
            )
            return END

        log_embeddings = state.get("log_embeddings")
        if (
            not log_embeddings
            or not isinstance(log_embeddings, list)
            or not state.get("raw_error_logs")
        ):
            self._logger.info(
                "Embeddings are empty/invalid or no corresponding raw logs after embedding node. Cannot cluster. Ending run."
            )
            state["agent_status"] = "failed_embedding_no_valid_output"
            return END
        self._logger.debug(
            f"Embedding check passed, status: {status}. Proceeding to cluster logs."
        )
        return "cluster_logs_node"

    def _check_clustering_status(self, state: ErrorSummarizerAgentState) -> str:
        status = state.get("agent_status", "unknown")
        if status == "failed_clustering":
            self._logger.error(
                f"Clustering failed critically: {state.get('error_messages')}. Ending run."
            )
            return END
        self._logger.debug(
            f"Clustering check passed, status: {status}. Proceeding to summarize."
        )
        return "summarize_and_store_node"

    def _build_graph(self) -> CompiledGraph:
        graph_builder = StateGraph(ErrorSummarizerAgentState)

        graph_builder.add_node("start_node", self._start_analysis_node)
        graph_builder.add_node("fetch_logs_node", self._fetch_error_logs_node)
        graph_builder.add_node("embed_logs_node", self._embed_logs_node)
        graph_builder.add_node("cluster_logs_node", self._cluster_logs_node)
        graph_builder.add_node(
            "summarize_and_store_node", self._summarize_and_store_node
        )

        graph_builder.set_entry_point("start_node")

        graph_builder.add_conditional_edges(
            "start_node", self._check_initialization_status
        )
        graph_builder.add_conditional_edges("fetch_logs_node", self._check_fetch_status)
        graph_builder.add_conditional_edges(
            "embed_logs_node", self._check_embedding_status
        )
        graph_builder.add_conditional_edges(
            "cluster_logs_node", self._check_clustering_status
        )
        graph_builder.add_edge("summarize_and_store_node", END)

        return graph_builder.compile()

    def run(
        self,
        group_name: str,
        start_time_iso: str,
        end_time_iso: str,
        error_log_levels: Optional[List[str]] = None,
        max_logs_to_process: int = cfg.DEFAULT_MAX_LOGS_FOR_SUMMARY,
        embedding_model_name: str = cfg.DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY,  # Can be local or API
        llm_model_for_summary: str = cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION,
        clustering_params: Optional[Dict[str, Any]] = None,
        sampling_params: Optional[Dict[str, int]] = None,
        target_summary_index: str = cfg.INDEX_ERROR_SUMMARIES,
    ) -> ErrorSummarizerAgentState:

        final_error_log_levels = error_log_levels or list(cfg.DEFAULT_ERROR_LEVELS)

        initial_state_dict: Dict[str, Any] = {
            "group_name": group_name,
            "start_time_iso": start_time_iso,
            "end_time_iso": end_time_iso,
            "error_log_levels": final_error_log_levels,
            "max_logs_to_process": max_logs_to_process,
            "embedding_model_name": embedding_model_name,
            "llm_model_for_summary": llm_model_for_summary,
            "clustering_params": clustering_params
            or {
                "eps": cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY,
                "min_samples": cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY,
            },
            "sampling_params": sampling_params
            or {
                "max_samples_per_cluster": cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY,
                "max_samples_unclustered": cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY,
            },
            "target_summary_index": target_summary_index,
            "agent_status": "pending",
            "error_messages": [],
            "final_summary_ids": [],
            "processed_cluster_details": [],
            "raw_error_logs": [],
            "error_log_messages": [],
            "error_log_timestamps": [],
            "log_embeddings": None,
            "cluster_assignments": None,
            "parsed_log_index_name": "",
        }

        initial_state: ErrorSummarizerAgentState = initial_state_dict  # type: ignore

        self._logger.info(
            f"ErrorSummarizerAgent run initiated for group: {initial_state['group_name']}, "
            f"time window: {initial_state['start_time_iso']} to {initial_state['end_time_iso']}"
        )

        final_state = self.graph.invoke(initial_state)
        self._logger.info(
            f"ErrorSummarizerAgent run finished. Final status: {final_state.get('agent_status')}"
        )
        if final_state.get("error_messages"):
            self._logger.error(
                f"Agent run encountered errors: {final_state['error_messages']}"
            )
        return final_state
