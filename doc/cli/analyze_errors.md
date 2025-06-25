# logLLM CLI: `analyze-errors` Command

The `analyze-errors` command provides an interface to the `ErrorSummarizerAgent`, enabling users to analyze and summarize error logs stored in Elasticsearch.

**Prerequisites:**

- Elasticsearch must be running (`python -m src.logllm db start`).
- Raw logs must have been collected (`collect` command).
- Logs must have been parsed into structured fields, especially `loglevel` and `@timestamp`, via `static-grok-parse`.

**Base command:** `python -m src.logllm analyze-errors <action> [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Actions

### `analyze-errors run-summary`

Executes the error log summarization pipeline for a specified group and time window.

**Workflow (simplified from agent perspective):**

1.  **Initialization:** Checks for the target parsed log index (e.g., `parsed_log_<group>`) and required field mappings.
2.  **Fetch Logs:** Retrieves error logs based on the group, time window, and specified error levels.
3.  **Embed Logs:** Generates vector embeddings for the messages of the fetched error logs using the specified embedding model (local or API-based).
4.  **Cluster Logs:** Applies DBSCAN clustering to the embeddings to group similar error messages.
5.  **Summarize & Store:** For each cluster (and unclustered logs), samples representative logs, generates a structured summary using an LLM, and stores this summary in a designated Elasticsearch index (default: `log_error_summaries`).

**Usage:**

```bash
python -m src.logllm analyze-errors run-summary -g GROUP_NAME [OPTIONS]
```

**Required Options:**

- `-g GROUP`, `--group GROUP`:
  The name of the log group (e.g., "apache", "system*kernel") whose `parsed_log*<group>` index should be analyzed.

**Optional Options:**

- `--start-time <ISO_TIMESTAMP>`:
  Start timestamp for log query in ISO 8601 format (e.g., `YYYY-MM-DDTHH:MM:SSZ`). Defaults to 24 hours ago.
- `--end-time <ISO_TIMESTAMP>`:
  End timestamp for log query in ISO 8601 format. Defaults to now.
- `--error-levels <LEVELS_STRING>`:
  Comma-separated list of log levels to consider as errors (e.g., "error,critical,warn"). Input will be lowercased.
  Defaults to values from `cfg.DEFAULT_ERROR_LEVELS` (e.g., `"error,critical,fatal,warn"`).
- `--max-logs <NUMBER>`:
  Maximum number of error logs to fetch and process from the time window.
  Defaults to `cfg.DEFAULT_MAX_LOGS_FOR_SUMMARY` (e.g., 5000).
- `--embedding-model <MODEL_NAME_OR_PATH>`:
  Name or path of the embedding model. Can be a Google API model (e.g., `"models/text-embedding-004"`) or a local Sentence Transformer model (e.g., `"sentence-transformers/all-MiniLM-L6-v2"`).
  Defaults to `cfg.DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY` (e.g., `"sentence-transformers/all-MiniLM-L6-v2"`).
- `--llm-model <MODEL_NAME>`:
  Name of the LLM model for generating summaries (e.g., `"gemini-1.5-flash-latest"`).
  Defaults to `cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION`.
- `--dbscan-eps <FLOAT>`:
  DBSCAN epsilon parameter for clustering.
  Defaults to `cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY` (e.g., 0.3).
- `--dbscan-min-samples <NUMBER>`:
  DBSCAN min_samples parameter for clustering.
  Defaults to `cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY` (e.g., 2).
- `--max-samples-per-cluster <NUMBER>`:
  Maximum log samples from each cluster for LLM input.
  Defaults to `cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY` (e.g., 5).
- `--max-samples-unclustered <NUMBER>`:
  Maximum log samples from unclustered logs for LLM input.
  Defaults to `cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY` (e.g., 10).
- `--output-index <INDEX_NAME>`:
  Elasticsearch index to store the generated summaries.
  Defaults to `cfg.INDEX_ERROR_SUMMARIES` (e.g., `"log_error_summaries"`).

**Examples:**

1.  **Analyze errors for "apache" group, last 24 hours, default settings:**

    ```bash
    python -m src.logllm analyze-errors run-summary -g apache
    ```

2.  **Analyze "error" and "warn" level logs for "myapp" group from Jan 1, 2024, to Jan 2, 2024, using a specific embedding model and LLM:**
    ```bash
    python -m src.logllm analyze-errors run-summary -g myapp \
        --start-time "2024-01-01T00:00:00Z" \
        --end-time "2024-01-02T00:00:00Z" \
        --error-levels "error,warn" \
        --embedding-model "models/text-embedding-004" \
        --llm-model "gemini-1.5-pro-latest"
    ```

**Output:**
The CLI will print a summary of the agent's run, including overall status, any errors, number of logs fetched, cluster assignment overview (if applicable), details of processed clusters (including LLM summaries), and the total number of summaries stored in Elasticsearch.
