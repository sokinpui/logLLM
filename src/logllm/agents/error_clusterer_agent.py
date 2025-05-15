# src/logllm/agents/error_clusterer_agent.py (NEW FILE)
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from ..config import config as cfg
from ..data_schemas.error_analysis import (  # Assuming new schema file
    ClusterResult,
    LogDocument,
)
from ..utils.llm_model import LLMModel  # For embeddings
from ..utils.logger import Logger


class ErrorClustererAgent:
    def __init__(self, embedding_model: LLMModel):
        self.embedding_model = embedding_model
        self.logger = Logger()

    def _get_embeddings(self, messages: List[str]) -> Optional[np.ndarray]:
        try:
            # The embedding model should handle batching if necessary
            embeddings = self.embedding_model.embedding.embed_documents(messages)
            return np.array(embeddings)
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
        max_docs_for_clustering: int = 2000,  # Limit to prevent OOM with embeddings
    ) -> List[ClusterResult]:
        self.logger.info(
            f"Starting error clustering for {len(error_log_docs)} documents."
        )
        if not error_log_docs:
            return []

        # Limit the number of documents for clustering to manage resources
        docs_to_cluster = error_log_docs
        if len(error_log_docs) > max_docs_for_clustering:
            self.logger.warning(
                f"Clustering on a sample of {max_docs_for_clustering} docs due to large input size."
            )
            # Potentially implement smarter sampling here if needed, e.g., random sample
            import random

            docs_to_cluster = random.sample(error_log_docs, max_docs_for_clustering)

        messages = [doc["_source"].get("message", "") for doc in docs_to_cluster]
        if not any(messages):
            self.logger.warning(
                "No 'message' field found in log documents for clustering."
            )
            # Treat all as one "unparsed" cluster
            stats = self._get_cluster_stats(docs_to_cluster)
            return [
                ClusterResult(
                    cluster_id=0,
                    representative_message="Messages unavailable for clustering",
                    count=len(docs_to_cluster),
                    example_log_docs=docs_to_cluster[:5],
                    all_log_ids_in_cluster=[doc["_id"] for doc in docs_to_cluster],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            ]

        embeddings = self._get_embeddings(messages)
        if embeddings is None or len(embeddings) == 0:
            self.logger.error("Failed to generate embeddings. Cannot cluster.")
            # Fallback: treat all as one big cluster
            stats = self._get_cluster_stats(docs_to_cluster)  # Use docs_to_cluster here
            return [
                ClusterResult(
                    cluster_id=0,
                    representative_message="Embedding generation failed",
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
            dbscan = DBSCAN(
                eps=eps, min_samples=min_samples, metric="cosine"
            )  # Cosine is good for text embeddings
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

            # Choose a representative message (e.g., first one, or shortest, or closest to centroid if calculated)
            representative_message = current_cluster_docs[0]["_source"].get(
                "message", "N/A"
            )
            stats = self._get_cluster_stats(current_cluster_docs)

            clustered_results.append(
                ClusterResult(
                    cluster_id=int(label),  # Ensure it's an int
                    representative_message=representative_message,
                    count=len(current_cluster_docs),
                    example_log_docs=current_cluster_docs[
                        : cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY
                    ],  # Sample for direct inclusion
                    all_log_ids_in_cluster=[doc["_id"] for doc in current_cluster_docs],
                    first_occurrence_ts=stats["first"],
                    last_occurrence_ts=stats["last"],
                )
            )

        self.logger.info(
            f"Clustering complete. Found {len(unique_labels)} clusters (incl. noise)."
        )
        return sorted(
            clustered_results, key=lambda x: x["count"], reverse=True
        )  # Sort by count
