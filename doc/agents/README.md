# logLLM Agents Documentation

This section provides detailed documentation for the various agents used within the `logLLM` project. Agents are specialized components responsible for carrying out specific tasks, often involving interaction with Large Language Models (LLMs), databases, or other utilities.

## Core Agent Abstraction

- **[`agent_abc.md`](./agent_abc.md):** Describes the abstract base class `Agent`, which defines the common interface for all agents in the system, particularly those utilizing graph-based workflows like LangGraph.

## Log Processing and Parsing Agents

### Filesystem-based Parsing (Local Files to CSV)

These agents parse log files directly from the local filesystem and typically output CSV files.

- **[`simple_grok_log_parser_agent.md`](./simple_grok_log_parser_agent.md):** Details the `SimpleGrokLogParserAgent` for parsing single log files with Grok, potentially using an LLM for pattern generation if no pattern is provided.
- **[`group_log_parser_agent.md`](./group_log_parser_agent.md):** Explains the `GroupLogParserAgent`, which orchestrates parsing of multiple log files grouped by directory structure (based on `group_infos` from ES), delegating to `SimpleGrokLogParserAgent` for individual file parsing.

### Elasticsearch-based Log Parsing (Raw ES Logs to Structured ES Logs)

This agent parses raw log data already ingested into Elasticsearch, using statically defined Grok patterns.

- **[`static_grok_parser_agent.md`](./static_grok_parser_agent.md):** Documents the `StaticGrokParserAgent`, a LangGraph-based agent that orchestrates the parsing of log groups within Elasticsearch using Grok patterns defined in a YAML file. It manages status tracking and bulk indexing of parsed/unparsed results.

### Timestamp Normalization Agent

This agent processes parsed logs in Elasticsearch to standardize timestamp information.

- **[`timestamp_normalizer_agent.md`](./timestamp_normalizer_agent.md):** Details the `TimestampNormalizerAgent`, a LangGraph-based agent that scans `parsed_log_<group_name>` indices, normalizes various timestamp formats to UTC ISO 8601, and updates the `@timestamp` field in-place. It can also remove the `@timestamp` field.

## Error Analysis and Summarization Agent

This agent forms a pipeline to filter, cluster, sample, and summarize error logs from Elasticsearch.

- **[`error_summarizer_agent.md`](./error_summarizer_agent.md):** Describes the `ErrorSummarizerAgent`, a LangGraph-based agent responsible for the entire error analysis workflow. This includes fetching error logs, embedding messages, clustering similar errors, sampling representative logs, generating structured summaries using an LLM, and storing these summaries.
  - For an overview of the pipeline, configuration, and shared data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

## Utility Note

Some utility classes, while not agents themselves, are crucial for agent operations. For example:

- `ESTextChunkManager` (documented in `utils/chunk_manager.md`) helps agents process large text data from Elasticsearch in manageable chunks.
- `LocalSentenceTransformerEmbedder` (documented in `utils/local_sentence_transformer_embedder.md`) provides local embedding capabilities.
