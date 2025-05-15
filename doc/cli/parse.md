# logLLM CLI: `parse` Command

The `parse` command is used for parsing log files directly from the local filesystem using Grok patterns. The parsed output is typically written to CSV files. This command can operate on a single file or, in conjunction with previously collected group information, parse all files belonging to known log groups.

**Base command:** `python -m src.logllm parse [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Functionality

- **Single File Parsing (`-f`):**

  - Takes a path to a single log file.
  - If a Grok pattern is provided via `--grok-pattern`, it uses that pattern.
  - If no pattern is provided, it samples lines from the file and uses an LLM (e.g., Gemini) to attempt to generate a suitable Grok pattern.
  - Parses the file line by line using the determined Grok pattern.
  - Writes the parsed fields to a CSV file named `parsed_grok_<original_filename>.log.csv` in the same directory as the input file.
  - Reports the number of lines parsed and skipped.

- **Group-based Directory Parsing (`-d`):**
  - Requires log collection (`collect` command) to have been run previously for the specified directory.
  - It queries Elasticsearch for group information associated with the given original log directory.
  - For each group, it attempts to determine a common Grok pattern by sampling the first available log file in that group (using an LLM if no consistent pattern is found quickly).
  - It then processes all log files belonging to each group.
    - If a group-level pattern was determined, it's used.
    - If a file fails with the group pattern, it might attempt a fallback to generate a file-specific pattern.
  - Can run in parallel using multiple worker processes (`-t` option) for different files.
  - Outputs CSV files similar to single file mode, stored alongside the original log files.

---

## Options

**Input Source (Mutually Exclusive, Required):**

- `-d DIRECTORY`, `--directory DIRECTORY`:
  Specifies the _original_ root directory path of the logs that were previously processed by the `collect` command. This triggers group-based parsing. The actual log files parsed are based on the absolute paths stored during collection.
- `-f FILE`, `--file FILE`:
  Specifies the direct path to a single local log file to be parsed.

**Common Options:**

- `--grok-pattern "PATTERN_STRING"`:
  (Optional, **only applicable when using `-f`/`--file` mode**)
  Allows you to provide a specific Grok pattern string to be used for parsing the single file. If this option is omitted when using `-f`, the system will attempt to generate a Grok pattern using an LLM based on sample lines from the file. This option is ignored if `-d` is used.
- `-v`, `--show-progress`:
  When using group-based parsing (`-d`) and running sequentially (i.e., `threads=1`), this flag disables the compact, overwriting progress bar and instead shows detailed per-file status updates directly in the console. For parallel runs, detailed status is typically always shown.
- `-t THREADS`, `--threads THREADS`:
  (Only applicable when using `-d`/`--directory` mode)
  Specifies the number of parallel worker processes to use for parsing log files. This can significantly speed up parsing for large numbers of files or groups. Defaults to `1` (sequential execution). Ignored if `-f` is used.
  Example: `-t 4` will use up to 4 worker processes. The maximum sensible value is typically the number of CPU cores on your machine.

---

## Examples

1.  **Parse all log groups associated with an original log directory `./my_collected_logs` using 4 threads:**
    _(This assumes `python -m src.logllm collect -d ./my_collected_logs` was run previously)_

    ```bash
    python -m src.logllm parse -d ./my_collected_logs -t 4
    ```

    This command will look up groups related to `./my_collected_logs` in Elasticsearch, then parse the log files (wherever they are located based on the paths stored during collection) belonging to those groups. Output CSVs will be placed next to their respective original log files.

2.  **Parse a single log file, letting the LLM generate the Grok pattern:**

    ```bash
    python -m src.logllm parse -f /var/log/custom_app/service.log
    ```

    A CSV file named `parsed_grok_service.log.csv` will be created in `/var/log/custom_app/`.

3.  **Parse a single log file with a user-provided Grok pattern:**
    ```bash
    python -m src.logllm parse -f /opt/logs/auth.log --grok-pattern "%{SYSLOGTIMESTAMP:timestamp} %{SYSLOGHOST:hostname} sshd\[%{INT:pid}\]: %{GREEDYDATA:message}"
    ```
    A CSV file named `parsed_grok_auth.log.csv` will be created in `/opt/logs/`.

---

**Output:**

- The primary output is CSV files containing the structured data extracted by the Grok patterns.
- The console will display status messages, including which files are being processed, success/failure indicators, and a summary of parsed/skipped lines or generated CSVs.
- If LLM pattern generation is used, messages about this process will also appear.
