# src/logllm/agents/error_analysis_pipeline_agent.py
from typing import Any, Dict, List, Optional

# from elasticsearch.helpers import bulk # Not directly used here anymore
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
from ..utils.llm_model import LLMModel
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

        self.graph: CompiledGraph = self._build_graph()

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
            if self.db.instance.indices.exists(index=working_index_name):
                self.logger.info(
                    f"[{group_name}] Deleting existing working index: {working_index_name}"
                )
                self.db.instance.indices.delete(
                    index=working_index_name, ignore_unavailable=True
                )
                status_msgs.append(f"Deleted old working index {working_index_name}.")

            if "_source" not in es_query_for_errors:
                es_query_for_errors["_source"] = True

            all_hits_from_source = self.db.scroll_search(
                index=source_index_for_errors,
                query=es_query_for_errors,
            )
            self.logger.info(
                f"[{group_name}] Fetched {len(all_hits_from_source)} raw documents from '{source_index_for_errors}'."
            )

            if not all_hits_from_source:
                status_msgs.append(
                    f"Fetched 0 error logs from {source_index_for_errors}."
                )
                return {
                    "error_log_docs": [],
                    "status_messages": status_msgs,
                    "clusters": None,
                }

            actions_to_bulk = []
            for hit in all_hits_from_source:
                if "_source" in hit and "_id" in hit:
                    actions_to_bulk.append(
                        {
                            "_index": working_index_name,
                            "_id": hit["_id"],
                            "_source": hit["_source"],
                        }
                    )
                    error_docs.append({"_id": hit["_id"], "_source": hit["_source"]})

            if actions_to_bulk:
                self.logger.info(
                    f"[{group_name}] Bulk indexing {len(actions_to_bulk)} documents into '{working_index_name}'."
                )
                success_count, errors = self.db.bulk_operation(actions=actions_to_bulk)
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
            return {
                "error_log_docs": error_docs,
                "status_messages": status_msgs,
                "clusters": None,
            }

        except Exception as e:
            self.logger.error(
                f"[{group_name}] Failed during fetch/store to working index: {e}",
                exc_info=True,
            )
            status_msgs.append(f"ERROR: Failed fetch/store to working index: {e}")
            return {
                "error_log_docs": [],
                "status_messages": status_msgs,
                "clusters": None,
            }

    def _cluster_errors_node(self, state: ErrorAnalysisPipelineState) -> Dict[str, Any]:
        self.logger.info(f"[{state['group_name']}] Clustering error logs...")
        status_msgs = state.get("status_messages", [])
        if not state["error_log_docs"]:
            self.logger.warning(f"[{state['group_name']}] No error logs to cluster.")
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
            max_docs_for_clustering=clustering_params.get(
                "max_docs_for_clustering", cfg.DEFAULT_MAX_DOCS_FOR_CLUSTERING
            ),
        )
        self.logger.info(
            f"[{state['group_name']}] Clustering resulted in {len(clusters)} clusters."
        )
        return {
            "clusters": clusters,
            "current_cluster_index": 0,
            "status_messages": status_msgs
            + [f"Found {len(clusters)} clusters (incl. noise if any)."],
        }

    def _sample_and_summarize_cluster_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        current_idx = state["current_cluster_index"]
        # We can be sure 'clusters' exists and is not None here due to graph flow
        cluster = state["clusters"][current_idx]  # type: ignore
        group_name = state["group_name"]
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_per_cluster", cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY
        )

        self.logger.info(
            f"[{group_name}] Processing cluster ID {cluster['cluster_id']} (loop index: {current_idx}, count: {cluster['count']})"
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
                f"[{group_name}] Summary generated for cluster ID {cluster['cluster_id']}."
            )
        else:
            status_msgs.append(
                f"Failed to generate summary for cluster ID {cluster['cluster_id']}."
            )
            self.logger.warning(
                f"[{group_name}] Failed to summarize cluster ID {cluster['cluster_id']}."
            )

        return {
            "generated_summaries": new_summaries,
            "status_messages": status_msgs,
            "current_cluster_index": current_idx + 1,
        }

    def _sample_and_summarize_unclustered_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        group_name = state["group_name"]
        self.logger.info(f"[{group_name}] Processing unclustered errors (or fallback).")
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_unclustered", cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY
        )
        status_msgs = state.get("status_messages", [])

        if not state["error_log_docs"]:
            self.logger.warning(f"[{group_name}] No unclustered logs to summarize.")
            return {
                "status_messages": status_msgs + ["No unclustered logs to summarize."]
            }

        import random

        docs_to_sample_from = state["error_log_docs"]
        samples_for_summary = random.sample(
            docs_to_sample_from, min(len(docs_to_sample_from), max_samples)
        )

        summary = self.summarizer.run(
            group_name, samples_for_summary, cluster_context=None
        )

        new_summaries = state.get("generated_summaries", [])
        if summary:
            new_summaries.append(summary)
            status_msgs.append("Generated summary for unclustered/fallback batch.")
            self.logger.info(
                f"[{group_name}] Summary generated for unclustered/fallback batch."
            )
        else:
            status_msgs.append(
                "Failed to generate summary for unclustered/fallback batch."
            )
            self.logger.warning(
                f"[{group_name}] Failed to summarize unclustered/fallback batch."
            )

        return {"generated_summaries": new_summaries, "status_messages": status_msgs}

    def _store_summaries_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        generated_summaries = state.get("generated_summaries", [])
        status_msgs = state.get("status_messages", [])
        group_name = state["group_name"]
        self.logger.info(
            f"[{group_name}] Storing {len(generated_summaries)} summaries."
        )
        stored_count = 0
        for summary_obj in generated_summaries:
            try:
                self.db.insert(
                    summary_obj.model_dump(), index=cfg.INDEX_ERROR_SUMMARIES
                )
                stored_count += 1
            except Exception as e:
                self.logger.error(
                    f"[{group_name}] Failed to store summary: {getattr(summary_obj, 'error_category', 'N/A')} - {e}",
                    exc_info=True,
                )
                status_msgs.append(f"ERROR storing summary: {e}")

        final_status_message = f"Stored {stored_count} summaries."
        if stored_count == 0 and len(generated_summaries) > 0:
            final_status_message = "Attempted to store summaries, but 0 were successfully stored (check logs)."
        elif stored_count == 0 and len(generated_summaries) == 0:
            final_status_message = "No summaries were generated to store."

        return {"status_messages": status_msgs + [final_status_message]}

    def _decide_clustering_outcome(self, state: ErrorAnalysisPipelineState) -> str:
        clusters = state.get("clusters")
        # status_msgs will be updated directly in the state by the node if needed,
        # or can be appended here to a copy if preferred.
        group_name = state["group_name"]

        if not state["error_log_docs"]:
            self.logger.warning(
                f"[{group_name}] No error logs fetched, skipping to end."
            )
            return "finish_cluster_processing"

        if clusters and len(clusters) > 0:
            has_meaningful_cluster = any(
                c["cluster_id"] != -1 and c["count"] > 0 for c in clusters if c
            ) or any(
                c["cluster_id"] == -1 and c["count"] > 0 for c in clusters if c
            )  # Noise cluster with docs is meaningful

            if not has_meaningful_cluster:
                self.logger.warning(
                    f"[{group_name}] Clustering resulted only in empty or pure noise clusters. Falling back."
                )
                # Update status_messages in state if this decision path is taken
                # state["status_messages"] = state.get("status_messages", []) + ["Clustering resulted in no meaningful data clusters, using fallback summarization."]
                return "summarize_unclustered_fallback"

            self.logger.info(
                f"[{group_name}] Proceeding with {len(clusters)} cluster results."
            )
            # state["status_messages"] = state.get("status_messages", []) + [f"Clustering successful, proceeding to summarize {len(clusters)} cluster results (incl. noise if any)."]
            return "check_cluster_loop_condition"
        else:
            self.logger.warning(
                f"[{group_name}] No clusters found or clustering step failed. Falling back."
            )
            # state["status_messages"] = state.get("status_messages", []) + ["No valid clusters found or clustering failed, using fallback summarization."]
            return "summarize_unclustered_fallback"

    # This function is now purely for conditional branching logic
    def _conditional_check_cluster_loop(self, state: ErrorAnalysisPipelineState) -> str:
        """Condition to decide if there are more clusters to process."""
        current_idx = state.get("current_cluster_index", 0)
        clusters = state.get("clusters", [])  # clusters could be None if fetch failed
        group_name = state["group_name"]

        if not clusters:  # Handle case where clusters might be None
            self.logger.debug(
                f"[{group_name}] Loop condition: NO, clusters list is not available."
            )
            return "finish_cluster_processing"

        if current_idx < len(clusters):
            current_cluster_to_process = clusters[current_idx]
            if current_cluster_to_process["count"] == 0:
                self.logger.warning(
                    f"[{group_name}] Skipping cluster ID {current_cluster_to_process['cluster_id']} at index {current_idx} as it has zero documents (will re-evaluate loop)."
                )
                # To effectively skip, we need the node to increment the index.
                # This conditional logic should ideally point to a node that increments
                # and then back to itself, or the node "process_this_cluster" must handle
                # the zero count case gracefully and increment.
                # For simplicity, let's assume _check_cluster_loop_node (if it existed as a state updater)
                # would increment the index. Here, we'll just say "process" and let the target node skip.
                # OR, a better approach: Point to a small "increment_and_loop" node.
                # For now, we will rely on process_this_cluster to increment.
                # Actually, the current _check_cluster_loop_node in the graph structure is the one that *returns* the decision string.
                # The node *itself* must return a state update if it modifies current_cluster_index.
                # Let's ensure `process_this_cluster` always increments `current_cluster_index`.
                # The `_sample_and_summarize_cluster_node` already increments `current_cluster_index`.
                return "process_this_cluster"  # It will be processed, sample_and_summarize will increment index.

            self.logger.debug(
                f"[{group_name}] Loop condition: YES, process cluster at index {current_idx} (ID: {clusters[current_idx]['cluster_id']})"
            )
            return "process_this_cluster"
        else:
            self.logger.debug(
                f"[{group_name}] Loop condition: NO, all {len(clusters)} clusters processed."
            )
            return "finish_cluster_processing"

    # Node that does nothing but allow branching.
    def _passthrough_node(self, state: ErrorAnalysisPipelineState) -> Dict[str, Any]:
        """A simple node that makes no changes to the state, used for branching."""
        return {}

    def _build_graph(self) -> CompiledGraph:
        workflow = StateGraph(ErrorAnalysisPipelineState)

        workflow.add_node("fetch_initial_errors", self._fetch_initial_errors_node)
        workflow.add_node("cluster_errors", self._cluster_errors_node)

        # This node is just a branching point. It doesn't modify state.
        # The conditional logic for this branch point is provided by _conditional_check_cluster_loop
        workflow.add_node(
            "check_cluster_loop_condition_branch_point", self._passthrough_node
        )

        workflow.add_node(
            "sample_and_summarize_cluster", self._sample_and_summarize_cluster_node
        )
        workflow.add_node(
            "summarize_unclustered_fallback_node",
            self._sample_and_summarize_unclustered_node,
        )
        workflow.add_node("store_summaries", self._store_summaries_node)

        workflow.set_entry_point("fetch_initial_errors")
        workflow.add_edge("fetch_initial_errors", "cluster_errors")

        # Conditional edge after clustering
        workflow.add_conditional_edges(
            "cluster_errors",  # Source node
            self._decide_clustering_outcome,  # Path mapper function
            {  # Destination map
                "check_cluster_loop_condition": "check_cluster_loop_condition_branch_point",  # Go to the branch point
                "summarize_unclustered_fallback": "summarize_unclustered_fallback_node",
                "finish_cluster_processing": "store_summaries",
            },
        )

        # Conditional edge for the loop itself, originating from the branch point
        workflow.add_conditional_edges(
            "check_cluster_loop_condition_branch_point",  # Source is the branch point node
            self._conditional_check_cluster_loop,  # Path mapper function that decides next step
            {  # Destination map
                "process_this_cluster": "sample_and_summarize_cluster",
                "finish_cluster_processing": "store_summaries",
            },
        )

        # After processing a cluster, it goes back to the branch point to re-evaluate the loop condition
        workflow.add_edge(
            "sample_and_summarize_cluster", "check_cluster_loop_condition_branch_point"
        )

        workflow.add_edge("summarize_unclustered_fallback_node", "store_summaries")
        workflow.add_edge("store_summaries", END)

        return workflow.compile()

    def run(self, initial_state_input: Dict[str, Any]) -> ErrorAnalysisPipelineState:
        self.logger.info(
            f"Starting Error Analysis Pipeline for group: {initial_state_input['group_name']}"
        )
        graph_input_state: ErrorAnalysisPipelineState = {
            "group_name": initial_state_input["group_name"],
            "es_query_for_errors": initial_state_input["es_query_for_errors"],
            "clustering_params": initial_state_input.get("clustering_params", {}),
            "sampling_params": initial_state_input.get("sampling_params", {}),
            "error_log_docs": [],
            "clusters": None,
            "current_cluster_index": 0,
            "current_samples_for_summary": [],
            "generated_summaries": [],
            "status_messages": [],
        }

        # Ensure all keys from ErrorAnalysisPipelineState are present in graph_input_state
        # This is mostly for type hinting and ensuring the TypedDict is satisfied.
        # The graph should correctly populate or handle missing optional fields.
        final_state = self.graph.invoke(graph_input_state)  # type: ignore

        self.logger.info(
            f"Error Analysis Pipeline finished. Status messages: {final_state.get('status_messages')}"
        )
        return final_state  # type: ignore
