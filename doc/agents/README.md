# logLLM Agents Documentation

This section provides detailed documentation for the various agents used within the `logLLM` project. Agents are specialized components responsible for carrying out specific tasks, often involving interaction with Large Language Models (LLMs), databases, or other utilities.

## Core Agent Abstraction

- **[`agent_abc.md`](./agent_abc.md):** Describes the abstract base class `Agent`, which defines the common interface for all agents in the system, particularly those utilizing graph-based workflows like LangGraph.

## Log Parsing Agents

### Filesystem-based Parsing (using Grok)

These agents parse log files directly from the local filesystem.

- **[`simple_grok_log_parser_agent.md`](./simple_grok_log_parser_agent.md):** Details the `SimpleGrokLogParserAgent` for parsing single log files with Grok, potentially using LLM for pattern generation.
- **[`group_log_parser_agent.md`](./group_log_parser_agent.md):** Explains the `GroupLogParserAgent`, which orchestrates parsing of multiple log files grouped by directory structure, delegating to `SimpleGrokLogParserAgent`.

### Elasticsearch-based Parsing (using Grok and LangGraph)

These agents parse logs already ingested into Elasticsearch, employing more complex, multi-step workflows managed by LangGraph.

- **[`scroll_grok_parser_agent.md`](./scroll_grok_parser_agent.md):** Documents the `ScrollGrokParserAgent`, a lower-level agent for iterating through ES documents, applying Grok patterns, and bulk indexing results.
- **[`single_group_parser_agent.md`](./single_group_parser_agent.md):** Describes the `SingleGroupParserAgent`, which manages the entire parsing workflow for a single log group in Elasticsearch, including LLM pattern generation, validation, and history logging.
- **[`all_groups_parser_agent.md`](./all_groups_parser_agent.md):** Details the `AllGroupsParserAgent`, an orchestrator for concurrently parsing all log groups in Elasticsearch using multiple `SingleGroupParserAgent` instances.

## Error Analysis and Summarization Agents

These agents form a pipeline to filter, cluster, sample, and summarize error logs from Elasticsearch. For an overview of the pipeline, configuration, and shared data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

- **[`error_clusterer_agent.md`](./error_clusterer_agent.md):** Explains the `ErrorClustererAgent`, which groups similar error log messages using embeddings and clustering algorithms.
- **[`error_summarizer_agent.md`](./error_summarizer_agent.md):** Describes the `ErrorSummarizerAgent`, responsible for taking sampled error logs and generating structured summaries using an LLM.
- **[`error_analysis_pipeline_agent.md`](./error_analysis_pipeline_agent.md):** Details the `ErrorAnalysisPipelineAgent`, the LangGraph-based orchestrator for the entire error analysis and summarization workflow.

## Utility Note

Some utility classes, while not agents themselves, are crucial for agent operations. For example, `ESTextChunkManager` (documented in `utils.md`) helps agents process large text data from Elasticsearch in manageable chunks.
