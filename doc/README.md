# logLLM Documentation

Welcome to the official documentation for `logLLM`, a comprehensive system for advanced log management and analysis using Large Language Models.

This documentation serves as a central resource for developers and contributors to understand the architecture, components, and workflows of the project.

## Core Concepts & Orchestration

- **[Overview](./overview.md):** High-level architecture of the `logLLM` system, focusing on the CLI as the central orchestrator and how it dispatches tasks to various modules and agents.
- **[Configuration](./configurable.md):** Detailed explanation of the `config.py` file and all its variables, covering settings for logging, Docker, databases, LLMs, and agent behaviors.

## Modern Context Protocol (MCP)

- **[MCP Overview](./mcp/README.md):** Introduction to the Modern Context Protocol, the standardized framework for managing and exchanging rich, structured information between system components to enable more intelligent and interconnected operations.

## Agents

- **[Agent Documentation](./agents/README.md):** An index and overview of all specialized agents used in `logLLM`, with links to detailed documentation for each agent.

## Utilities & Managers

- **[Utility Modules](./utils/README.md):** An index and overview of utility classes and functions found in `src/logllm/utils/`, with links to detailed documentation for each utility module.

## Prompt Management

- **[Prompt Management Overview](./prompts_manager.md):** Overview of the prompt management system, linking to utility class details and CLI command documentation.
  - For `PromptsManager` class details: See [./utils/prompts_manager_utility.md](./utils/prompts_manager_utility.md).
  - For `pm` CLI command details: See [./cli/pm.md](./cli/pm.md).

## Error Analysis Pipeline

- **[Error Analysis Overview](./error_analysis_overview.md):** Describes the pipeline for filtering, clustering, sampling, and summarizing error logs, including relevant configurations and data structures. Links to detailed documentation for specific agents involved in this pipeline.

## Command Line Interface (CLI)

- **[CLI Commands](./cli/README.md):** Entry point for detailed documentation of all `logLLM` CLI commands, their actions, options, and examples.

This documentation is intended to be a living resource. As `logLLM` evolves, these documents will be updated to reflect new features and changes.
