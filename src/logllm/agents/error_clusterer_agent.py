# src/logllm/agents/error_clusterer_agent.py
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import DBSCAN

from ..config import config as cfg
from ..data_schemas.error_analysis import (
    ClusterResult,
    LogDocument,
)
from ..utils.llm_model import LLMModel
from ..utils.logger import Logger

# from sklearn.preprocessing import StandardScaler # Not currently used


class ErrorClustererAgent:
    def __init__(self, embedding_model: LLMModel):
        self.embedding_model = embedding_model
        self.logger = Logger()

    def _get_embeddings(self, messages: List[str]) -> Optional[np.ndarray]:
        try:
            # Use a task_type suitable for clustering/similarity
            # The embedding_model.generate_embeddings method should handle batching if necessary
            embeddings_list_of_lists = self.embedding_model.generate_embeddings(
                messages,
                task_type="SEMANTIC_SIMILARITY",  # Or "CLUSTERING" if preferred and supported well
            )
            if not embeddings_list_of_lists:
                self.logger.warning(
                    "generate_embeddings returned no embeddings (possibly empty input or all empty strings)."
                )
                return np.array(
                    []
                )  # Return empty array to be handled by downstream logic

            return np.array(embeddings_list_of_lists)
        except Exception as e:
            self.logger.error(
                f"Failed to get embeddings for messages: {e}", exc_info=True
            )
            return None

    def _get_cluster_stats(self, cluster_docs: List[LogDocument]) -> Dict[str, Any]:
        if not cluster_docs:
            return {"first": None, "last": None}
        timestamps = sorted(
            [
                doc["_source"].get("@timestamp")
                for doc in cluster_docs
                if doc["_source"].get("@timestamp")
            ]
        )
        return {
            "first": timestamps[0] if timestamps else None,
            "last": timestamps[-1] if timestamps else None,
        }

    def run(
        self,
        error_log_docs: List[LogDocument],
        eps: float = cfg.DEFAULT_DBSCAN_EPS,
        min_samples: int = cfg.DEFAULT_DBSCAN_MIN_SAMPLES,
        max_docs_for_clustering: int = cfg.DEFAULT_MAX_DOCS_FOR_CLUSTERING,
    ) -> List[ClusterResult]:
        self.logger.info(
            f"Starting error clustering for {len(error_log_docs)} documents. Max docs for actual clustering: {max_docs_for_clustering}."
        )
        if not error_log_docs:
            return []

        # Limit the number of documents for clustering to manage resources
        docs_to_cluster = error_log_docs
        if len(error_log_docs) > max_docs_for_clustering:
            self.logger.warning(
                f"Clustering on a sample of {max_docs_for_clustering} docs from {len(error_log_docs)} due to large input size."
            )
            import random

            docs_to_cluster = random.sample(error_log_docs, max_docs_for_clustering)

        messages = [doc["_source"].get("message", "") for doc in docs_to_cluster]
        if not any(messages):  # Check if all messages are empty or missing
            self.logger.warning(
                "No non-empty 'message' field found in log documents selected for clustering."
            )
            stats = self._get_cluster_stats(docs_to_cluster)
            return [
                ClusterResult(
                    cluster_id=0,  # Using 0 for a single "unparsable" group
                    representative_message="Messages unavailable or empty for clustering",
                    count=len(docs_to_cluster),
                    example_log_docs=docs_to_cluster[:5],
                    all_log_ids_in_cluster=[doc["_id"] for doc in docs_to_cluster],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            ]

        embeddings = self._get_embeddings(messages)
        if (
            embeddings is None or len(embeddings) == 0
        ):  # len(embeddings) == 0 handles empty np.array
            self.logger.error(
                "Failed to generate embeddings or no embeddings produced. Cannot cluster."
            )
            stats = self._get_cluster_stats(docs_to_cluster)
            return [
                ClusterResult(
                    cluster_id=0,
                    representative_message="Embedding generation failed or yielded no results",
                    count=len(docs_to_cluster),
                    example_log_docs=docs_to_cluster[:5],
                    all_log_ids_in_cluster=[doc["_id"] for doc in docs_to_cluster],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            ]

        # Scale embeddings (optional but often good for DBSCAN)
        # embeddings_scaled = StandardScaler().fit_transform(embeddings) # Consider if needed

        # DBSCAN Clustering
        try:
            dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
            labels = dbscan.fit_predict(embeddings)
        except Exception as e:
            self.logger.error(f"DBSCAN clustering failed: {e}", exc_info=True)
            stats = self._get_cluster_stats(docs_to_cluster)
            return [
                ClusterResult(
                    cluster_id=0,
                    representative_message="Clustering algorithm failed",
                    count=len(docs_to_cluster),
                    example_log_docs=docs_to_cluster[:5],
                    all_log_ids_in_cluster=[doc["_id"] for doc in docs_to_cluster],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            ]

        clustered_results: List[ClusterResult] = []
        unique_labels = set(labels)

        for label in unique_labels:
            cluster_indices = [i for i, l in enumerate(labels) if l == label]
            current_cluster_docs = [docs_to_cluster[i] for i in cluster_indices]

            if not current_cluster_docs:
                continue

            representative_message = current_cluster_docs[0]["_source"].get(
                "message", "N/A"
            )
            if (
                label == -1
                and representative_message == "N/A"
                and len(current_cluster_docs) > 0
            ):
                # Try to find a more meaningful representative message for noise if first is bad
                for doc_in_noise in current_cluster_docs:
                    msg = doc_in_noise["_source"].get("message")
                    if msg and msg != "N/A":
                        representative_message = msg
                        break
            if label == -1:  # For noise points
                representative_message = (
                    f"Noise (misc. errors) - e.g., {representative_message[:100]}..."
                )

            stats = self._get_cluster_stats(current_cluster_docs)

            clustered_results.append(
                ClusterResult(
                    cluster_id=int(label),
                    representative_message=representative_message,
                    count=len(current_cluster_docs),
                    example_log_docs=current_cluster_docs[
                        : cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY
                    ],
                    all_log_ids_in_cluster=[doc["_id"] for doc in current_cluster_docs],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            )

        self.logger.info(
            f"Clustering complete. Found {len(unique_labels)} clusters (label -1 indicates noise)."
        )
        return sorted(clustered_results, key=lambda x: x["count"], reverse=True)
