# logLLM: Intelligent Log Analysis Orchestration

`logLLM` is a Python-based system designed for help user monitor system log under the help of AI

## Prerequisites

- Python 3.9+
- Docker (or Colima on macOS) for running Elasticsearch & Kibana.
- `git` (for prompt management version control).
- Google Generative AI API Key (set as `GENAI_API_KEY` environment variable) for LLM features.

## Quick Start

1.  **Clone the Repository:**

    ```bash
    git clone <repository_url>
    cd logllm
    ```

2.  **Set up Python Environment (Recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt # Assuming a requirements.txt exists
    ```

3.  **Set `GENAI_API_KEY`:**
    Export your Google AI API key as an environment variable:

    ```bash
    export GENAI_API_KEY="YOUR_API_KEY"
    ```

4.  **Start Backend Services (Elasticsearch & Kibana):**
    This command uses Docker to start the necessary containers. On macOS, it may manage Colima.

    ```bash
    python -m src.logllm db start
    ```

    Wait for the services to be fully up. Elasticsearch is typically at `http://localhost:9200`, Kibana at `http://localhost:5601`.

5.  **Collect Logs:**
    Place your log files in a directory (e.g., `./sample_logs/`). The `collect` command will scan this directory, group logs, and ingest them into Elasticsearch.

    ```bash
    # Example: assuming logs are in ./sample_logs/
    # and this directory contains subdirectories like ./sample_logs/apache/, ./sample_logs/hadoop/
    python -m src.logllm collect -d ./sample_logs
    ```

6.  **Parse Logs in Elasticsearch:**
    This command processes the raw logs collected into Elasticsearch, generates Grok patterns (LLM-assisted), parses the logs, and stores structured results back into new Elasticsearch indices.

    ```bash
    # Parse all collected groups using 2 worker threads
    python -m src.logllm es-parse run -t 2
    ```

    - Parsed logs go to `parsed_log_<group_name>`.
    - Unparsed/fallback logs go to `unparsed_log_<group_name>`.
    - History of parsing runs is stored in `grok_results_history`.

7.  **Normalize Timestamps:**
    Process the parsed logs to standardize their timestamps to UTC ISO 8601.

    ```bash
    # Normalize timestamps for all groups that were parsed
    python -m src.logllm normalize-ts run --all-groups -t 2
    ```

    - Normalized logs are stored in `normalized_parsed_log_<group_name>`.

8.  **Analyze Errors (Example):**
    Run the error analysis pipeline on a specific group's normalized logs.

    ```bash
    # Analyze errors for the 'apache' group from the last 7 days
    python -m src.logllm analyze-errors run -g apache --time-window "now-7d"
    ```

    - Summaries are stored in `log_error_summaries`.

9.  **Explore Other Commands:**
    - `python -m src.logllm pm scan -d src/logllm/agents -r`: Scan for prompts.
    - `python -m src.logllm parse -f /path/to/single.log`: Parse a single local file.
    - Use `--help` for any command to see its options (e.g., `python -m src.logllm es-parse list --help`).

## Full Documentation

For detailed information on architecture, individual commands, agents, and configuration, please refer to the [./doc/README.md](./doc/README.md).

## Stopping Services

    ```bash
    python -m src.logllm db stop
    ```
