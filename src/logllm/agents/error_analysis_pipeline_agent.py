# src/logllm/agents/error_analysis_pipeline_agent.py (NEW FILE)
from typing import Any, Dict, List, Optional

from elasticsearch.helpers import bulk
from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph

from ..config import config as cfg
from ..data_schemas.error_analysis import (
    ClusterResult,
    ErrorAnalysisPipelineState,
    ErrorSummarySchema,
    LogDocument,
)
from ..utils.database import ElasticsearchDatabase
from ..utils.llm_model import (  # For embeddings in clusterer, and generation in summarizer
    LLMModel,
)
from ..utils.logger import Logger
from ..utils.prompts_manager import PromptsManager
from .error_clusterer_agent import ErrorClustererAgent
from .error_summarizer_agent import ErrorSummarizerAgent


class ErrorAnalysisPipelineAgent:
    def __init__(
        self,
        db: ElasticsearchDatabase,
        llm_model: LLMModel,
        prompts_manager: PromptsManager,
    ):
        self.db = db
        self.llm_model = llm_model
        self.prompts_manager = prompts_manager
        self.logger = Logger()

        self.clusterer = ErrorClustererAgent(embedding_model=llm_model)
        self.summarizer = ErrorSummarizerAgent(
            llm_model=llm_model, prompts_manager=prompts_manager
        )

        self.graph: CompiledGraph = self._build_graph()  # type hint for self.graph

    # --- Graph Node Implementations ---
    def _fetch_initial_errors_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        group_name = state["group_name"]
        es_query_for_errors = state["es_query_for_errors"]
        status_msgs = state.get("status_messages", [])

        self.logger.info(f"[{group_name}] Fetching initial error logs using query.")

        source_index_for_errors = cfg.get_normalized_parsed_log_storage_index(
            group_name
        )
        working_index_name = cfg.get_error_analysis_working_index(group_name)

        self.logger.info(
            f"[{group_name}] Original source: '{source_index_for_errors}', Temp working index: '{working_index_name}'"
        )
        status_msgs.append(f"Using temp working index: {working_index_name}")

        error_docs: List[LogDocument] = []

        try:
            # 1. Delete the working index if it exists
            if self.db.instance.indices.exists(index=working_index_name):
                self.logger.info(
                    f"[{group_name}] Deleting existing working index: {working_index_name}"
                )
                self.db.instance.indices.delete(
                    index=working_index_name, ignore_unavailable=True
                )
                status_msgs.append(f"Deleted old working index {working_index_name}.")

            # 2. Create the working index (dynamic mapping should be fine for temp use)
            # self.db.instance.indices.create(index=working_index_name, ignore=400) # 400 if already exists (race condition)
            # logger.info(f"[{group_name}] Created new working index: {working_index_name}")
            # No explicit create needed if we're just going to bulk index; ES will create it.

            # 3. Fetch error logs from the original source index
            self.logger.info(
                f"[{group_name}] Querying original source '{source_index_for_errors}' for errors."
            )

            # Ensure the query body for fetching includes _source
            if "_source" not in es_query_for_errors:
                es_query_for_errors["_source"] = (
                    True  # Fetch all source fields by default if not specified
                )

            all_hits_from_source = self.db.scroll_search(
                index=source_index_for_errors,
                query=es_query_for_errors,  # This query already contains size and _source
            )
            self.logger.info(
                f"[{group_name}] Fetched {len(all_hits_from_source)} raw documents from '{source_index_for_errors}'."
            )

            if not all_hits_from_source:
                status_msgs.append(
                    f"Fetched 0 error logs from {source_index_for_errors}."
                )
                return {"error_log_docs": [], "status_messages": status_msgs}

            # 4. Bulk index these fetched logs into the working index
            actions_to_bulk = []
            for hit in all_hits_from_source:
                if (
                    "_source" in hit and "_id" in hit
                ):  # Ensure document has source and id
                    actions_to_bulk.append(
                        {
                            "_index": working_index_name,
                            "_id": hit["_id"],
                            "_source": hit["_source"],
                        }
                    )
                    # Also prepare the in-memory list for subsequent pipeline steps
                    error_docs.append({"_id": hit["_id"], "_source": hit["_source"]})

            if actions_to_bulk:
                self.logger.info(
                    f"[{group_name}] Bulk indexing {len(actions_to_bulk)} documents into '{working_index_name}'."
                )
                success_count, errors = self.db.bulk_operation(
                    actions=actions_to_bulk
                )  # Use the robust bulk_operation
                if errors:
                    self.logger.error(
                        f"[{group_name}] Errors during bulk indexing to working index: {errors[:3]}"
                    )
                    status_msgs.append(
                        f"ERROR: {len(errors)} errors bulk indexing to {working_index_name}."
                    )
                else:
                    self.logger.info(
                        f"[{group_name}] Successfully indexed {success_count} documents to '{working_index_name}'."
                    )
                    status_msgs.append(
                        f"Stored {success_count} fetched errors into {working_index_name}."
                    )
            else:
                self.logger.info(
                    f"[{group_name}] No valid documents to bulk index into working index."
                )

            status_msgs.append(f"Fetched {len(error_docs)} error logs for processing.")
            return {"error_log_docs": error_docs, "status_messages": status_msgs}

        except Exception as e:
            self.logger.error(
                f"[{group_name}] Failed during fetch/store to working index: {e}",
                exc_info=True,
            )
            status_msgs.append(f"ERROR: Failed fetch/store to working index: {e}")
            return {"error_log_docs": [], "status_messages": status_msgs}

    def _cluster_errors_node(self, state: ErrorAnalysisPipelineState) -> Dict[str, Any]:
        self.logger.info("Clustering error logs...")
        status_msgs = state.get("status_messages", [])
        if not state["error_log_docs"]:
            self.logger.warning("No error logs to cluster.")
            return {
                "clusters": [],
                "current_cluster_index": 0,
                "status_messages": status_msgs + ["No logs to cluster."],
            }

        clustering_params = state.get("clustering_params", {})
        clusters = self.clusterer.run(
            state["error_log_docs"],
            eps=clustering_params.get("eps", cfg.DEFAULT_DBSCAN_EPS),
            min_samples=clustering_params.get(
                "min_samples", cfg.DEFAULT_DBSCAN_MIN_SAMPLES
            ),
        )
        self.logger.info(f"Clustering resulted in {len(clusters)} clusters.")
        return {
            "clusters": clusters,
            "current_cluster_index": 0,  # Initialize index for the loop
            "status_messages": status_msgs + [f"Found {len(clusters)} clusters."],
        }

    def _sample_and_summarize_cluster_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        current_idx = state["current_cluster_index"]  # Index of the cluster to process
        cluster = state["clusters"][current_idx]
        group_name = state["group_name"]
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_per_cluster", cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY
        )

        self.logger.info(
            f"Processing cluster ID {cluster['cluster_id']} (loop index: {current_idx}, count: {cluster['count']}) for group {group_name}"
        )

        samples_for_summary = cluster["example_log_docs"][:max_samples]

        cluster_context_for_summarizer = {
            "representative_message": cluster["representative_message"],
            "count": cluster["count"],
            "first_occurrence_ts": cluster["first_occurrence_ts"],
            "last_occurrence_ts": cluster["last_occurrence_ts"],
        }

        summary = self.summarizer.run(
            group_name, samples_for_summary, cluster_context_for_summarizer
        )

        new_summaries = state.get("generated_summaries", [])
        status_msgs = state.get("status_messages", [])
        if summary:
            new_summaries.append(summary)
            status_msgs.append(
                f"Generated summary for cluster ID {cluster['cluster_id']}."
            )
            self.logger.info(
                f"Summary generated for cluster ID {cluster['cluster_id']}."
            )
        else:
            status_msgs.append(
                f"Failed to generate summary for cluster ID {cluster['cluster_id']}."
            )
            self.logger.warning(
                f"Failed to summarize cluster ID {cluster['cluster_id']}."
            )

        return {
            "generated_summaries": new_summaries,
            "status_messages": status_msgs,
            "current_cluster_index": current_idx
            + 1,  # Return the *next* index to be considered
        }

    def _sample_and_summarize_unclustered_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        self.logger.info("Processing unclustered errors (or fallback from clustering).")
        group_name = state["group_name"]
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_unclustered", cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY
        )
        status_msgs = state.get("status_messages", [])

        if not state["error_log_docs"]:
            return {
                "status_messages": status_msgs + ["No unclustered logs to summarize."]
            }

        import random

        samples_for_summary = random.sample(
            state["error_log_docs"], min(len(state["error_log_docs"]), max_samples)
        )

        summary = self.summarizer.run(
            group_name, samples_for_summary, cluster_context=None
        )

        new_summaries = state.get("generated_summaries", [])
        if summary:
            new_summaries.append(summary)
            status_msgs.append("Generated summary for unclustered/fallback batch.")
            self.logger.info("Summary generated for unclustered/fallback batch.")
        else:
            status_msgs.append(
                "Failed to generate summary for unclustered/fallback batch."
            )
            self.logger.warning("Failed to summarize unclustered/fallback batch.")

        return {"generated_summaries": new_summaries, "status_messages": status_msgs}

    def _store_summaries_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        generated_summaries = state.get("generated_summaries", [])
        status_msgs = state.get("status_messages", [])
        self.logger.info(f"Storing {len(generated_summaries)} summaries.")
        stored_count = 0
        for summary_obj in generated_summaries:
            try:
                self.db.insert(
                    summary_obj.model_dump(), index=cfg.INDEX_ERROR_SUMMARIES
                )
                stored_count += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to store summary: {getattr(summary_obj, 'error_category', 'N/A')} - {e}",
                    exc_info=True,
                )
                status_msgs.append(f"ERROR storing summary: {e}")

        return {"status_messages": status_msgs + [f"Stored {stored_count} summaries."]}

    # --- Conditional Edges ---
    def _decide_clustering_outcome(self, state: ErrorAnalysisPipelineState) -> str:
        clusters = state.get("clusters")
        status_msgs = state.get("status_messages", [])

        if clusters and len(clusters) > 0:
            if all(
                c["cluster_id"] == -1 for c in clusters if c
            ):  # Check if all are noise
                self.logger.warning(
                    "Clustering resulted only in noise. Falling back to unclustered summarization."
                )
                status_msgs.append(
                    "Clustering resulted only in noise, using fallback summarization."
                )
                return "summarize_unclustered_fallback"
            self.logger.info(f"Proceeding with {len(clusters)} clusters.")
            status_msgs.append(
                f"Clustering successful, proceeding to summarize {len(clusters)} clusters."
            )
            # State update current_cluster_index is already done by _cluster_errors_node
            return "check_cluster_loop_condition"  # Go to the loop condition checker
        else:
            self.logger.warning(
                "No clusters found or clustering failed. Falling back to unclustered summarization."
            )
            status_msgs.append("No valid clusters found, using fallback summarization.")
            return "summarize_unclustered_fallback"

    def _check_cluster_loop_condition_node(
        self, state: ErrorAnalysisPipelineState
    ) -> str:
        """Condition to decide if there are more clusters to process."""
        current_idx = state.get("current_cluster_index", 0)
        clusters = state.get("clusters", [])
        if current_idx < len(clusters):
            self.logger.debug(
                f"Loop condition: YES, process cluster at index {current_idx}"
            )
            return "process_this_cluster"
        else:
            self.logger.debug(
                f"Loop condition: NO, all {len(clusters)} clusters processed."
            )
            return "finish_cluster_processing"

    # --- Build Graph ---
    def _build_graph(self) -> CompiledGraph:
        workflow = StateGraph(ErrorAnalysisPipelineState)

        workflow.add_node("fetch_initial_errors", self._fetch_initial_errors_node)
        workflow.add_node("cluster_errors", self._cluster_errors_node)

        # This node acts as the entry point and decision point for the cluster processing loop
        workflow.add_node(
            "check_cluster_loop_condition", lambda state: {}
        )  # Simple pass-through node for the condition

        workflow.add_node(
            "sample_and_summarize_cluster", self._sample_and_summarize_cluster_node
        )
        workflow.add_node(
            "summarize_unclustered_fallback_node",
            self._sample_and_summarize_unclustered_node,
        )
        workflow.add_node("store_summaries", self._store_summaries_node)

        # Define Edges
        workflow.set_entry_point("fetch_initial_errors")
        workflow.add_edge("fetch_initial_errors", "cluster_errors")

        workflow.add_conditional_edges(
            "cluster_errors",
            self._decide_clustering_outcome,
            {
                "check_cluster_loop_condition": "check_cluster_loop_condition",
                "summarize_unclustered_fallback": "summarize_unclustered_fallback_node",
            },
        )

        # Cluster processing loop logic
        workflow.add_conditional_edges(
            "check_cluster_loop_condition",
            self._check_cluster_loop_condition_node,
            {
                "process_this_cluster": "sample_and_summarize_cluster",
                "finish_cluster_processing": "store_summaries",
            },
        )

        # After processing a cluster, its state (with incremented current_cluster_index)
        # flows back to check_cluster_loop_condition.
        workflow.add_edge(
            "sample_and_summarize_cluster", "check_cluster_loop_condition"
        )

        # Edge from fallback to storage
        workflow.add_edge("summarize_unclustered_fallback_node", "store_summaries")
        workflow.add_edge("store_summaries", END)

        return workflow.compile()

    def run(self, initial_state_input: Dict[str, Any]) -> ErrorAnalysisPipelineState:
        self.logger.info(
            f"Starting Error Analysis Pipeline for group: {initial_state_input['group_name']}"
        )

        # Ensure the input conforms to ErrorAnalysisPipelineState, providing defaults for optional fields
        # This helps if the caller provides a simpler dict.
        # LangGraph expects the input to `invoke` to match the State TypedDict.

        # Initialize with all keys expected by ErrorAnalysisPipelineState, using provided values or defaults
        graph_input_state: ErrorAnalysisPipelineState = {
            "group_name": initial_state_input["group_name"],
            "es_query_for_errors": initial_state_input["es_query_for_errors"],
            "clustering_params": initial_state_input.get("clustering_params", {}),
            "sampling_params": initial_state_input.get("sampling_params", {}),
            "error_log_docs": initial_state_input.get(
                "error_log_docs", []
            ),  # Initial fetch will populate
            "clusters": initial_state_input.get("clusters"),  # Will be None initially
            "current_cluster_index": initial_state_input.get(
                "current_cluster_index", 0
            ),
            "current_samples_for_summary": initial_state_input.get(
                "current_samples_for_summary", []
            ),
            "generated_summaries": initial_state_input.get("generated_summaries", []),
            "status_messages": initial_state_input.get("status_messages", []),
        }

        final_state = self.graph.invoke(graph_input_state)
        self.logger.info(
            f"Error Analysis Pipeline finished. Status messages: {final_state.get('status_messages')}"
        )
        return final_state
