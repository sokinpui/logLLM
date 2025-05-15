# logLLM CLI: `collect` Command

The `collect` command is responsible for discovering log files within a specified directory structure, grouping them, and ingesting their content into Elasticsearch. This step is crucial for making logs available for further processing by commands like `es-parse` and `normalize-ts`.

**Prerequisites:**

- Elasticsearch must be running. You can start it using `python -m src.logllm db start`.

**Base command:** `python -m src.logllm collect [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Functionality

When executed, the `collect` command performs the following actions:

1.  **Scans for Log Files:** Recursively searches the provided directory for files ending with the `.log` extension.
2.  **Groups Files:** Groups the found log files based on their immediate parent directory name. For example, logs in `/path/to/logs/apache/` would belong to the "apache" group.
3.  **Stores Group Information:** Saves metadata about these groups (group name and list of associated file paths) into a dedicated Elasticsearch index (default: `group_infos`, configurable in `config.py`). This information is used by other commands like `parse -d` and `es-parse` to identify logs for processing.
4.  **Ingests Log Lines:** Reads each log file line by line and inserts each line as a separate document into a group-specific Elasticsearch index.
    - The target index for raw logs is typically named `log_<group_name>` (e.g., `log_apache`).
    - It tracks the last line read for each file in another index (default: `log_last_line_status`), allowing for incremental updates if the command is run again on the same directory (it will only ingest new lines).
    - Uses efficient bulk indexing for performance.

---

## Options

- `-d DIRECTORY`, `--directory DIRECTORY` (Required):
  The path to the root directory containing the log files or subdirectories with log files. The command will scan this directory and its subdirectories.

---

## Examples

1.  **Collect logs from a local directory named `app_logs`:**
    Assume `app_logs` has the following structure:

    ```
    app_logs/
    ├── service_a/
    │   ├── access.log
    │   └── error.log
    └── service_b/
        └── application.log
    ```

    Command:

    ```bash
    python -m src.logllm collect -d ./app_logs
    ```

    - This will create two groups: "service_a" and "service_b".
    - Log lines from `access.log` and `error.log` will go into an Elasticsearch index like `log_service_a`.
    - Log lines from `application.log` will go into an index like `log_service_b`.
    - The `group_infos` index will be updated with information about these groups and files.

2.  **Collect logs from a system log directory:**
    ```bash
    python -m src.logllm collect -d /var/log
    ```
    This will scan `/var/log` and its subdirectories (e.g., `/var/log/apache2`, `/var/log/syslog`) for `.log` files, creating appropriate groups and ingesting the logs.

---

**Important Notes:**

- Running `collect` multiple times on the same directory will only ingest new lines appended to existing log files since the last run. It does not re-ingest already processed lines.
- The structure of the ingested documents includes the log content, line number, original file path, file ID, and an ingestion timestamp.
