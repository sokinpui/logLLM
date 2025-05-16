### 1. Log Collection (`collect`)

- **Purpose**: Scans local directories for `.log` files, groups them by parent directory, and ingests raw log lines into Elasticsearch.
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

### 2. Elasticsearch-based Log Parsing (`es-parse`)

- **Purpose**: Parses raw logs already ingested into Elasticsearch (by `collect`). It uses LLM-assisted Grok pattern generation and validation, processes logs in batches, and stores structured results back into new Elasticsearch indices.
- **Handler**: `src/logllm/cli/es_parse.py`
- **Core Agents**:
  - `src/logllm/agents/es_parser_agent.py::SingleGroupParserAgent` (LangGraph-based, for one group)
  - `src/logllm/agents/es_parser_agent.py::AllGroupsParserAgent` (Orchestrates multiple `SingleGroupParserAgent` instances)
  - `src/logllm/agents/es_parser_agent.py::ScrollGrokParserAgent` (Core ES data processing)
- **Key Outputs (ES Indices)**:
  - `parsed_log_<group_name>`: Successfully parsed and structured log data.
  - `unparsed_log_<group_name>`: Logs that failed parsing or were processed by a fallback pattern.
  - `grok_results_history`: Summary of each parsing run (status, pattern, counts).
- **Workflow Example (`python -m src.logllm es-parse run -g hadoop`)**:
  1. `__main__.py` calls `handle_es_parse` in `cli/es_parse.py`.
  2. Handler initializes `ElasticsearchDatabase`, `GeminiModel`, `PromptsManager`.
  3. Handler initializes `SingleGroupParserAgent` for "hadoop".
  4. Agent's `run()` method executes its internal LangGraph workflow:
     - Fetch samples from `log_hadoop`.
     - Generate/validate Grok pattern (LLM involved).
     - Use `ScrollGrokParserAgent` to read from `log_hadoop`, parse, and bulk-index to `parsed_log_hadoop` and `unparsed_log_hadoop`.
     - Store run summary in `grok_results_history`.
  5. Handler displays summary from agent's final state.
     _(For `es-parse run` without `-g`, `AllGroupsParserAgent` manages concurrent processing of all groups.)_

### 3. Timestamp Normalization (`normalize-ts`)

- **Purpose**: Processes logs from `parsed_log_<group_name>` indices to standardize diverse timestamp formats into UTC ISO 8601, stored in the `@timestamp` field.
- **Handler**: `src/logllm/cli/normalize_ts.py`
- **Core Processor**: `src/logllm/processors/timestamp_normalizer.py::TimestampNormalizerAgent`
- **Key Outputs (ES Indices)**:
  - `normalized_parsed_log_<group_name>`: Parsed logs with standardized `@timestamp`.
- **Workflow Example (`python -m src.logllm normalize-ts run -g apache`)**:
  1. Handler calls `TimestampNormalizerAgent.process_group("apache")`.
  2. Agent scrolls `parsed_log_apache`, normalizes timestamps, and bulk-indexes results to `normalized_parsed_log_apache`.

### 4. Error Analysis & Summarization (`analyze-errors`)

- **Purpose**: Filters error logs from `normalized_parsed_log_<group_name>`, (optionally) clusters them, samples representative errors, and uses an LLM to generate structured summaries.
- **Handler**: `src/logllm/cli/analyze_errors.py`
- **Core Agent**: `src/logllm/agents/error_analysis_pipeline_agent.py::ErrorAnalysisPipelineAgent` (LangGraph-based)
  - Sub-agents: `ErrorClustererAgent`, `ErrorSummarizerAgent`.
- **Key Outputs (ES Indices)**:
  - `temp_error_analysis_<group_name>` (Temporary working index, deleted on next run for the group).
  - `log_error_summaries`: Stores LLM-generated error summaries.
- **Workflow Example (`python -m src.logllm analyze-errors run -g hadoop`)**:
  1. Handler initializes `ErrorAnalysisPipelineAgent`.
  2. Agent's `run()` method executes its LangGraph workflow:
     - Fetch errors from `normalized_parsed_log_hadoop` into `temp_error_analysis_hadoop`.
     - Cluster errors using `ErrorClustererAgent`.
     - For each cluster (or unclustered batch), sample logs and use `ErrorSummarizerAgent` (with LLM) to generate an `ErrorSummarySchema`.
     - Store summaries in `log_error_summaries`.

### Alternative: Local File Parsing (`parse`)

- **Purpose**: Parses log files directly from the local filesystem using Grok patterns (LLM-assisted or user-provided) and outputs structured data to CSV files.
- **Handler**: `src/logllm/cli/parse.py`
- **Core Agents**:
  - `src/logllm/agents/parser_agent.py::SimpleGrokLogParserAgent`
  - `src/logllm/agents/parser_agent.py::GroupLogParserAgent` (if `-d` is used, relies on `group_infos` from `collect`)
- **Key Outputs**: CSV files alongside original log files.

## Further Reading

- **Configuration Details**: [../configurable.md](../configurable.md)
- **Agent-Specific Documentation**: [../agents/README.md](../agents/README.md)
- **Utility Class Documentation**: [../utils/README.md](../utils/README.md)
- **CLI Command Reference**: [../cli/README.md](../cli/README.md)
- **Error Analysis Pipeline**: [../error_analysis_overview.md](../error_analysis_overview.md)
