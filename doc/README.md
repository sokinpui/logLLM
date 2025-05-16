## Core Concepts & Orchestration

- **[Overview](./overview.md):** High-level architecture of the `logLLM` system, focusing on the CLI as the central orchestrator and how it dispatches tasks to various modules and agents.
- **[Configuration](./configurable.md):** Detailed explanation of the `config.py` file and all its variables, covering settings for logging, Docker, databases, LLMs, and agent behaviors.

## Agents

- **[Agent Documentation](./agents/README.md):** An index and overview of all specialized agents used in `logLLM`, with links to detailed documentation for each agent.

## Utilities & Managers

- **[Utility Modules](./utils.md):** Documents various utility classes and functions found in `src/logllm/utils/`, such as database interaction (`database.py`), LLM model abstractions (`llm_model.py`), data structures (`data_struct.py`), Docker container management (`container_manager.py`), logging (`logger.py`), log collection (`collector.py`), RAG capabilities (`rag_manager.py`), and text chunking (`chunk_manager.py`).
- **[Prompt Management](./prompts_manager.md):** In-depth guide to the `PromptsManager` class and the `pm` CLI command for managing, versioning, and utilizing LLM prompts.

## Error Analysis Pipeline

- **[Error Analysis Overview](./error_analysis_overview.md):** Describes the pipeline for filtering, clustering, sampling, and summarizing error logs, including relevant configurations and data structures. Links to detailed documentation for specific agents involved in this pipeline.

## Command Line Interface (CLI)

- **[CLI Commands](./cli/README.md):** Entry point for detailed documentation of all `logLLM` CLI commands, their actions, options, and examples.

This documentation is intended to be a living resource. As `logLLM` evolves, these documents will be updated to reflect new features and changes.
