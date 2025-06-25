# logLLM Command Line Interface (CLI) Documentation

Welcome to the detailed documentation for the `logLLM` Command Line Interface. This guide is broken down by command to help you understand and utilize each feature of the `logLLM` system.

## General Information

- **Invocation:** All `logLLM` commands are run via the Python module execution:
  ```bash
  python -m src.logllm <command> [subcommand/action] [OPTIONS]
  ```
  Or, if your package is installed and has an entry point configured (e.g., `logllm`):
  ```bash
  logllm <command> [subcommand/action] [OPTIONS]
  ```
- **Help:** You can get help for any command or subcommand by appending `--help` or `-h`.
  - `python -m src.logllm --help` (for top-level commands)
  - `python -m src.logllm db --help` (for actions of the `db` command)
  - `python -m src.logllm static-grok-parse run --help` (for options of a specific action)

## Global Options

Before diving into specific commands, be aware of the [Global Options](./global_options.md) that can affect how `logLLM` operates, such as `--verbose` for detailed logging, and `--test` or `--json` for specifying prompt files. These options must be placed _before_ the main command name.

## Commands

Please select a command from the list below for detailed usage instructions and examples:

- **[`db`](./db.md):** Manage Database Containers (Elasticsearch & Kibana).

  - `start`: Start the database service containers.
  - `status`: Check the status of the containers.
  - `stop`: Stop the containers.
  - `restart`: Restart the containers.

- **[`collect`](./collect.md):** Collect and Ingest Logs into Elasticsearch.

  - Scans directories, groups log files, and ingests raw log lines.

- **[`parse`](./parse.md):** File-based Log Parsing (Local Files to CSV).

  - Parses local log files using Grok patterns (LLM-assisted or user-provided).
  - Outputs structured data to CSV files.
  - Can operate on single files or groups defined by prior collection.

- **[`static-grok-parse`](./static_grok_parse.md):** Elasticsearch-based Log Parsing with Static Grok Patterns.

  - `run`: Parses logs already in Elasticsearch using Grok patterns from a YAML file. Stores structured results back in ES.
  - `list`: Lists the parsing status for files/groups.
  - `delete`: Deletes parsed data and status entries for specified groups.

- **[`normalize-ts`](./normalize_ts.md):** Timestamp Normalization for Parsed Logs in Elasticsearch.

  - `run`: Processes logs from `parsed_log_<group_name>` indices, normalizes various timestamp formats to UTC ISO 8601, and updates the `@timestamp` field in-place.
  - `delete`: Removes the `@timestamp` field from `parsed_log_<group_name>` indices.

- **[`analyze-errors`](./analyze_errors.md):** Analyze and Summarize Error Logs from Elasticsearch.

  - `run-summary`: Executes a pipeline to filter, cluster, sample, and use an LLM to summarize error logs. Stores summaries in ES.
  - _(Future actions like `list-summaries` might be added to the CLI, currently available via API)_

- **[`pm`](./pm.md):** Prompt Management.
  - `scan`: Scans code to update the prompt JSON file structure.
  - `list`: Lists keys in the prompt store.
  - `add`: Adds or updates a prompt for a key.
  - `rm`: Removes keys from the prompt store.
  - `version`: Shows Git version history for prompts.
  - `revert`: Reverts prompts to a previous Git commit.
  - `diff`: Shows differences in prompts between two Git commits.
