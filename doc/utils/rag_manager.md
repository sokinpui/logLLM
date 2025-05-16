# RAG Manager Utility (`rag_manager.py`)

## File: `src/logllm/utils/rag_manager.py`

### Overview

Manages Retrieval-Augmented Generation (RAG) capabilities, using Elasticsearch as a vector store for document embeddings.

### Class: `RAGManager`

- **Purpose**: Loads documents, splits them, creates embeddings, stores them in an Elasticsearch vector index, and retrieves relevant document chunks based on a query to provide context to an LLM.
- **Key Methods**:
  - **`__init__(self, name: str, db: ElasticsearchDatabase, embeddings, model: LLMModel, multi_threading: bool = False)`**: Initializes the manager, setting up the `ElasticsearchStore` connected to a specific index (`cfg.INDEX_VECTOR_STORE + "_" + name`).
  - **`retrieve(self, prompt: str) -> str`**: Performs a similarity search in the vector store based on the `prompt`, retrieves top N documents, formats their content, and embeds it into a contextual prompt template (`prompts.rag.prompt`).
  - **`update_rag_from_directory(self, directory: str, db: ElasticsearchDatabase, file_extension: str = "md")`**: Clears the existing vector index, loads documents from the specified `directory` (using `DirectoryLoader`), splits them into chunks (using `RecursiveCharacterTextSplitter`), generates embeddings, and indexes the chunks into the Elasticsearch vector store.
  - **`_load_from_directory(...)`**: Internal helper called by `update_rag_from_directory` to handle loading, splitting, and indexing documents.
