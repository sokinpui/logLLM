# logLLM CLI: `es-parse` Command

The `es-parse` command is designed for parsing raw log data that has already been ingested into Elasticsearch (typically via the `collect` command). It leverages advanced agents, including LLM-powered Grok pattern generation and validation, to process logs and store structured results back into Elasticsearch.

**Prerequisites:**

- Elasticsearch must be running (`python -m src.logllm db start`).
- Raw logs must have been collected into Elasticsearch using `python -m src.logllm collect -d <your_log_dir>`.

**Base command:** `python -m src.logllm es-parse <action> [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Actions

The `es-parse` command has three primary actions: `run`, `list`, and `use`.

### `es-parse run`

This action executes the main parsing workflow on logs stored in Elasticsearch.
Key features of the workflow:

- Operates on log groups defined during the `collect` phase.
- Can process a single specified group or all known groups.
- **LLM-Powered Grok Generation:** If no pattern is provided, it samples log lines from Elasticsearch for the group and uses an LLM to generate a Grok pattern.
- **Pattern Validation:** The generated (or provided) pattern is validated against another set of sample lines.
- **Retry Mechanism:** If pattern generation or validation fails, the system can retry a configured number of times, providing context from previous failures to the LLM.
- **Fallback:** If a suitable pattern cannot be established after retries, a generic fallback pattern is used to ingest the original log lines into a "failed" index.
- **Data Indexing:**
  - Successfully parsed logs are indexed into `parsed_log_<group_name>`.
  - Logs that failed parsing with a good pattern, or all logs processed during a fallback, are indexed into `unparsed_log_<group_name>`.
- **History Logging:** A summary of each parsing attempt (status, pattern used, counts) is stored in the `grok_results_history` index.

**Usage:**

```bash
python -m src.logllm es-parse run [OPTIONS]
```

**Options:**

- `-g GROUP`, `--group GROUP`:
  (Optional) Specify a single log group name (e.g., "apache", "hadoop") to parse. If this option is omitted, all groups found in the `group_infos` index in Elasticsearch will be processed.
- `-f FIELD`, `--field FIELD`:
  The field name within the source Elasticsearch documents (e.g., `log_apache`) that contains the raw log line text to be parsed. Defaults to `"content"`.
- `--copy-fields FIELD1 [FIELD2 ...]`
  (Optional) A list of additional field names from the source document that should be copied to the target (parsed or unparsed) document if they don't already exist as a result of parsing.
- `-b BATCH_SIZE`, `--batch-size BATCH_SIZE`:
  The number of log documents to retrieve from Elasticsearch and process/index in each bulk request. Defaults to `1000`.
- `--keep-unparsed`:
  If specified, the agent will _not_ delete the existing `unparsed_log_<group_name>` index before starting the parsing run for that group. By default, this index is cleared to ensure it only contains failures from the current run.
- `-s SAMPLE_SIZE`, `--sample-size SAMPLE_SIZE`:
  The number of log lines to sample from Elasticsearch for the LLM to use when _generating_ a Grok pattern. Defaults to `20`.
- `--validation-sample-size SAMPLE_SIZE`:
  The number of log lines to sample from Elasticsearch for _validating_ a generated or provided Grok pattern. Defaults to `10`.
- `--validation-threshold RATE`:
  A float between 0.0 and 1.0 representing the minimum success rate required on the validation sample for a Grok pattern to be considered acceptable. Defaults to `0.5` (50% match rate).
- `--max-retries NUM_RETRIES`:
  The maximum number of times the system will retry Grok pattern generation and validation if the initial attempts fail. A value of `2` means 1 initial attempt + 2 retries = 3 total attempts. Defaults to `2`.
- `-t THREADS`, `--threads THREADS`:
  (Only applicable when processing all groups, i.e., when `-g` is NOT specified). The number of parallel worker threads to use for processing different log groups concurrently. Defaults to `1` (sequential processing of groups).
- `-p "PATTERN_STRING"`, `--pattern "PATTERN_STRING"`:
  (This option **requires** that `-g GROUP` also be specified). Allows you to provide a specific Grok pattern string to be used for parsing the specified group. This bypasses the LLM generation step for that group. The pattern will still undergo a syntax check and validation against sample lines.

**Examples:**

1.  **Run parsing for ALL log groups using 4 worker threads, with custom sample sizes:**

    ```bash
    python -m src.logllm es-parse run -t 4 -s 30 --validation-sample-size 15
    ```

2.  **Run parsing for only the "hadoop" log group:**

    ```bash
    python -m src.logllm es-parse run -g hadoop
    ```

3.  **Run parsing for the "apache" group using a user-provided Grok pattern, a higher validation threshold, and instruct the system to keep any existing logs in the `unparsed_log_apache` index:**
    ```bash
    python -m src.logllm es-parse run -g apache \
        -p "^\[%{DAY:day} %{MONTH:month} %{MONTHDAY:monthday} %{TIME:timestamp} %{YEAR:year}\] \[%{LOGLEVEL:level}\]" \
        --validation-threshold 0.8 \
        --keep-unparsed
    ```

---

### `es-parse list`

This action queries the `grok_results_history` index in Elasticsearch to display summaries of previous `es-parse run` attempts. This helps you track parsing success, patterns used, and processing counts for different groups over time.

**Usage:**

```bash
python -m src.logllm es-parse list [OPTIONS]
```

**Options:**

- `-g GROUP`, `--group GROUP`:
  (Optional) If specified, shows history results only for this particular group name.
- `-a`, `--all`:
  If specified, shows all historical entries for the selected group(s).
  - If `-g` is also specified, shows all history for that group.
  - If `-g` is NOT specified, shows all history for ALL groups.
    By default (if `-a` is not used):
  - If `-g` is specified, it shows only the _latest_ entry for that group.
  - If `-g` is NOT specified, it shows the _latest_ entry for _each_ group.
- `--group-name`:
  If specified, lists only the unique names of all groups that have entries in the `grok_results_history` index. This is useful for discovering which groups have been processed.
- `--json`:
  Outputs the query results in JSON format instead of the default human-readable text format.

**Examples:**

1.  **List the latest parsing result summary for each group:**

    ```bash
    python -m src.logllm es-parse list
    ```

    _Example Output Snippet:_

    ```
    --- Grok Parsing History Results (2 entries) ---

    Group 'apache' (Recorded: 2025-04-08 13:05:11):
      Status: success_with_errors
      Pattern Detail: ^\[%{DAY:day} ... %{GREEDYDATA:extra_info})$
      Docs Scanned: 56482
      Indexed Successfully (-> parsed_log_apache): 52004
      Failed/Fallback (-> unparsed_log_apache): 4478
      Grok Parse Errors: 4478, Bulk Index Errors: 0

    Group 'ssh' (Recorded: 2025-04-08 18:52:33):
      Status: success
      Pattern Detail: %{SYSLOGTIMESTAMP:timestamp} ... %{GREEDYDATA:message}
      Docs Scanned: 655147
      Indexed Successfully (-> parsed_log_ssh): 655147
      ...
    ```

2.  **List all historical parsing results specifically for the "ssh" group:**

    ```bash
    python -m src.logllm es-parse list -g ssh -a
    ```

3.  **List only the names of all groups that have a parsing history:**

    ```bash
    python -m src.logllm es-parse list --group-name
    ```

4.  **List the latest result for the "apache" group, outputting in JSON format:**
    ```bash
    python -m src.logllm es-parse list -g apache --json
    ```

---

### `es-parse use`

Re-runs the parsing process for a _specific group_ using a Grok pattern that was recorded during a _specific historical run_. This is useful if you identified a particularly good pattern from a past attempt (via `es-parse list`) and want to re-apply it, perhaps to newly collected data for that group or after modifying other configurations.

**Usage:**

```bash
python -m src.logllm es-parse use -g GROUP -t "YYYY-MM-DD HH:MM:SS" [OPTIONS]
```

**Required Options:**

- `-g GROUP`, `--group GROUP`:
  The name of the log group for which you want to re-run parsing.
- `-t "TIMESTAMP"`, `--time "TIMESTAMP"`:
  The exact timestamp string (e.g., `"2025-04-08 18:19:56"`) of the historical `es-parse run` whose Grok pattern you wish to reuse. This timestamp should precisely match the "Recorded:" time displayed in the output of the `es-parse list` command for the desired historical entry.

**Optional Options (These allow overriding some parameters for the re-run):**

- `-f FIELD`, `--field FIELD`: Override the source field for log lines.
- `--copy-fields FIELD1 [FIELD2 ...]` : Override fields to copy.
- `-b BATCH_SIZE`, `--batch-size BATCH_SIZE`: Override batch size.
- `--validation-sample-size SAMPLE_SIZE`: Override validation sample size (the historical pattern will still be validated).
- `--keep-unparsed`: Override the unparsed index handling.

**Example:**
Suppose `es-parse list` shows a successful run for the "ssh" group with the following entry:

```
Group 'ssh' (Recorded: 2025-04-08 18:52:33):
  Status: success
  Pattern Detail: %{SYSLOGTIMESTAMP:timestamp} %{SYSLOGHOST:hostname} sshd\[%{INT:pid}\]: %{GREEDYDATA:message}
  ...
```

To re-run parsing for the "ssh" group using that exact pattern:

```bash
python -m src.logllm es-parse use -g ssh -t "2025-04-08 18:52:33"
```

This command will fetch the Grok pattern `%{SYSLOGTIMESTAMP:timestamp} ...` from the history entry matching that group and time, and then initiate a new parsing run for the "ssh" group using this retrieved pattern. The LLM generation step is bypassed. The results of this new run will also be logged in the history.
