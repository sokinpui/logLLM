# logLLM CLI: `analyze-errors` Command

The `analyze-errors` command orchestrates a pipeline to filter, (optionally) cluster, sample, and use a Large Language Model (LLM) to summarize error logs previously ingested and parsed into Elasticsearch. The generated summaries are then stored in a dedicated Elasticsearch index.

**Prerequisites:**

- Elasticsearch must be running (`python -m src.logllm db start`).
- Raw logs must have been collected (`collect` command).
- Logs must have been parsed into structured fields, especially `level` (or `log_level`) and `@timestamp`, ideally via `es-parse` and then timestamp-normalized via `normalize-ts`. The command queries indices like `normalized_parsed_log_<group_name>`.

**Base command:** `python -m src.logllm analyze-errors <action> [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Actions

### `analyze-errors run`

Executes the error analysis and summarization pipeline.

**Workflow:**

1.  **Filter:** Fetches error logs from the specified group's `normalized_parsed_log_<group_name>` index based on provided log levels (e.g., "ERROR,CRITICAL") and a time window.
    - These fetched logs are temporarily stored in a working index (e.g., `temp_error_analysis_<group_name>`), which is cleared at the start of each run for that group.
2.  **Cluster (Optional):** Groups the filtered error messages based on semantic similarity using embeddings and DBSCAN. This helps to identify distinct types of errors. If clustering is ineffective or disabled, proceeds with unclustered data.
3.  **Sample:** Takes a representative sample of log lines from each cluster (or from the unclustered set).
4.  **Summarize with LLM:** For each set of samples, it constructs a prompt and queries an LLM (e.g., Gemini) to generate a structured summary (category, description, potential causes, impact, keywords).
5.  **Store Summary:** Saves the LLM-generated summaries into the `log_error_summaries` Elasticsearch index.

**Usage:**

```bash
python -m src.logllm analyze-errors run -g GROUP_NAME [OPTIONS]
```

**Required Options:**

- `-g GROUP`, `--group GROUP`:
  The name of the log group (e.g., "apache", "ssh") whose parsed logs should be analyzed for errors.

**Optional Options:**

- `--time-window <ES_TIME_STRING>`:
  Specifies the time window for fetching error logs. Uses Elasticsearch date math (e.g., `"now-24h"`, `"now-7d"`, `"2023-01-01||/d"`).
  Defaults to `"now-24h"`.
- `--log-levels <LEVELS_STRING>`:
  A comma-separated string of log levels to filter for (case-insensitive, will be lowercased for query).
  Defaults to `"ERROR,CRITICAL,FATAL"`.
- `--max-initial-errors <NUMBER>`:
  The maximum number of error log documents to fetch initially from Elasticsearch for analysis.
  Defaults to `5000`.
- `--clustering-method <METHOD>`:
  The method to use for clustering errors.
  Choices: `embedding_dbscan`, `none`.
  Defaults to `embedding_dbscan`. If `none`, the clustering step is skipped, and all fetched errors are treated as a single batch for sampling and potential summarization.
- `--dbscan-eps <FLOAT>`:
  (Only if `clustering-method` is `embedding_dbscan`) Epsilon parameter for DBSCAN clustering. Defines the maximum distance between two samples for one to be considered as in the neighborhood of the other.
  Defaults to `0.5` (from `config.py`).
- `--dbscan-min-samples <NUMBER>`:
  (Only if `clustering-method` is `embedding_dbscan`) The number of samples in a neighborhood for a point to be considered as a core point by DBSCAN.
  Defaults to `3` (from `config.py`).
- `--max-samples-per-cluster <NUMBER>`:
  The maximum number of log examples to take from each identified error cluster to provide as context to the LLM for summarization.
  Defaults to `5` (from `config.py`).
- `--max-samples-unclustered <NUMBER>`:
  If clustering is skipped or yields no distinct clusters, this is the maximum number of error logs to sample from the overall filtered set to feed the LLM.
  Defaults to `20` (from `config.py`).

**Examples:**

1.  **Analyze errors for the "apache" group from the last 24 hours, using default error levels and clustering:**

    ```bash
    python -m src.logllm analyze-errors run -g apache
    ```

2.  **Analyze "ERROR" and "WARNING" level logs for "hadoop" group from the last 3 days, with custom DBSCAN parameters:**

    ```bash
    python -m src.logllm analyze-errors run -g hadoop --time-window "now-3d" --log-levels "ERROR,WARNING" --dbscan-eps 0.4 --dbscan-min-samples 2
    ```

3.  **Analyze errors for "nginx" group without clustering, taking up to 30 samples for LLM summarization:**
    ```bash
    python -m src.logllm analyze-errors run -g nginx --clustering-method none --max-samples-unclustered 30
    ```

---

### `analyze-errors list`

Queries the `log_error_summaries` index in Elasticsearch to display previously generated error summaries.

**Usage:**

```bash
python -m src.logllm analyze-errors list [OPTIONS]
```

**Options:**

- `-g GROUP`, `--group GROUP`:
  (Optional) Filter summaries to show only those belonging to the specified group name.
- `--latest <NUMBER>`:
  (Optional) Show only the N most recent summaries (based on `analysis_timestamp`).

**Examples:**

1.  **List all stored error summaries, latest first:**

    ```bash
    python -m src.logllm analyze-errors list
    ```

2.  **List the 5 latest error summaries for the "apache" group:**
    ```bash
    python -m src.logllm analyze-errors list -g apache --latest 5
    ```

**Example Output Snippet for `list`:**

```
--- Stored Error Summaries (1 entries) ---
------------------------------
Group: apache (Analyzed: 2025-05-17T10:30:00.123Z)
Category: Null Pointer Access in UserServlet
Description: The application encountered a null pointer exception when trying to access user session data in UserServlet. This typically happens if a session expires or is invalidated but code attempts to use it.
Potential Causes: Session timeout before operation completion, Invalid session ID being passed, Race condition in session creation/invalidation.
Impact: Affected users would be logged out unexpectedly or see an error page when performing actions requiring a valid session.
Keywords: NullPointerException, UserServlet, SessionInvalid, AuthError
Original Logs Count (in cluster/batch): 15
Input Examples: 5
```
