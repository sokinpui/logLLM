# logLLM Command Line Interface (CLI) Documentation

Welcome to the detailed documentation for the `logLLM` Command Line Interface. This guide is broken down by command to help you understand and utilize each feature of the `logLLM` system.

## General Information

- **Invocation:** All `logLLM` commands are run via the Python module execution:
  ```bash
  python -m src.logllm <command> [subcommand/action] [OPTIONS]
  ```
- **Help:** You can get help for any command or subcommand by appending `--help` or `-h`.
  - `python -m src.logllm --help` (for top-level commands)
  - `python -m src.logllm db --help` (for actions of the `db` command)
  - `python -m src.logllm es-parse run --help` (for options of a specific action)

## Global Options

Before diving into specific commands, be aware of the [Global Options](./global_options.md) that can affect how `logLLM` operates, such as `--verbose` for detailed logging, and `--test` or `--json` for specifying prompt files. These options must be placed _before_ the main command.

## Commands

Please select a command from the list below for detailed usage instructions and examples:

- **[`db`](./db.md):** Manage Database Containers (Elasticsearch & Kibana).

  - `start`: Start the database service containers.
  - `status`: Check the status of the containers.
  - `stop`: Stop the containers.
  - `restart`: Restart the containers.

- **[`collect`](./collect.md):** Collect and Ingest Logs into Elasticsearch.

  - Scans directories, groups log files, and ingests raw log lines.

- **[`parse`](./parse.md):** File-based Log Parsing.

  - Parses local log files using Grok patterns (LLM-assisted or user-provided).
  - Outputs structured data to CSV files.
  - Can operate on single files or groups defined by prior collection.

- **[`es-parse`](./es-parse.md):** Elasticsearch-based Log Parsing.

  - `run`: Parses logs already in Elasticsearch, with LLM-assisted Grok generation/validation, and stores structured results back in ES.
  - `list`: Lists history of previous `es-parse run` attempts.
  - `use`: Re-runs parsing for a group using a pattern from a specific historical run.

- **[`normalize-ts`](./normalize-ts.md):** Timestamp Normalization for Parsed Logs.

  - `run`: Processes logs from `parsed_log_*` indices, standardizes timestamps to UTC ISO 8601, and stores them in new `normalized_parsed_log_*` indices.
  - `delete`: Deletes the `normalized_parsed_log_*` indices.

- **[`analyze-errors`](./analyze-errors.md):** (NEW) Analyze and Summarize Error Logs from Elasticsearch.

  - `run`: Executes a pipeline to filter, cluster, sample, and use an LLM to summarize error logs. Stores summaries in ES.
  - `list`: Lists previously generated error summaries from ES.

- **[`pm`](./pm.md):** Prompt Management.
  - `scan`: Scans code to update the prompt JSON file structure.
  - `list`: Lists keys in the prompt store.
  - `add`: Adds or updates a prompt for a key.
  - `rm`: Removes keys from the prompt store.
  - `version`: Shows Git version history for prompts.
  - `revert`: Reverts prompts to a previous Git commit.
  - `diff`: Shows differences in prompts between two Git commits.
