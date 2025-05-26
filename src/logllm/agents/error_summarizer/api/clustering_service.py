# src/logllm/agents/error_summarizer/api/clustering_service.py
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import DBSCAN

from ....utils.logger import Logger


class LogClusteringService:
    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger or Logger()

    def cluster_logs_dbscan(
        self,
        log_embeddings: List[List[float]],
        eps: float = 0.5,
        min_samples: int = 5,
    ) -> List[int]:
        """
        Clusters log embeddings using DBSCAN.

        Args:
            log_embeddings: A list of embedding vectors.
            eps: The maximum distance between two samples for one to be considered
                 as in the neighborhood of the other.
            min_samples: The number of samples in a neighborhood for a point
                         to be considered as a core point.

        Returns:
            A list of cluster labels for each log entry. Outliers are labeled -1.
        """
        if not log_embeddings:
            self._logger.warning("No log embeddings provided for clustering.")
            return []

        self._logger.info(
            f"Starting DBSCAN clustering with eps={eps}, min_samples={min_samples} on {len(log_embeddings)} embeddings."
        )

        try:
            embeddings_array = np.array(log_embeddings)
            if embeddings_array.ndim == 1:  # Single embedding
                self._logger.warning(
                    "Only one embedding provided. Assigning to cluster 0 or -1 if min_samples > 1."
                )
                return [0] if min_samples <= 1 else [-1]
            if embeddings_array.shape[0] < min_samples:
                self._logger.warning(
                    f"Number of embeddings ({embeddings_array.shape[0]}) is less than min_samples ({min_samples}). All points will be outliers."
                )
                return [-1] * embeddings_array.shape[0]

            dbscan = DBSCAN(
                eps=eps, min_samples=min_samples, metric="cosine"
            )  # Cosine is often good for text embeddings
            cluster_labels = dbscan.fit_predict(embeddings_array)

            n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
            n_noise = list(cluster_labels).count(-1)
            self._logger.info(
                f"DBSCAN clustering completed. Found {n_clusters} clusters and {n_noise} noise points."
            )
            return cluster_labels.tolist()
        except Exception as e:
            self._logger.error(f"Error during DBSCAN clustering: {e}", exc_info=True)
            return [-1] * len(log_embeddings)  # Return all as outliers on error
