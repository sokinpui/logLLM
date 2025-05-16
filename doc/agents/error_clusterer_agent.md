# Error Clusterer Agent (`error_clusterer_agent.py`)

## File: `src/logllm/agents/error_clusterer_agent.py`

### Overview

The `ErrorClustererAgent` is responsible for taking a list of filtered error log documents and grouping them into clusters based on the semantic similarity of their error messages. This helps in identifying distinct types of errors within a larger set.

For a general overview of the error analysis pipeline, related configurations, and data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

### Core Logic

1.  Extracts the `message` field (or other relevant text field) from each input `LogDocument`.
2.  Utilizes an embedding model (provided via an `LLMModel` instance, e.g., a Gemini embedding model like `models/text-embedding-004`) to generate vector embeddings for each error message.
3.  Applies the DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm to these embeddings.
    - `eps`: The maximum distance between two samples for one to be considered as in the neighborhood of the other.
    - `min_samples`: The number of samples in a neighborhood for a point to be considered as a core point.
    - These parameters are configurable (see `config.py` and CLI options for `analyze-errors run`).
4.  For each identified cluster (and for noise points, typically labeled -1 by DBSCAN), it compiles a `ClusterResult` object. This object includes:
    - `cluster_id`: The ID assigned by DBSCAN.
    - `representative_message`: A sample message from the cluster.
    - `count`: Number of logs in the cluster.
    - `example_log_docs`: A few full `LogDocument` examples from the cluster for summarization.
    - `all_log_ids_in_cluster`: All document IDs belonging to this cluster.
    - `first_occurrence_ts` / `last_occurrence_ts`: Timestamps of the earliest and latest logs in the cluster.

### Key Methods

- **`__init__(self, embedding_model: LLMModel)`**

  - Initializes the agent with an LLM model instance that is capable of providing text embeddings (e.g., `GeminiModel` which includes `GoogleGenerativeAIEmbeddings`).

- **`run(self, error_log_docs: List[LogDocument], eps: float, min_samples: int, max_docs_for_clustering: int = 2000) -> List[ClusterResult]`**

  - **Description**: The main execution method. It takes a list of `LogDocument` objects (filtered error logs).
  - **Parameters**:
    - `error_log_docs` (List[LogDocument]): The list of error logs to cluster.
    - `eps` (float): DBSCAN `eps` parameter.
    - `min_samples` (int): DBSCAN `min_samples` parameter.
    - `max_docs_for_clustering` (int): An internal limit on the number of documents to process for embedding generation to manage resource usage (defaults to 2000). If more docs are provided, a random sample is taken.
  - **Returns**: (List[ClusterResult]): A list of `ClusterResult` objects, sorted by cluster count in descending order.

- **`_get_embeddings(self, messages: List[str]) -> Optional[np.ndarray]`**

  - **Description**: Internal helper to generate embeddings for a list of text messages using the `self.embedding_model.embedding.embed_documents()` method.
  - **Returns**: (Optional[np.ndarray]): A NumPy array of embeddings, or `None` on failure.

- **`_get_cluster_stats(self, cluster_docs: List[LogDocument]) -> Dict[str, Any]`**
  - **Description**: Internal helper to calculate the first and last occurrence timestamps for a given list of documents within a cluster.
  - **Returns**: (Dict[str, Any]): A dictionary with keys "first" and "last" holding optional ISO timestamp strings.

### Data Structures

Refer to `src/logllm/data_schemas/error_analysis.py` for `LogDocument` and `ClusterResult` definitions, also summarized in [../error_analysis_overview.md](../error_analysis_overview.md).
