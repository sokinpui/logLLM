# logLLM System Overview

This document provides a high-level overview of the `logLLM` system architecture, focusing on how the Command Line Interface (CLI) orchestrates various modules and agents to perform log processing, analysis, and management tasks.

## System Architecture

`logLLM` is designed as a modular system with the following key components:

1.  **Command Line Interface (CLI)** (`src/logllm/cli/`):

    - The primary user interaction point.
    - Parses user commands and arguments.
    - Initializes necessary utility classes (Database, LLM Model, Prompts Manager).
    - Instantiates and runs appropriate Agents to perform the requested tasks.
    - Located in `src/logllm/cli/__main__.py` and individual command files.

2.  **Agents** (`src/logllm/agents/`):

    - Specialized components responsible for complex tasks like log parsing, error analysis, and data transformation.
    - Many newer agents (e.g., `StaticGrokParserAgent`, `ErrorSummarizerAgent`, `TimestampNormalizerAgent`) are built using `langgraph` for managing multi-step workflows.
    - Interact with Utilities (LLM, DB, Prompts) and the Modern Context Protocol to perform their functions.

3.  **Modern Context Protocol (MCP)** (`src/logllm/mcp/`):

    - A foundational architectural layer for standardizing the exchange of rich, structured information.
    - It provides schemas (`ContextItem`, `MCPToolDefinition`), a `ContextManager` for building context payloads, and a `ToolRegistry` for discovering and invoking tools.
    - This enables more intelligent agent interoperability and more nuanced interactions with LLMs.

4.  **Utilities** (`src/logllm/utils/`):

    - **`database.py` (`ElasticsearchDatabase`):** Manages all interactions with Elasticsearch (data storage, querying, indexing).
    - **`llm_model.py` (`GeminiModel`):** Handles communication with Large Language Models (e.g., Google Gemini). It is integrated with the MCP to understand and generate tool calls or structured output.
    - **`local_embedder.py` (`LocalSentenceTransformerEmbedder`):** Provides local text embedding generation using Sentence Transformer models.
    - **`prompts_manager.py` (`PromptsManager`):** Manages LLM prompts stored in a JSON file, including version control with Git.
    - **`collector.py` (`Collector`):** Scans directories, groups log files, and ingests raw log lines into Elasticsearch.
    - **`container_manager.py` (`DockerManager`):** Manages Docker containers for backend services like Elasticsearch and Kibana.
    - **`logger.py` (`Logger`):** Provides a standardized logging facility for the application.
    - **`data_struct.py`**: Defines common data structures (dataclasses) used across the system.
    - **`chunk_manager.py`**: Helps manage large text data from Elasticsearch for LLM processing.

5.  **Configuration** (`src/logllm/config/config.py`):

    - Centralized configuration file for settings related to Docker, Elasticsearch, LLM models, agent parameters, and file paths.

6.  **API (FastAPI)** (`src/logllm/api/`):

    - Provides HTTP endpoints for interacting with `logLLM` functionalities, mirroring many CLI capabilities.
    - Allows for integration with a web-based frontend or other services.

7.  **Frontend (React/TypeScript)** (`frontend/`):
    - A web-based user interface for interacting with the `logLLM` API.

## Core Workflow Examples

The CLI orchestrates tasks by invoking agents and utilities. Here are some primary workflows:

### 1. Log Collection (`collect`)

- **Purpose**: Scans local directories for log files, groups them (e.g., by application type based on parent directory), and ingests raw log lines into Elasticsearch.
- **Handler**: `src/logllm/cli/collect.py`
- **Core Utility**: `src/logllm/utils/collector.py::Collector`
- **Key Outputs (ES Indices)**:
  - `group_infos`: Metadata about log groups and their file paths.
  - `log_<group_name>`: Stores raw log lines for each group.
  - `log_last_line_status`: Tracks progress for incremental collection.
- **Workflow Example (`python -m src.logllm collect -d ./logs`)**:
  1. `__main__.py` calls `handle_collect` in `cli/collect.py`.
  2. `handle_collect` initializes `ElasticsearchDatabase` and `Collector`.
  3. `Collector` scans `./logs`, groups files, and updates `group_infos`.
  4. `Collector.insert_very_large_logs_into_db()` ingests lines into `log_<group>` indices.

### 2. Elasticsearch-based Log Parsing (`static-grok-parse`)

- **Purpose**: Parses raw logs already ingested into Elasticsearch (by `collect`). It uses Grok patterns (defined in a YAML file) to structure log data and stores these structured results back into new Elasticsearch indices. This version uses a LangGraph-based agent for orchestrating the parsing of all groups.
- **Handler**: `src/logllm/cli/static_grok_parse.py`
- **Core Agent**:
  - `src/logllm/agents/static_grok_parser/__init__.py::StaticGrokParserAgent` (LangGraph-based, orchestrates parsing for all groups).
- **Key Outputs (ES Indices)**:
  - `parsed_log_<group_name>`: Successfully parsed and structured log data.
  - `unparsed_log_<group_name>`: Logs that failed parsing with the defined Grok pattern.
  - `static_grok_parse_status`: Tracks parsing progress per file.
- **Workflow Example (`python -m src.logllm static-grok-parse run --all-groups --grok-patterns-file grok_patterns.yaml`)**:
  1. `__main__.py` calls `handle_static_grok_run` in `cli/static_grok_parse.py`.
  2. Handler initializes `ElasticsearchDatabase` and `StaticGrokParserAgent` with the specified patterns file.
  3. Agent's `run()` method executes its internal LangGraph workflow:
     - Fetches all group names from `group_infos`.
     - For each group:
       - Retrieves the specific Grok pattern for the group from the YAML file.
       - Iterates through raw log files (from `log_<group_name>`) not yet fully parsed.
       - Applies the Grok pattern.
       - Bulk-indexes successfully parsed logs into `parsed_log_<group_name>`.
       - Bulk-indexes unparsed logs into `unparsed_log_<group_name>`.
       - Updates `static_grok_parse_status`.
  4. Handler displays a summary from the agent's final state.

### 3. Timestamp Normalization (`normalize-ts`)

- **Purpose**: Processes logs from `parsed_log_<group_name>` indices to discover, parse, and standardize diverse timestamp formats into UTC ISO 8601, storing the result in the `@timestamp` field. This makes time-based queries and analysis consistent.
- **Handler**: `src/logllm/cli/normalize_ts.py`
- **Core Agent**: `src/logllm/agents/timestamp_normalizer/__init__.py::TimestampNormalizerAgent` (LangGraph-based)
- **Key Outputs (ES Indices)**: Modifies `parsed_log_<group_name>` indices in-place by adding/updating the `@timestamp` field.
- **Workflow Example (`python -m src.logllm normalize-ts run -g apache`)**:
  1. Handler initializes `ElasticsearchDatabase` and `TimestampNormalizerAgent`.
  2. Agent's `run()` method executes its LangGraph workflow for the "apache" group:
     - Scrolls through documents in `parsed_log_apache`.
     - For each document, attempts to find and parse a timestamp field using `TimestampNormalizationService`.
     - Updates the document with a normalized `@timestamp` field.
     - Bulk-updates the modified documents back into `parsed_log_apache`.

### 4. Error Analysis & Summarization (`analyze-errors`)

- **Purpose**: Filters error logs from `parsed_log_<group_name>` (ideally after timestamp normalization), clusters them by semantic similarity, samples representative errors, and uses an LLM to generate structured summaries of these errors.
- **Handler**: `src/logllm/cli/analyze_errors.py`
- **Core Agent**: `src/logllm/agents/error_summarizer/__init__.py::ErrorSummarizerAgent` (LangGraph-based)
- **Key Outputs (ES Indices)**:
  - `log_error_summaries`: Stores LLM-generated error summaries.
- **Workflow Example (`python -m src.logllm analyze-errors run-summary -g hadoop --start-time ... --end-time ...`)**:
  1. Handler initializes `ElasticsearchDatabase` and `ErrorSummarizerAgent`.
  2. Agent's `run()` method executes its LangGraph workflow:
     - Fetches error logs from `parsed_log_hadoop` based on time window and log levels.
     - Embeds log messages using an embedding model (local or API).
     - Clusters embeddings using DBSCAN.
     - For each cluster (or unclustered batch), samples logs and uses `LLMService` (with Gemini) to generate an `LogClusterSummaryOutput`.
     - Stores summaries in `log_error_summaries`.

### Alternative: Local File Parsing (`parse`)

- **Purpose**: Parses log files directly from the local filesystem using Grok patterns (LLM-assisted or user-provided) and outputs structured data to CSV files. This is an older parsing method, with `static-grok-parse` being preferred for logs already in Elasticsearch.
- **Handler**: `src/logllm/cli/parse.py`
- **Core Agents**:
  - `src/logllm/agents/parser_agent.py::SimpleGrokLogParserAgent`
  - `src/logllm/agents/parser_agent.py::GroupLogParserAgent` (if `-d` is used, relies on `group_infos` from `collect`)
- **Key Outputs**: CSV files alongside original log files.

## Further Reading

- **Configuration Details**: [./configurable.md](./configurable.md)
- **Modern Context Protocol**: [./mcp/README.md](./mcp/README.md)
- **Agent-Specific Documentation**: [./agents/README.md](./agents/README.md)
- **Utility Class Documentation**: [./utils/README.md](./utils/README.md)
- **CLI Command Reference**: [./cli/README.md](./cli/README.md)
- **Error Analysis Pipeline**: [./error_analysis_overview.md](./error_analysis_overview.md)
