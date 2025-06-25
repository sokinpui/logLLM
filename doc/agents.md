# Detailed Documentation for Agent-Related Files

This document provides an index and overview of the agents used within the `logLLM` project. Agents are specialized components designed for specific tasks, often involving complex workflows, interactions with Large Language Models (LLMs), and database operations.

---

## Core Agent Abstraction

- **[`Agent Abstract Base Class (agent_abc.md)`](./agents/agent_abc.md):** Describes `Agent`, the foundational abstract class for many agents, particularly those built with LangGraph.

---

## Log Processing and Analysis Agents

### 1. Filesystem-based Log Parsing (`src/logllm/agents/parser_agent.py`)

These agents parse log files directly from the local filesystem.

- **[`SimpleGrokLogParserAgent`](./agents/simple_grok_log_parser_agent.md):** Parses single log files using Grok patterns. It can utilize an LLM to generate a pattern if one is not provided. Outputs to CSV.
- **[`GroupLogParserAgent`](./agents/group_log_parser_agent.md):** Orchestrates the parsing of multiple log files. It uses group information (previously collected into Elasticsearch) to identify files and can delegate parsing of individual files to `SimpleGrokLogParserAgent`. Supports parallel processing.

### 2. Elasticsearch-based Log Parsing (`src/logllm/agents/static_grok_parser/`)

This agent processes raw log data that has already been ingested into Elasticsearch. It uses predefined Grok patterns from a YAML file.

- **[`StaticGrokParserAgent`](./agents/static_grok_parser_agent.md):** A LangGraph-based agent that orchestrates the parsing workflow for all log groups. It reads raw logs from `log_<group_name>` indices, applies Grok patterns, handles derived fields, and stores structured results in `parsed_log_<group_name>` and unparsed logs in `unparsed_log_<group_name>`. Manages parsing status per file in `static_grok_parse_status`.

### 3. Timestamp Normalization (`src/logllm/agents/timestamp_normalizer/`)

This agent standardizes timestamp information in parsed logs stored in Elasticsearch.

- **[`TimestampNormalizerAgent`](./agents/timestamp_normalizer_agent.md):** A LangGraph-based agent that processes documents in `parsed_log_<group_name>` indices. It identifies and parses various timestamp formats, converts them to UTC ISO 8601, and updates the `@timestamp` field in-place. It can also be used to remove the `@timestamp` field.

### 4. Error Analysis and Summarization (`src/logllm/agents/error_summarizer/`)

This agent analyzes error logs from Elasticsearch, clusters them, samples representative logs, and uses an LLM to generate structured summaries.

- **[`ErrorSummarizerAgent`](./agents/error_summarizer_agent.md):** A LangGraph-based agent that orchestrates the entire error analysis pipeline. This includes fetching error logs, generating embeddings (using local or API models), clustering similar errors, sampling logs from clusters, generating structured summaries via an LLM, and storing these summaries in Elasticsearch (index `log_error_summaries`).
  - **Overview of the pipeline**: [../error_analysis_overview.md](../error_analysis_overview.md)

---

## Utility Note

Several utility classes support agent operations:

- `ESTextChunkManager` for handling large text data from Elasticsearch.
- `LocalSentenceTransformerEmbedder` for local text embeddings.
- `LLMModel` (and `GeminiModel`) for LLM interactions.
- `ElasticsearchDatabase` for database operations.
- `PromptsManager` for managing LLM prompts.

Refer to the [Utilities Documentation](./utils/README.md) for more details on these supporting modules.
