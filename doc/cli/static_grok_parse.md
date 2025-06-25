# logLLM CLI: `static-grok-parse` Command

The `static-grok-parse` command is designed for parsing raw log data that has already been ingested into Elasticsearch (typically via the `collect` command). It uses predefined Grok patterns specified in a YAML file to structure the log data and stores the results back into Elasticsearch.

**Prerequisites:**

- Elasticsearch must be running (`python -m src.logllm db start`).
- Raw logs must have been collected into Elasticsearch using `python -m src.logllm collect -d <your_log_dir>`.
- A Grok patterns YAML file must exist (e.g., `grok_patterns.yaml`).

**Base command:** `python -m src.logllm static-grok-parse <action> [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Actions

The `static-grok-parse` command has three primary actions: `run`, `list`, and `delete`.

### `static-grok-parse run`

This action executes the main parsing workflow using statically defined Grok patterns.

**Workflow Overview:**

- Operates on log groups defined during the `collect` phase (from `group_infos` index).
- Can process a single specified group or all known groups.
- For each group:
  - Retrieves the corresponding Grok pattern and any derived field definitions from the specified YAML file.
  - Iterates through raw log files (from `log_<group_name>`) that haven't been fully parsed, based on status tracked in `static_grok_parse_status`.
  - Applies the Grok pattern to each new log line.
  - If parsing is successful, processes any defined derived fields.
  - Stores successfully parsed logs in `parsed_log_<group_name>`.
  - Stores logs that failed to match the Grok pattern in `unparsed_log_<group_name>`.
  - Updates the `static_grok_parse_status` index to track parsing progress for each file.
- An orchestrator agent (`StaticGrokParserAgent`) manages this process for all selected groups.

**Usage:**

```bash
python -m src.logllm static-grok-parse run [OPTIONS]
```

**Required Options (Group Selection - Mutually Exclusive):**

- `-g GROUP`, `--group GROUP`:
  Specify a single log group name (e.g., "apache", "hadoop") to parse.
- `-a`, `--all-groups`:
  Parse all known log groups found in the `group_infos` index.

**Optional Options:**

- `--grok-patterns-file <FILE_PATH>`:
  Path to the YAML file containing Grok patterns. If not specified, defaults to `grok_patterns.yaml` in the current working directory.
- `--clear`:
  If specified, previously parsed data (`parsed_log_*`, `unparsed_log_*` indices) and status entries in `static_grok_parse_status` for the selected group(s) will be deleted before the parsing run. **Use with caution.**

**Examples:**

1.  **Run parsing for ALL log groups using `my_patterns.yaml` and clear previous results:**

    ```bash
    python -m src.logllm static-grok-parse run --all-groups --grok-patterns-file ./conf/my_patterns.yaml --clear
    ```

2.  **Run parsing for only the "hadoop" log group using the default `grok_patterns.yaml`:**
    ```bash
    python -m src.logllm static-grok-parse run -g hadoop
    ```

**Output:**
The CLI will display a summary of the parsing run, including the overall orchestrator status and status for each processed group (e.g., number of files processed, errors).

---

### `static-grok-parse list`

This action queries the `static_grok_parse_status` index in Elasticsearch to display the current parsing status for individual log files.

**Usage:**

```bash
python -m src.logllm static-grok-parse list [OPTIONS]
```

**Optional Options:**

- `--grok-patterns-file <FILE_PATH>`: (Typically not needed for `list`, but included for consistency if agent needs init).
- `-g GROUP`, `--group GROUP`:
  Filter the status list to show entries only for this particular group name.
- `--json`:
  Outputs the status list in JSON format instead of the default human-readable text format.

**Examples:**

1.  **List the parsing status for all files:**

    ```bash
    python -m src.logllm static-grok-parse list
    ```

    _Example Output Snippet:_

    ```
    --- Static Grok Parsing Status (X entries) ---
      Group: apache
        File ID: <hash_of_file1_path>
        Relative Path: apache/access.log
        Last Grok Parsed Line: 10500
        Collector Total Lines: 10500
        Last Parse Timestamp: 2023-10-27T14:30:00Z
        Last Parse Status: completed_up_to_date
    --------------------
    ...
    ```

2.  **List parsing status for files in the "ssh" group, in JSON format:**
    ```bash
    python -m src.logllm static-grok-parse list -g ssh --json
    ```

---

### `static-grok-parse delete`

This action deletes previously parsed data and status entries for specified groups. It will remove the `parsed_log_<group_name>` and `unparsed_log_<group_name>` indices, and clear entries from `static_grok_parse_status` for the files within those groups.

**Usage:**

```bash
python -m src.logllm static-grok-parse delete [OPTIONS]
```

**Required Options (Group Selection - Mutually Exclusive):**

- `-g GROUP`, `--group GROUP`:
  Specify a single group name whose parsed data and status should be deleted.
- `-a`, `--all-groups`:
  Delete parsed data and status for ALL known groups.

**Optional Options:**

- `--grok-patterns-file <FILE_PATH>`: (Typically not needed for `delete`, but included for consistency if agent needs init).
- `-y`, `--yes`:
  Confirm deletion without prompting. **Use with extreme caution, as this action is irreversible.**

**Examples:**

1.  **Delete all parsed data and status for the "nginx" group (will ask for confirmation):**

    ```bash
    python -m src.logllm static-grok-parse delete -g nginx
    ```

2.  **Delete all parsed data and status for ALL groups, bypassing confirmation:**
    ```bash
    python -m src.logllm static-grok-parse delete --all-groups -y
    ```
