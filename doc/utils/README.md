# Utility Modules Documentation

This section provides detailed documentation for the various utility classes and functions located within the `src/logllm/utils/` directory. These utilities provide foundational support for the core functionalities of the `logLLM` system.

- **[`chunk_manager.md`](./chunk_manager.md):** Describes `ESTextChunkManager` for fetching and serving large text data from Elasticsearch in manageable, token-aware chunks.
- **[`collector_utility.md`](./collector_utility.md):** Details the `Collector` class responsible for discovering, grouping, and ingesting log files into Elasticsearch.
- **[`container_manager_utility.md`](./container_manager_utility.md):** Explains the `DockerManager` class for managing Docker containers, primarily for the Elasticsearch and Kibana environment.
- **[`data_structures.md`](./data_structures.md):** Documents the `dataclasses` used for structuring log-related data (e.g., `LineOfLogFile`, `LogFile`, `Event`).
- **[`database_utility.md`](./database_utility.md):** Covers the `ElasticsearchDatabase` class, which provides an abstraction layer for database operations.
- **[`llm_model.md`](./llm_model.md):** Describes base classes and specific implementations (e.g., `GeminiModel`) for interacting with Large Language Models.
- **[`logger_utility.md`](./logger_utility.md):** Details the singleton `Logger` class for consistent application-wide logging.
- **[`prompts_manager_utility.md`](./prompts_manager_utility.md):** Explains the `PromptsManager` class for managing LLM prompts, including version control with Git. (For CLI usage, see `../cli/pm.md`).
- **[`rag_manager.md`](./rag_manager.md):** Documents the `RAGManager` for managing Retrieval-Augmented Generation capabilities using Elasticsearch as a vector store.
