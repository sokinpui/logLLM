# src/logllm/agents/error_analysis_pipeline_agent.py (NEW FILE)
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from ..utils.database import ElasticsearchDatabase
from ..utils.llm_model import (
    LLMModel,
)  # For embeddings in clusterer, and generation in summarizer
from ..utils.prompts_manager import PromptsManager
from ..utils.logger import Logger
from ..config import config as cfg
from ..data_schemas.error_analysis import (
    LogDocument,
    ClusterResult,
    ErrorSummarySchema,
    ErrorAnalysisPipelineState,
)
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
        self.llm_model = llm_model  # Pass the single LLM model instance
        self.prompts_manager = prompts_manager
        self.logger = Logger()

        # Instantiate atomic agents
        self.clusterer = ErrorClustererAgent(
            embedding_model=llm_model
        )  # Clusterer uses LLM for embeddings
        self.summarizer = ErrorSummarizerAgent(
            llm_model=llm_model, prompts_manager=prompts_manager
        )

        self.graph = self._build_graph()

    # --- Graph Node Implementations ---
    def _fetch_initial_errors_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        self.logger.info(
            f"Fetching initial error logs for group '{state['group_name']}' using query."
        )
        try:
            # Assuming es_query_for_errors is a full ES query body
            # And it specifies _source fields like 'message', '@timestamp'
            error_docs_raw = self.db.scroll_search(
                index=cfg.get_normalized_parsed_log_storage_index(
                    state["group_name"]
                ),  # or parsed_log_*
                query=state["es_query_for_errors"],
            )
            # Convert to LogDocument structure
            error_docs: List[LogDocument] = [
                {"_id": hit["_id"], "_source": hit["_source"]} for hit in error_docs_raw
            ]
            self.logger.info(f"Fetched {len(error_docs)} initial error documents.")
            return {
                "error_log_docs": error_docs,
                "status_messages": [f"Fetched {len(error_docs)} error logs."],
            }
        except Exception as e:
            self.logger.error(f"Failed to fetch initial errors: {e}", exc_info=True)
            return {
                "error_log_docs": [],
                "status_messages": [f"ERROR: Failed to fetch initial errors: {e}"],
            }

    def _cluster_errors_node(self, state: ErrorAnalysisPipelineState) -> Dict[str, Any]:
        self.logger.info("Clustering error logs...")
        if not state["error_log_docs"]:
            self.logger.warning("No error logs to cluster.")
            return {
                "clusters": [],
                "status_messages": state["status_messages"] + ["No logs to cluster."],
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
            "current_cluster_index": 0,
            "status_messages": state["status_messages"]
            + [f"Found {len(clusters)} clusters."],
        }

    def _sample_and_summarize_cluster_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        idx = state["current_cluster_index"]
        cluster = state["clusters"][idx]
        group_name = state["group_name"]
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_per_cluster", cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY
        )

        self.logger.info(
            f"Processing cluster {cluster['cluster_id']} (count: {cluster['count']}) for group {group_name}"
        )

        # Sampling: cluster['example_log_docs'] already contains up to max_samples from clusterer
        # If more sophisticated sampling from cluster['all_log_ids_in_cluster'] is needed, implement here.
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
                f"Generated summary for cluster {cluster['cluster_id']}."
            )
            self.logger.info(f"Summary generated for cluster {cluster['cluster_id']}.")
        else:
            status_msgs.append(
                f"Failed to generate summary for cluster {cluster['cluster_id']}."
            )
            self.logger.warning(f"Failed to summarize cluster {cluster['cluster_id']}.")

        return {"generated_summaries": new_summaries, "status_messages": status_msgs}

    def _sample_and_summarize_unclustered_node(
        self, state: ErrorAnalysisPipelineState
    ) -> Dict[str, Any]:
        # This node runs if clustering is skipped or fails significantly
        self.logger.info("Processing unclustered errors (or fallback from clustering).")
        group_name = state["group_name"]
        sampling_params = state.get("sampling_params", {})
        max_samples = sampling_params.get(
            "max_samples_unclustered", cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY
        )

        # Simple random sampling from all error_log_docs
        import random

        if not state["error_log_docs"]:
            return {
                "status_messages": state["status_messages"]
                + ["No unclustered logs to summarize."]
            }

        samples_for_summary = random.sample(
            state["error_log_docs"], min(len(state["error_log_docs"]), max_samples)
        )

        summary = self.summarizer.run(
            group_name, samples_for_summary, cluster_context=None
        )  # No cluster context

        new_summaries = state.get("generated_summaries", [])
        status_msgs = state.get("status_messages", [])
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
        self.logger.info(f"Storing {len(state['generated_summaries'])} summaries.")
        stored_count = 0
        for summary_obj in state["generated_summaries"]:
            try:
                self.db.insert(
                    summary_obj.model_dump(), index=cfg.INDEX_ERROR_SUMMARIES
                )
                stored_count += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to store summary: {summary_obj.error_category} - {e}",
                    exc_info=True,
                )
                # Add to status_messages in state?
        return {
            "status_messages": state["status_messages"]
            + [f"Stored {stored_count} summaries."]
        }

    # --- Conditional Edges ---
    def _should_continue_clustering_loop(
        self, state: ErrorAnalysisPipelineState
    ) -> str:
        if state["current_cluster_index"] < len(state.get("clusters", [])):
            return "sample_and_summarize_cluster"  # Go to process the current cluster
        return "store_summaries"  # All clusters processed

    def _decide_clustering_outcome(self, state: ErrorAnalysisPipelineState) -> str:
        clusters = state.get("clusters")
        # Define "good" clustering: e.g., at least one non-noise cluster, or certain coverage.
        # For simplicity, if any clusters (even just one, potentially a "noise" cluster if DBSCAN outputs that as 0)
        # are found, we try to process them. Otherwise, fallback.
        if clusters and len(clusters) > 0:
            # Check if all clusters are noise (cluster_id == -1)
            if all(c["cluster_id"] == -1 for c in clusters):
                self.logger.warning(
                    "Clustering resulted only in noise. Falling back to unclustered summarization."
                )
                return "summarize_unclustered_fallback"
            self.logger.info(f"Proceeding with {len(clusters)} clusters.")
            return "start_clustering_loop"  # Path to iterate clusters
        else:
            self.logger.warning(
                "No clusters found or clustering failed. Falling back to unclustered summarization."
            )
            return "summarize_unclustered_fallback"  # Path for unclustered processing

    # --- Build Graph ---
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ErrorAnalysisPipelineState)

        workflow.add_node("fetch_initial_errors", self._fetch_initial_errors_node)
        workflow.add_node("cluster_errors", self._cluster_errors_node)

        # Node to start the loop (just passes through or sets initial loop state)
        workflow.add_node(
            "start_clustering_loop_node", lambda state: {"current_cluster_index": 0}
        )

        workflow.add_node(
            "sample_and_summarize_cluster", self._sample_and_summarize_cluster_node
        )
        # Fallback node if clustering is not effective
        workflow.add_node(
            "summarize_unclustered_fallback_node",
            self._sample_and_summarize_unclustered_node,
        )

        workflow.add_node("store_summaries", self._store_summaries_node)

        # Define Edges
        workflow.set_entry_point("fetch_initial_errors")
        workflow.add_edge("fetch_initial_errors", "cluster_errors")

        # Conditional after clustering
        workflow.add_conditional_edges(
            "cluster_errors",
            self._decide_clustering_outcome,
            {
                "start_clustering_loop": "start_clustering_loop_node",  # Go to loop setup
                "summarize_unclustered_fallback": "summarize_unclustered_fallback_node",  # Go to fallback
            },
        )

        # Loop for processing clusters
        workflow.add_conditional_edges(
            "start_clustering_loop_node",  # From the loop setup node
            self._should_continue_clustering_loop,
            {
                "sample_and_summarize_cluster": "sample_and_summarize_cluster",
                "store_summaries": "store_summaries",  # Done with loop
            },
        )
        workflow.add_edge(
            "sample_and_summarize_cluster",
            lambda state: {"current_cluster_index": state["current_cluster_index"] + 1},
        )  # Increment index
        workflow.add_conditional_edges(  # After incrementing, check condition again to loop or exit
            lambda state: state,  # Pass-through node that just checks state
            self._should_continue_clustering_loop,
            {
                "sample_and_summarize_cluster": "sample_and_summarize_cluster",
                "store_summaries": "store_summaries",
            },
        )

        # Edge from fallback to storage
        workflow.add_edge("summarize_unclustered_fallback_node", "store_summaries")

        workflow.add_edge("store_summaries", END)

        return workflow.compile()

    def run(
        self, initial_state: ErrorAnalysisPipelineState
    ) -> ErrorAnalysisPipelineState:
        self.logger.info(
            f"Starting Error Analysis Pipeline for group: {initial_state['group_name']}"
        )
        # Ensure default values for optional inputs if not provided
        if "clustering_params" not in initial_state:
            initial_state["clustering_params"] = {}
        if "sampling_params" not in initial_state:
            initial_state["sampling_params"] = {}

        final_state = self.graph.invoke(initial_state)
        self.logger.info(
            f"Error Analysis Pipeline finished. Status messages: {final_state.get('status_messages')}"
        )
        return final_state
