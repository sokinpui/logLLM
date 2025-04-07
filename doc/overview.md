# Overview Documentation for `logLLM` Orchestration

## Overview (Updated)
The `logLLM` project uses a Command Line Interface (CLI) as its primary entry point, defined in `src/logllm/cli/__main__.py`. This CLI acts as the central orchestrator, dispatching tasks to various specialized modules and agents based on the user-provided command (e.g., `db`, `collect`, `parse`, `es-parse`, `pm`). Instead of a single, monolithic graph defined in a `graph.py` file, the project employs a collection of potentially independent or sequentially invoked workflows managed through the CLI structure.

---

## Purpose
The CLI (`__main__.py`) and its associated command handlers (in `src/logllm/cli/`) are designed to:
- **Provide User Interface**: Offer a clear and structured way for users to interact with the different functionalities of the `logLLM` system (database management, collection, parsing, prompt management).
- **Dispatch Workflows**: Route user commands to the appropriate handler functions, which in turn initialize and run the necessary utility classes or agent workflows.
- **Manage Dependencies**: Ensure that core components like the database connection, LLM model, and logger are initialized correctly for the requested command.
- **Coordinate Functionality**: Enable different parts of the system (e.g., collection, parsing) to work together, often relying on shared resources like the Elasticsearch database and configuration settings.

---

## Structure and High-Level Functionality
The orchestration layer is implemented through the `argparse` library in `__main__.py` and handler functions within the `src/logllm/cli/` directory.

### Key Components:
- **`src/logllm/cli/__main__.py`**:
    - Defines the main parser and subparsers for each top-level command (`db`, `collect`, `parse`, `es-parse`, `pm`).
    - Handles global arguments (`--verbose`, `--test`, `--json`).
    - Registers the specific argument parsers for each command from their respective files (e.g., `collect.register_collect_parser`).
    - Parses the command-line arguments and calls the appropriate handler function (`args.func(args)`).
- **`src/logllm/cli/*.py` (e.g., `collect.py`, `parse.py`, `es_parse.py`, `pm.py`, `container.py`):**
    - Each file defines the specific arguments for its command (e.g., `collect` takes `-d`).
    - Contains a registration function (e.g., `register_collect_parser`) to add its parser to the main subparser group.
    - Contains a handler function (e.g., `handle_collect`) that implements the logic for that command, often by:
        - Initializing necessary utilities (Database, Logger, Model, PromptsManager).
        - Calling methods on utility classes (e.g., `Collector`, `DockerManager`).
        - Initializing and running specific agents (e.g., `GroupLogParserAgent`, `AllGroupsParserAgent`).

### Workflow Execution:
- Workflows are typically triggered by executing a specific CLI command.
- **Example (`collect` command):**
    1. User runs `python -m src.logllm collect -d ./logs`.
    2. `__main__.py` parses the command and calls `handle_collect` in `collect.py`.
    3. `handle_collect` initializes `ElasticsearchDatabase` and `Collector`.
    4. It calls methods on `Collector` (e.g., `insert_very_large_logs_into_db`) to perform the collection and ingestion task.
- **Example (`es-parse` command):**
    1. User runs `python -m src.logllm es-parse -g hadoop`.
    2. `__main__.py` calls `handle_es_parse` in `es_parse.py`.
    3. `handle_es_parse` initializes `ElasticsearchDatabase`, `GeminiModel`, `PromptsManager`.
    4. It initializes the appropriate agent (`SingleGroupParserAgent` in this case).
    5. It calls the agent's `run` method, which executes the internal LangGraph workflow for parsing that specific group.
    6. The handler function then displays a summary based on the agent's final state.

### Agent Interaction:
- While there isn't one overarching `graph.py`, individual commands like `es-parse` *do* use agents built with graph-based structures (`langgraph`) internally (e.g., `SingleGroupParserAgent` in `es_parser_agent.py`).
- Data sharing between *different* command workflows often happens implicitly via the shared Elasticsearch database (e.g., `collect` writes raw logs and group info, `parse`/`es-parse` read this data).

---

## Usage Notes
- **Execution**: Run commands via `python -m src.logllm <command> [options]`.
- **Dependencies**: Ensure required services (like Elasticsearch via `db start`) are running before executing commands that depend on them (like `collect`, `es-parse`).
- **Configuration**: System behavior is heavily influenced by `src/logllm/config/config.py`.
- **Modularity**: New commands or functionalities can be added by creating new files in `src/logllm/cli/`, defining their arguments, handler, and registration function, and registering them in `__main__.py`.

---

## Conceptual Example
Instead of a single graph, think of the CLI as a switchboard:
- `python -m src.logllm db start` -> Connects to the "Start DB Containers" workflow in `cli/container.py`.
- `python -m src.logllm collect -d logs` -> Connects to the "Collect Logs" workflow in `cli/collect.py`.
- `python -m src.logllm es-parse -t 4` -> Connects to the "Parse Logs in ES (All Groups, Parallel)" workflow in `cli/es_parse.py`, which internally uses `AllGroupsParserAgent`.
- `python -m src.logllm pm scan -d src` -> Connects to the "Scan for Prompts" workflow in `cli/pm.py`.

Each command triggers a distinct (though potentially related via shared data) workflow.

